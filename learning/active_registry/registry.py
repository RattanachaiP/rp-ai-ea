"""Canonical trusted projection of authoritative Knowledge lifecycle receipts."""
from __future__ import annotations

from contextlib import contextmanager
from dataclasses import replace
from datetime import datetime, timedelta, timezone
from hashlib import sha256
import hmac
import json
import os
from pathlib import Path
import socket
from typing import Any, Mapping
from uuid import NAMESPACE_URL, UUID, uuid4, uuid5

from .models import ActiveKnowledgeEntry, EVENT_TYPES
from .storage import ActiveRegistryStorage


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _iso(value: datetime) -> str:
    return value.isoformat(timespec="microseconds").replace("+00:00", "Z")


def _data(value: Any) -> Mapping[str, Any] | None:
    value = value.to_dict() if hasattr(value, "to_dict") else value
    return value if isinstance(value, Mapping) else None


def _uuid(value: object) -> bool:
    try:
        UUID(str(value)); return True
    except (ValueError, TypeError, AttributeError):
        return False


def _timestamp(value: object) -> bool:
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00")).tzinfo is not None
    except (ValueError, TypeError, AttributeError):
        return False


def _receipt_digest(data: Mapping[str, Any]) -> str:
    unsigned = dict(data); unsigned.pop("signature", None)
    canonical = json.dumps(unsigned, sort_keys=True, separators=(",", ":"), allow_nan=False)
    return sha256(canonical.encode("utf-8")).hexdigest()


