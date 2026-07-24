"""Execution-only authority for already-approved promotion decisions."""
from __future__ import annotations

from contextlib import contextmanager
from datetime import datetime, timezone
from hashlib import sha256
import hmac
import json
import os
from pathlib import Path
import socket
from typing import Any, Mapping
from uuid import NAMESPACE_URL, UUID, uuid4, uuid5

from .models import PromotionAuthorityConfig, PromotionRecord, PromotionTransaction
from .storage import PromotionRecordStorage


def _canonical(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)


def _digest(value: Any) -> str:
    return sha256(_canonical(value).encode("utf-8")).hexdigest()


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _iso(value: datetime) -> str:
    return value.isoformat(timespec="microseconds").replace("+00:00", "Z")


class PromotionAuthority:
    """Validate trusted decisions and request one idempotent lifecycle CAS transition."""

    def __init__(self, *, config: PromotionAuthorityConfig | None = None, root="learning_data",
                 lifecycle_service=None, clock=_now) -> None:
        self.config = config or PromotionAuthorityConfig()
        self.storage = PromotionRecordStorage(root)
        self.root = Path(root)
        if lifecycle_service is None:
            raise ValueError("LIFECYCLE_TRANSITION_PORT_REQUIRED")
        self.lifecycle_service = lifecycle_service
        self.clock = clock

    @staticmethod
    def _data(report: Any) -> Mapping[str, Any] | None:
        return report.to_dict() if hasattr(report, "to_dict") else report if isinstance(report, Mapping) else None

    @staticmethod
    def _semantic(data: Mapping[str, Any]) -> str:
        value = data.get("semantic_identity") or data.get("knowledge_uuid")
        if not isinstance(value, str) or not value:
            raise ValueError("MISSING_PROMOTION_SEMANTIC_IDENTITY")
        return value

    @contextmanager
    def _lock(self, semantic: str):
        locks = self.root / "promotion_locks"
        locks.mkdir(parents=True, exist_ok=True)
        path = locks / (sha256(semantic.encode("utf-8")).hexdigest() + ".lock")
        owner = str(uuid4())
        now = self.clock()
        payload = {"owner": owner, "pid": os.getpid(), "host": socket.gethostname(), "acquired_at": _iso(now)}
        encoded = (_canonical(payload) + "\n").encode("utf-8")
        fd = None
        for _ in range(2):
            try:
                fd = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
                os.write(fd, encoded)
                break
            except FileExistsError as exc:
                try:
                    current = json.loads(path.read_text(encoding="utf-8"))
                    acquired = datetime.fromisoformat(current["acquired_at"].replace("Z", "+00:00"))
                    stale = (now - acquired).total_seconds() > self.config.lock_lease_seconds
                except (OSError, ValueError, KeyError, TypeError, json.JSONDecodeError):
                    stale = False
                if not stale:
                    raise RuntimeError("PROMOTION_LOCK_CONTENDED") from exc
                tombstone = path.with_suffix(f".stale.{uuid4().hex}")
                try:
                    path.replace(tombstone)
                except FileNotFoundError:
                    continue
        if fd is None:
            raise RuntimeError("PROMOTION_LOCK_CONTENDED")
        try:
            yield
        finally:
            os.close(fd)
            try:
                current = json.loads(path.read_text(encoding="utf-8"))
                if current.get("owner") == owner:
                    path.unlink(missing_ok=True)
            except (OSError, ValueError, json.JSONDecodeError):
                pass

    def validate(self, report: Any) -> dict[str, Any]:
        data = self._data(report)
        if not isinstance(data, Mapping):
            raise ValueError("MISSING_PROMOTION_DECISION_REPORT")
        required = {"decision_uuid", "knowledge_uuid", "decision", "decision_status", "snapshot_digest",
                    "qualification_digest", "policy_version", "created_at", "schema_version",
                    "configuration_digest", "signature"}
        if not required.issubset(data) or any(not isinstance(data[key], str) or not data[key] for key in required):
            raise ValueError("INVALID_PROMOTION_DECISION_REPORT")
        try:
            UUID(data["decision_uuid"])
            UUID(data["knowledge_uuid"])
        except (ValueError, TypeError, AttributeError) as exc:
            raise ValueError("INVALID_PROMOTION_UUID") from exc
        if data["decision"] != "PROMOTE" or data["decision_status"] != "APPROVED":
            raise ValueError("PROMOTION_DECISION_NOT_EXECUTABLE")
        if data["schema_version"] != self.config.expected_schema_version:
            raise ValueError("UNKNOWN_PROMOTION_DECISION_SCHEMA")
        if data["policy_version"] not in self.config.allowed_policy_versions:
            raise ValueError("UNAPPROVED_PROMOTION_CONFIGURATION")
        for name in ("snapshot_digest", "qualification_digest", "configuration_digest", "signature"):
            if len(data[name]) != 64 or any(char not in "0123456789abcdef" for char in data[name].lower()):
                raise ValueError("INVALID_PROMOTION_DIGEST")
        if self.config.approved_configuration_digests and data["configuration_digest"] not in self.config.approved_configuration_digests:
            raise ValueError("UNAPPROVED_PROMOTION_CONFIGURATION")
        trusted = self.config.trusted_decision_signatures.get(data["decision_uuid"])
        if not trusted or not hmac.compare_digest(trusted, data["signature"]):
            raise ValueError("UNTRUSTED_PROMOTION_DECISION")
        unsigned = dict(data)
        supplied = unsigned.pop("signature")
        if not hmac.compare_digest(supplied, _digest(unsigned)):
            raise ValueError("INVALID_PROMOTION_SIGNATURE")
        try:
            created = datetime.fromisoformat(data["created_at"].replace("Z", "+00:00"))
        except ValueError as exc:
            raise ValueError("INVALID_PROMOTION_TIMESTAMP") from exc
        if created.tzinfo is None:
            raise ValueError("INVALID_PROMOTION_TIMESTAMP")
        age = (self.clock() - created).total_seconds()
        if age < 0 or age > self.config.maximum_decision_age_seconds:
            raise ValueError("EXPIRED_PROMOTION_DECISION")
        result = dict(data)
        result["semantic_identity"] = self._semantic(data)
        return result

    def _record(self, tx: PromotionTransaction, transition: Mapping[str, Any], status: str,
                *, previous: str = "", error: str = "") -> PromotionRecord:
        record_uuid = str(uuid5(NAMESPACE_URL, f"{tx.decision_uuid}:{status}"))
        return PromotionRecord(record_uuid, tx.decision_uuid, tx.knowledge_uuid, tx.semantic_identity,
                               transition, _iso(self.clock()), status, self.config.operator,
                               self.config.version, tx.transaction_uuid, previous, error)

    def execute(self, report: Any) -> PromotionRecord:
        data = self.validate(report)
        existing = self.storage.committed(data["decision_uuid"])
        if existing:
            return existing
        tx = PromotionTransaction(str(uuid4()), data["decision_uuid"], data["knowledge_uuid"], data["semantic_identity"])
        tx.set_state("VALIDATING")
        with self._lock(tx.semantic_identity):
            tx.set_state("LOCKED")
            existing = self.storage.committed(tx.decision_uuid)
            if existing:
                return existing
            transition = {
                "knowledge_uuid": tx.knowledge_uuid,
                "expected_current_state": "VERIFIED",
                "new_state": "ACTIVE",
                "idempotency_key": tx.decision_uuid,
                "triggering_component": "PromotionAuthority",
                "reason": f"approved promotion decision {tx.decision_uuid}",
                "governance_version": self.config.governance_version,
                "lifecycle_version": self.config.lifecycle_version,
                "timestamp": _iso(self.clock()),
                "transition_uuid": str(uuid5(NAMESPACE_URL, tx.decision_uuid)),
            }
            prepared = self._record(tx, transition, "PREPARED")
            self.storage.write(prepared)
            tx.record = prepared
            tx.set_state("PREPARED")
            lifecycle_called = False
            try:
                tx.set_state("EXECUTING")
                lifecycle_called = True
                event = self.lifecycle_service(**transition)
                event_data = event.to_dict() if hasattr(event, "to_dict") else event
                if not isinstance(event_data, Mapping):
                    raise RuntimeError("LIFECYCLE_TRANSITION_MISMATCH")
                for key in ("knowledge_uuid", "new_state", "idempotency_key", "transition_uuid"):
                    if event_data.get(key) != transition[key]:
                        raise RuntimeError("LIFECYCLE_TRANSITION_MISMATCH")
                tx.set_state("COMMITTING")
                committed = self._record(tx, transition, "COMMITTED", previous=prepared.record_uuid)
                self.storage.write(committed)
                tx.record = committed
                tx.set_state("COMPLETED")
                return committed
            except Exception as exc:
                tx.error = str(exc)
                status = "IN_DOUBT" if lifecycle_called else "FAILED"
                tx.set_state(status)
                failure = self._record(tx, transition, status, previous=prepared.record_uuid, error=str(exc))
                self.storage.write(failure)
                raise

    def history(self, decision_uuid: str | None = None) -> tuple[PromotionRecord, ...]:
        records = self.storage.all()
        return tuple(record for record in records if decision_uuid is None or record.decision_uuid == decision_uuid)
