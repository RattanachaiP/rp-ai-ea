"""Fail-closed assembly from an authorized decision to an MT5 package.

This boundary copies runtime truth.  It does not infer execution authority from
direction, calculate risk, validate a broker request, or send an order.
"""
from __future__ import annotations

from datetime import datetime, timezone
import json
from math import isfinite
import os
from pathlib import Path
from typing import Callable, Mapping
from uuid import UUID, uuid4

from execution_package_contract import (
    EXECUTABLE_DECISION, EXECUTABLE_DECISION_LIFECYCLE, EXECUTABLE_STATES,
    EXECUTION_PACKAGE_FIELDS, EXECUTION_PACKAGE_SCHEMA_VERSION,
)
from runtime.decision_publication import (
    DECISION_HEARTBEAT_MAXIMUM_AGE_SECONDS, DECISION_PRODUCER,
    PUBLISHED_SCHEMA_VERSION, RUNTIME_VERSION,
)
from runtime.market_state_reader import (
    MARKET_STATE_MAXIMUM_AGE_SECONDS, SOURCE_UUID as MARKET_STATE_SOURCE_UUID,
)


FAILURE_OWNERS = frozenset({"ASSEMBLY", "VALIDATION", "PUBLICATION"})
STATE_SCHEMA_VERSION = "1.0"


class ExecutionPackageError(ValueError):
    """A governed failure with stable ownership and reason."""

    def __init__(self, owner: str, reason: str) -> None:
        if owner not in FAILURE_OWNERS:
            raise ValueError("INVALID_FAILURE_OWNER")
        super().__init__(reason)
        self.owner, self.reason = owner, reason