class ActiveKnowledgeRegistry:
    """Append-only read model fed only by pre-authorized lifecycle receipts."""

    def __init__(self, *, root: str | Path = "learning_data", trusted_receipts: Mapping[str, str] | None = None,
                 approved_sources: tuple[str, ...] = ("PromotionAuthority", "LifecycleAuthority"),
                 lock_lease_seconds: int = 30, clock=_now) -> None:
        if not isinstance(lock_lease_seconds, int) or isinstance(lock_lease_seconds, bool) or lock_lease_seconds < 1:
            raise ValueError("INVALID_ACTIVE_REGISTRY_CONFIG")
        self.root = Path(root); self.storage = ActiveRegistryStorage(root)
        self.trusted_receipts = dict(trusted_receipts or {}); self.approved_sources = tuple(approved_sources)
        self.lock_lease_seconds = lock_lease_seconds; self.clock = clock

    @contextmanager
    def _semantic_lock(self, semantic_identity: str):
        directory = self.root / "active_registry_locks"; directory.mkdir(parents=True, exist_ok=True)
        path = directory / f"{sha256(semantic_identity.encode()).hexdigest()}.lock"
        owner, now = str(uuid4()), self.clock()
        payload = {"owner": owner, "pid": os.getpid(), "hostname": socket.gethostname(),
                   "acquired_at": _iso(now), "expires_at": _iso(now + timedelta(seconds=self.lock_lease_seconds))}
        encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
        fd = None
        for attempt in range(2):
            try:
                fd = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY); os.write(fd, encoded); os.fsync(fd); break
            except FileExistsError as exc:
                try:
                    current = json.loads(path.read_text(encoding="utf-8"))
                    expires = datetime.fromisoformat(str(current["expires_at"]).replace("Z", "+00:00"))
                except (OSError, ValueError, TypeError, KeyError, json.JSONDecodeError):
                    raise RuntimeError("ACTIVE_REGISTRY_LOCK_CORRUPTED") from exc
                if attempt == 0 and expires <= self.clock(): path.unlink(missing_ok=True); continue
                raise RuntimeError("ACTIVE_REGISTRY_LOCK_CONTENDED") from exc
        try:
            yield
        finally:
            if fd is not None:
                os.close(fd)
                try: current = json.loads(path.read_text(encoding="utf-8"))
                except (OSError, ValueError, TypeError, json.JSONDecodeError): current = {}
                if current.get("owner") == owner: path.unlink(missing_ok=True)

    def _project(self) -> dict[str, ActiveKnowledgeEntry]:
        projected = {}
        for event in self.storage.all():
            if event.event_type == "SUPERSESSION":
                projected[event.previous_knowledge_uuid] = replace(
                    event, knowledge_uuid=event.previous_knowledge_uuid, status="SUPERSEDED")
                projected[event.knowledge_uuid] = event
            else:
                projected[event.knowledge_uuid] = event
        return projected

    def _validate_receipt(self, receipt: Any) -> Mapping[str, Any]:
        data = _data(receipt)
        required = {"receipt_uuid", "event_type", "knowledge_uuid", "semantic_identity", "effective_at", "sequence",
                    "source_event_uuid", "source_authority", "source_version", "schema_version", "configuration_version",
                    "lineage_reference", "reason", "signature"}
        if not isinstance(data, Mapping): raise ValueError("MISSING_ACTIVE_REGISTRY_RECEIPT")
        if not required.issubset(data): raise ValueError("INVALID_ACTIVE_REGISTRY_RECEIPT")
        if (not _uuid(data["receipt_uuid"]) or not _uuid(data["knowledge_uuid"]) or not _uuid(data["source_event_uuid"])
                or data["event_type"] not in EVENT_TYPES or not _timestamp(data["effective_at"])
                or not isinstance(data["sequence"], int) or isinstance(data["sequence"], bool) or data["sequence"] < 1
                or data["source_authority"] not in self.approved_sources
                or any(not isinstance(data[k], str) or not data[k].strip() for k in (
                    "semantic_identity", "source_version", "schema_version", "configuration_version",
                    "lineage_reference", "reason", "signature"))):
            raise ValueError("INVALID_ACTIVE_REGISTRY_RECEIPT")
        trusted = self.trusted_receipts.get(data["receipt_uuid"]); computed = _receipt_digest(data)
        if trusted is None or not hmac.compare_digest(trusted, computed) or not hmac.compare_digest(data["signature"], computed):
            raise ValueError("UNTRUSTED_ACTIVE_REGISTRY_RECEIPT")
        if data["event_type"] == "SUPERSESSION":
            if not _uuid(data.get("previous_knowledge_uuid")) or not _uuid(data.get("previous_activation_uuid")) or data["previous_knowledge_uuid"] == data["knowledge_uuid"]:
                raise ValueError("INVALID_SUPERSESSION_RECEIPT")
        elif data["event_type"] in {"RETIREMENT", "ARCHIVAL"} and not _uuid(data.get("previous_activation_uuid")):
            raise ValueError("INVALID_TERMINAL_RECEIPT")
        return dict(data)

    def _entry(self, receipt: Mapping[str, Any]) -> ActiveKnowledgeEntry:
        kind = receipt["event_type"]
        status = {"ACTIVATION": "ACTIVE", "SUPERSESSION": "ACTIVE", "RETIREMENT": "RETIRED", "ARCHIVAL": "ARCHIVED"}[kind]
        return ActiveKnowledgeEntry(
            activation_uuid=str(uuid5(NAMESPACE_URL, f"active-registry:{receipt['receipt_uuid']}:{kind}")),
            knowledge_uuid=receipt["knowledge_uuid"], semantic_identity=receipt["semantic_identity"],
            activation_timestamp=receipt["effective_at"], activation_reason=receipt["reason"],
            source_receipt_uuid=receipt["receipt_uuid"], source_event_uuid=receipt["source_event_uuid"],
            source_authority=receipt["source_authority"], schema_version=receipt["schema_version"],
            configuration_version=receipt["configuration_version"], lineage_reference=receipt["lineage_reference"],
            event_type=kind, sequence=receipt["sequence"], status=status,
            previous_knowledge_uuid=receipt.get("previous_knowledge_uuid", ""),
            previous_activation_uuid=receipt.get("previous_activation_uuid", ""), metadata=receipt.get("metadata", {}))

    def apply(self, receipt: Any) -> ActiveKnowledgeEntry:
        data = self._validate_receipt(receipt); existing = self.storage.by_receipt(data["receipt_uuid"])
        if existing: return existing
        with self._semantic_lock(data["semantic_identity"]):
            existing = self.storage.by_receipt(data["receipt_uuid"])
            if existing: return existing
            events = self.storage.all(); expected = events[-1].sequence + 1 if events else 1
            if data["sequence"] != expected: raise ValueError("ACTIVE_REGISTRY_SEQUENCE_MISMATCH")
            current = self._project(); kind = data["event_type"]; knowledge = data["knowledge_uuid"]; semantic = data["semantic_identity"]
            active = [x for x in current.values() if x.status == "ACTIVE" and x.semantic_identity == semantic]
            if kind == "ACTIVATION":
                if current.get(knowledge): raise ValueError("KNOWLEDGE_ALREADY_REGISTERED")
                if active: raise ValueError("DUPLICATE_ACTIVE_SEMANTIC_IDENTITY")
            elif kind == "SUPERSESSION":
                old = current.get(data["previous_knowledge_uuid"])
                if (not old or old.status != "ACTIVE" or old.semantic_identity != semantic
                        or old.activation_uuid != data["previous_activation_uuid"] or current.get(knowledge)
                        or any(x.knowledge_uuid != old.knowledge_uuid for x in active)):
                    raise ValueError("BROKEN_SUPERSESSION_LINEAGE")
            elif kind == "RETIREMENT":
                old = current.get(knowledge)
                if not old or old.status != "ACTIVE" or old.activation_uuid != data["previous_activation_uuid"]:
                    raise ValueError("BROKEN_RETIREMENT_LINEAGE")
            else:
                old = current.get(knowledge)
                if not old or old.status != "RETIRED" or old.activation_uuid != data["previous_activation_uuid"]:
                    raise ValueError("BROKEN_ARCHIVAL_LINEAGE")
            entry = self._entry(data); self.storage.write(entry); return entry

    def register(self, receipt: Any) -> ActiveKnowledgeEntry:
        data = self._validate_receipt(receipt)
        if data["event_type"] not in {"ACTIVATION", "SUPERSESSION"}: raise ValueError("ACTIVATION_RECEIPT_REQUIRED")
        return self.apply(data)

    def apply_lifecycle_event(self, receipt: Any) -> ActiveKnowledgeEntry:
        data = self._validate_receipt(receipt)
        if data["event_type"] not in {"RETIREMENT", "ARCHIVAL"}: raise ValueError("LIFECYCLE_RECEIPT_REQUIRED")
        return self.apply(data)

    def get_active(self, knowledge_uuid: str):
        entry = self._project().get(knowledge_uuid); return entry if entry and entry.status == "ACTIVE" else None
    def get_by_uuid(self, knowledge_uuid: str): return self._project().get(knowledge_uuid)
    def get_by_semantic_identity(self, semantic_identity: str, *, active_only: bool = True):
        values = [x for x in self._project().values() if x.semantic_identity == semantic_identity and (not active_only or x.status == "ACTIVE")]
        return tuple(sorted(values, key=lambda x: (x.sequence, x.knowledge_uuid)))
    def history(self, knowledge_uuid: str | None = None):
        events = self.storage.all()
        return events if knowledge_uuid is None else tuple(x for x in events if x.knowledge_uuid == knowledge_uuid or x.previous_knowledge_uuid == knowledge_uuid)
    def list_active(self):
        return tuple(sorted((x for x in self._project().values() if x.status == "ACTIVE"), key=lambda x: (x.semantic_identity, x.knowledge_uuid)))
    def lookup(self, value: str): return self.get_active(value) or next(iter(self.get_by_semantic_identity(value)), None)
    def resolve(self, semantic_identity: str): return next(iter(self.get_by_semantic_identity(semantic_identity)), None)