class ExecutionPackageAssembler:
    """Verify, construct, validate, durably sequence, and atomically publish."""

    def __init__(self, decision_path: Path | str, output_path: Path | str,
                 *, clock: Callable[[], float] | None = None,
                 uuid_factory: Callable[[], object] | None = None) -> None:
        self.decision_path, self.output_path = Path(decision_path), Path(output_path)
        if self.decision_path.name != "decision.json":
            raise ValueError("INPUT_MUST_BE_DECISION_JSON")
        if self.output_path.name != "execution_package.json":
            raise ValueError("OUTPUT_MUST_BE_EXECUTION_PACKAGE_JSON")
        self.root = self.output_path.parent
        self.state_path = self.root / "execution_package_state.json"
        self.trace_path = self.root / "execution_package_trace.log"
        self.health_path = self.root / "execution_package_health.json"
        self._clock, self._uuid_factory = clock or __import__("time").time, uuid_factory or uuid4

    def assemble(self) -> dict[str, object]:
        """Publish exactly one already-authorized runtime decision."""
        self.root.mkdir(parents=True, exist_ok=True)
        try:
            decision = self._read_and_verify()
            self._trace("ASSEMBLY", "ACCEPTED", "authorized decision accepted")
            package = self._construct(decision)
            self._trace("ASSEMBLY", "ASSEMBLED", "execution facts copied")
            self._validate(package, decision)
            self._trace("VALIDATION", "VALID", "schema, authority, and lineage verified")
            # Authority advances first.  A crash can suppress/reject a package,
            # never republish an older sequence after deletion or rollback.
            self._publish_state(package)
            try:
                self._atomic_write(self.output_path, self._serialize(package))
            except OSError as error:
                raise ExecutionPackageError("PUBLICATION", "PACKAGE_PUBLICATION_FAILED") from error
            self._trace("PUBLICATION", "PUBLISHED", "atomic replacement complete")
        except ExecutionPackageError as error:
            self._record_failure(error)
            raise
        except (OSError, json.JSONDecodeError, TypeError, ValueError) as error:
            governed = ExecutionPackageError("ASSEMBLY", "DECISION_PUBLICATION_UNREADABLE")
            self._record_failure(governed)
            raise governed from error
        self._publish_observational_health(package)
        return package

    def _read_and_verify(self) -> dict[str, object]:
        value = json.loads(self.decision_path.read_bytes())
        if type(value) is not dict:
            raise ExecutionPackageError("VALIDATION", "INVALID_DECISION_SCHEMA")
        required = {
            "decision_uuid", "market_state_sequence_id", "heartbeat_unix", "producer",
            "producer_version", "schema_version", "market_state_source_uuid", "symbol",
            "direction", "confidence", "active_profile", "volume", "entry_price",
            "stop_loss", "take_profit", "management", "decision_timestamp",
            "decision_lifecycle", "decision", "execution_state", "final_veto_owner",
            "effective_veto_code", "entry_allowed", "executor_order_send_required",
        }
        missing = sorted(required.difference(value))
        if missing:
            raise ExecutionPackageError("VALIDATION", f"MISSING_DECISION_FIELD_{missing[0].upper()}")
        if value["producer"] != DECISION_PRODUCER:
            raise ExecutionPackageError("VALIDATION", "INVALID_DECISION_PRODUCER")
        if value["producer_version"] != RUNTIME_VERSION:
            raise ExecutionPackageError("VALIDATION", "INVALID_DECISION_PRODUCER_VERSION")
        if value["schema_version"] != PUBLISHED_SCHEMA_VERSION:
            raise ExecutionPackageError("VALIDATION", "INVALID_DECISION_SCHEMA")
        self._uuid(value["decision_uuid"], "INVALID_DECISION_UUID")
        self._uuid(value["market_state_source_uuid"], "INVALID_SOURCE_UUID")
        if value["market_state_source_uuid"] != MARKET_STATE_SOURCE_UUID:
            raise ExecutionPackageError("VALIDATION", "INVALID_LINEAGE")
        heartbeat = value["heartbeat_unix"]
        # Publication freshness is Runtime-owned.  The imported market limit is
        # retained as a stricter lineage-age ceiling for the embedded market fact.
        maximum_age = min(DECISION_HEARTBEAT_MAXIMUM_AGE_SECONDS, MARKET_STATE_MAXIMUM_AGE_SECONDS)
        if type(heartbeat) is not int or heartbeat <= 0 or abs(float(self._clock()) - heartbeat) > maximum_age:
            raise ExecutionPackageError("VALIDATION", "STALE_HEARTBEAT")
        sequence = value["market_state_sequence_id"]
        if type(sequence) is not int or sequence < 1:
            raise ExecutionPackageError("VALIDATION", "INVALID_MARKET_SEQUENCE")
        self._verify_runtime_authority(value)
        state = self._load_state()
        if state is not None and sequence <= state["last_market_sequence"]:
            raise ExecutionPackageError("VALIDATION", "NON_MONOTONIC_SEQUENCE")
        return value

    @staticmethod
    def _verify_runtime_authority(value: Mapping[str, object]) -> None:
        if value["decision_lifecycle"] != EXECUTABLE_DECISION_LIFECYCLE:
            raise ExecutionPackageError("VALIDATION", "DECISION_LIFECYCLE_NOT_EXECUTABLE")
        if value["decision"] != EXECUTABLE_DECISION:
            raise ExecutionPackageError("VALIDATION", "DECISION_NOT_AUTHORIZED")
        if value["execution_state"] not in EXECUTABLE_STATES:
            raise ExecutionPackageError("VALIDATION", "EXECUTION_STATE_NOT_EXECUTABLE")
        if value["final_veto_owner"] != "NONE" or value["effective_veto_code"] != "NONE":
            raise ExecutionPackageError("VALIDATION", "RUNTIME_EXECUTION_VETOED")
        if value["entry_allowed"] is not True or value["executor_order_send_required"] is not True:
            raise ExecutionPackageError("VALIDATION", "RUNTIME_EXECUTION_NOT_AUTHORIZED")

    def _construct(self, decision: Mapping[str, object]) -> dict[str, object]:
        return {
            "execution_uuid": str(self._uuid_factory()), "decision_uuid": decision["decision_uuid"],
            "market_sequence": decision["market_state_sequence_id"], "heartbeat_unix": decision["heartbeat_unix"],
            "producer": decision["producer"], "producer_version": decision["producer_version"],
            "schema_version": EXECUTION_PACKAGE_SCHEMA_VERSION, "source_uuid": decision["market_state_source_uuid"],
            "symbol": decision["symbol"], "direction": decision["direction"], "confidence": decision["confidence"],
            "risk_profile": decision["active_profile"], "lot_size": decision["volume"],
            "entry": decision["entry_price"], "sl": decision["stop_loss"], "tp": decision["take_profit"],
            "management_profile": decision["management"], "execution_timestamp": self._timestamp(),
        }

    def _validate(self, package: Mapping[str, object], decision: Mapping[str, object]) -> None:
        if tuple(package) != EXECUTION_PACKAGE_FIELDS or package["schema_version"] != EXECUTION_PACKAGE_SCHEMA_VERSION:
            raise ExecutionPackageError("VALIDATION", "INVALID_EXECUTION_SCHEMA")
        for field in ("execution_uuid", "decision_uuid", "source_uuid"):
            self._uuid(package[field], f"INVALID_{field.upper()}")
        if (package["decision_uuid"] != decision["decision_uuid"] or package["source_uuid"] != decision["market_state_source_uuid"]
                or package["market_sequence"] != decision["market_state_sequence_id"]):
            raise ExecutionPackageError("VALIDATION", "INVALID_LINEAGE")
        for field in ("confidence", "lot_size", "entry", "sl", "tp"):
            if type(package[field]) not in (int, float) or not isfinite(package[field]):
                raise ExecutionPackageError("VALIDATION", f"INVALID_{field.upper()}")
        if package["direction"] not in {"BUY", "SELL"} or package["lot_size"] <= 0:
            raise ExecutionPackageError("VALIDATION", "INVALID_EXECUTION_FIELDS")
        for field in ("producer", "producer_version", "symbol", "risk_profile", "management_profile", "execution_timestamp"):
            if type(package[field]) is not str or not package[field]:
                raise ExecutionPackageError("VALIDATION", f"MISSING_{field.upper()}")

    def _load_state(self) -> dict[str, object] | None:
        try:
            state = json.loads(self.state_path.read_text(encoding="utf-8"))
        except FileNotFoundError:
            return None
        except (OSError, json.JSONDecodeError) as error:
            raise ExecutionPackageError("VALIDATION", "INVALID_PUBLICATION_STATE") from error
        fields = {"schema_version", "last_market_sequence", "last_decision_uuid", "last_execution_uuid", "last_publication_time"}
        if type(state) is not dict or set(state) != fields or state["schema_version"] != STATE_SCHEMA_VERSION:
            raise ExecutionPackageError("VALIDATION", "INVALID_PUBLICATION_STATE")
        if type(state["last_market_sequence"]) is not int or state["last_market_sequence"] < 1:
            raise ExecutionPackageError("VALIDATION", "INVALID_PUBLICATION_STATE")
        self._uuid(state["last_decision_uuid"], "INVALID_PUBLICATION_STATE")
        self._uuid(state["last_execution_uuid"], "INVALID_PUBLICATION_STATE")
        return state

    def _publish_state(self, package: Mapping[str, object]) -> None:
        state = {"schema_version": STATE_SCHEMA_VERSION, "last_market_sequence": package["market_sequence"],
                 "last_decision_uuid": package["decision_uuid"], "last_execution_uuid": package["execution_uuid"],
                 "last_publication_time": package["execution_timestamp"]}
        try:
            self._atomic_write(self.state_path, self._serialize(state))
        except OSError as error:
            raise ExecutionPackageError("PUBLICATION", "STATE_PUBLICATION_FAILED") from error

    def _publish_observational_health(self, package: Mapping[str, object]) -> None:
        value = {"status": "OBSERVED", "execution_uuid": package["execution_uuid"],
                 "decision_uuid": package["decision_uuid"], "market_sequence": package["market_sequence"],
                 "failure_owner": None, "failure_reason": None, "updated_at": self._timestamp()}
        try:
            self._atomic_write(self.health_path, self._serialize(value))
        except OSError as error:
            # Health is explicitly non-authoritative and never consumed for
            # readiness.  Its failure is visible and cannot revoke a package.
            self._trace("PUBLICATION", "EVIDENCE_FAILED", f"HEALTH_PUBLICATION_FAILED:{type(error).__name__}")

    def _record_failure(self, error: ExecutionPackageError) -> None:
        self._trace(error.owner, "FAILED", error.reason)
        value = {"status": "REJECTED", "execution_uuid": None, "decision_uuid": None,
                 "market_sequence": None, "failure_owner": error.owner,
                 "failure_reason": error.reason, "updated_at": self._timestamp()}
        try:
            self._atomic_write(self.health_path, self._serialize(value))
        except OSError as health_error:
            self._trace("PUBLICATION", "EVIDENCE_FAILED", f"HEALTH_PUBLICATION_FAILED:{type(health_error).__name__}")

    @staticmethod
    def _uuid(value: object, reason: str) -> None:
        try:
            canonical = str(UUID(value)) if type(value) is str else None
        except (ValueError, TypeError, AttributeError):
            canonical = None
        if canonical != value:
            raise ExecutionPackageError("VALIDATION", reason)

    def _timestamp(self) -> str:
        return datetime.fromtimestamp(float(self._clock()), timezone.utc).isoformat().replace("+00:00", "Z")

    @staticmethod
    def _serialize(value: Mapping[str, object]) -> bytes:
        return (json.dumps(value, ensure_ascii=False, allow_nan=False, indent=2) + "\n").encode()

    def _trace(self, owner: str, event: str, reason: str) -> None:
        record = {"timestamp": self._timestamp(), "owner": owner, "event": event, "reason": reason}
        with self.trace_path.open("a", encoding="utf-8") as stream:
            stream.write(json.dumps(record, sort_keys=True) + "\n"); stream.flush(); os.fsync(stream.fileno())

    @staticmethod
    def _atomic_write(path: Path, payload: bytes) -> None:
        temporary = path.with_name(path.name + ".tmp")
        try:
            with temporary.open("wb") as stream:
                stream.write(payload); stream.flush(); os.fsync(stream.fileno())
            os.replace(temporary, path)
            # POSIX directory fsync makes the rename durable.  Platforms that
            # cannot open/fsync a directory retain atomic replacement only.
            if os.name == "posix":
                descriptor = os.open(path.parent, os.O_RDONLY)
                try:
                    os.fsync(descriptor)
                finally:
                    os.close(descriptor)
        finally:
            if temporary.exists():
                temporary.unlink()


def assemble_execution_package(decision_path: Path | str, output_path: Path | str) -> dict[str, object]:
    return ExecutionPackageAssembler(decision_path, output_path).assemble()
