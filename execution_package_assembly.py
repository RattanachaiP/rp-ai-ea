"""Governed assembly boundary from ``decision.json`` to the MT5 package.

The assembler copies execution facts; it has no authority to calculate or
modify strategy, risk, or management values.
"""
from __future__ import annotations

from datetime import datetime, timezone
import json
from math import isfinite
import os
from pathlib import Path
from typing import Callable, Mapping
from uuid import UUID, uuid4


EXECUTION_SCHEMA_VERSION = "1.0"
DECISION_SCHEMA_VERSION = "2.0"
DECISION_PRODUCER = "RP_AI_RUNTIME"
MAX_HEARTBEAT_AGE_SECONDS = 120
FAILURE_OWNERS = frozenset({"ASSEMBLY", "VALIDATION", "PUBLICATION"})
PACKAGE_FIELDS = (
    "execution_uuid", "decision_uuid", "market_sequence", "heartbeat_unix",
    "producer", "producer_version", "schema_version", "source_uuid", "symbol",
    "direction", "confidence", "risk_profile", "lot_size", "entry", "sl", "tp",
    "management_profile", "execution_timestamp",
)


class ExecutionPackageError(ValueError):
    """A fail-closed package failure with an accountable owner and reason."""

    def __init__(self, owner: str, reason: str) -> None:
        if owner not in FAILURE_OWNERS:
            raise ValueError("INVALID_FAILURE_OWNER")
        super().__init__(reason)
        self.owner = owner
        self.reason = reason


class ExecutionPackageAssembler:
    """Verify, construct, validate, and atomically publish one package."""

    def __init__(self, decision_path: Path | str, output_path: Path | str,
                 *, clock: Callable[[], float] | None = None,
                 uuid_factory: Callable[[], object] | None = None) -> None:
        self.decision_path = Path(decision_path)
        self.output_path = Path(output_path)
        if self.decision_path.name != "decision.json":
            raise ValueError("INPUT_MUST_BE_DECISION_JSON")
        if self.output_path.name != "execution_package.json":
            raise ValueError("OUTPUT_MUST_BE_EXECUTION_PACKAGE_JSON")
        self.root = self.output_path.parent
        self.trace_path = self.root / "execution_package_trace.log"
        self.health_path = self.root / "execution_package_health.json"
        self._clock = clock or __import__("time").time
        self._uuid_factory = uuid_factory or uuid4

    def assemble(self) -> dict[str, object]:
        """Publish a package, or persist exact failure ownership and re-raise."""
        self.root.mkdir(parents=True, exist_ok=True)
        try:
            decision = self._read_and_verify()
            self._trace("ASSEMBLY", "ACCEPTED", "verified decision accepted")
            package = self._construct(decision)
            self._trace("ASSEMBLY", "ASSEMBLED", "execution package constructed")
            self._validate(package, decision)
            self._trace("VALIDATION", "VALID", "schema and lineage verified")
            try:
                self._atomic_write(self.output_path, self._serialize(package))
            except OSError as error:
                raise ExecutionPackageError("PUBLICATION", "ATOMIC_PUBLICATION_FAILED") from error
            self._trace("PUBLICATION", "PUBLISHED", "atomic replacement complete")
            self._write_health("VERIFIED", package, None, None)
            return package
        except ExecutionPackageError as error:
            self._trace(error.owner, "FAILED", error.reason)
            self._write_health("REJECTED", None, error.owner, error.reason)
            raise
        except (OSError, json.JSONDecodeError, TypeError) as error:
            governed = ExecutionPackageError("ASSEMBLY", "DECISION_PUBLICATION_UNREADABLE")
            self._trace(governed.owner, "FAILED", governed.reason)
            self._write_health("REJECTED", None, governed.owner, governed.reason)
            raise governed from error

    def _read_and_verify(self) -> dict[str, object]:
        raw = self.decision_path.read_bytes()
        value = json.loads(raw)
        if type(value) is not dict:
            raise ExecutionPackageError("VALIDATION", "INVALID_DECISION_SCHEMA")
        required = {
            "decision_uuid", "market_state_sequence_id", "heartbeat_unix", "producer",
            "producer_version", "schema_version", "market_state_source_uuid", "symbol",
            "direction", "confidence", "active_profile", "volume", "entry_price",
            "stop_loss", "take_profit", "management_profile", "decision_timestamp",
        }
        missing = sorted(required.difference(value))
        if missing:
            raise ExecutionPackageError("VALIDATION", f"MISSING_DECISION_FIELD_{missing[0].upper()}")
        if value["producer"] != DECISION_PRODUCER:
            raise ExecutionPackageError("VALIDATION", "MISSING_OR_INVALID_PRODUCER")
        if value["schema_version"] != DECISION_SCHEMA_VERSION:
            raise ExecutionPackageError("VALIDATION", "INVALID_DECISION_SCHEMA")
        self._uuid(value["decision_uuid"], "INVALID_DECISION_UUID")
        self._uuid(value["market_state_source_uuid"], "INVALID_SOURCE_UUID")
        heartbeat = value["heartbeat_unix"]
        if type(heartbeat) is not int or heartbeat <= 0 or abs(float(self._clock()) - heartbeat) > MAX_HEARTBEAT_AGE_SECONDS:
            raise ExecutionPackageError("VALIDATION", "STALE_HEARTBEAT")
        sequence = value["market_state_sequence_id"]
        if type(sequence) is not int or sequence < 1:
            raise ExecutionPackageError("VALIDATION", "INVALID_MARKET_SEQUENCE")
        previous = self._existing_package()
        if previous is not None and sequence <= previous.get("market_sequence", -1):
            raise ExecutionPackageError("VALIDATION", "NON_MONOTONIC_SEQUENCE")
        return value

    def _construct(self, decision: Mapping[str, object]) -> dict[str, object]:
        timestamp = datetime.fromtimestamp(float(self._clock()), timezone.utc).replace(microsecond=0)
        return {
            "execution_uuid": str(self._uuid_factory()),
            "decision_uuid": decision["decision_uuid"],
            "market_sequence": decision["market_state_sequence_id"],
            "heartbeat_unix": decision["heartbeat_unix"],
            "producer": decision["producer"],
            "producer_version": decision["producer_version"],
            "schema_version": EXECUTION_SCHEMA_VERSION,
            "source_uuid": decision["market_state_source_uuid"],
            "symbol": decision["symbol"], "direction": decision["direction"],
            "confidence": decision["confidence"], "risk_profile": decision["active_profile"],
            "lot_size": decision["volume"], "entry": decision["entry_price"],
            "sl": decision["stop_loss"], "tp": decision["take_profit"],
            "management_profile": decision["management_profile"],
            "execution_timestamp": timestamp.isoformat().replace("+00:00", "Z"),
        }

    def _validate(self, package: Mapping[str, object], decision: Mapping[str, object]) -> None:
        if tuple(package) != PACKAGE_FIELDS:
            raise ExecutionPackageError("VALIDATION", "INVALID_EXECUTION_SCHEMA")
        self._uuid(package["execution_uuid"], "INVALID_EXECUTION_UUID")
        self._uuid(package["decision_uuid"], "INVALID_DECISION_UUID")
        self._uuid(package["source_uuid"], "INVALID_SOURCE_UUID")
        if package["schema_version"] != EXECUTION_SCHEMA_VERSION:
            raise ExecutionPackageError("VALIDATION", "INVALID_EXECUTION_SCHEMA")
        if (package["decision_uuid"] != decision["decision_uuid"] or
                package["source_uuid"] != decision["market_state_source_uuid"] or
                package["market_sequence"] != decision["market_state_sequence_id"]):
            raise ExecutionPackageError("VALIDATION", "INVALID_LINEAGE")
        for field in ("confidence", "lot_size", "entry", "sl", "tp"):
            value = package[field]
            if type(value) not in (int, float) or not isfinite(value):
                raise ExecutionPackageError("VALIDATION", f"INVALID_{field.upper()}")
        if package["direction"] not in {"BUY", "SELL"} or package["lot_size"] <= 0:
            raise ExecutionPackageError("VALIDATION", "INVALID_EXECUTION_FIELDS")
        for field in ("producer", "producer_version", "symbol", "risk_profile",
                      "management_profile", "execution_timestamp"):
            if type(package[field]) is not str or not package[field]:
                raise ExecutionPackageError("VALIDATION", f"MISSING_{field.upper()}")

    def _existing_package(self) -> dict[str, object] | None:
        try:
            value = json.loads(self.output_path.read_text(encoding="utf-8"))
            return value if type(value) is dict else None
        except FileNotFoundError:
            return None
        except (OSError, json.JSONDecodeError) as error:
            raise ExecutionPackageError("VALIDATION", "INVALID_EXISTING_PACKAGE") from error

    @staticmethod
    def _uuid(value: object, reason: str) -> None:
        try:
            canonical = str(UUID(value)) if type(value) is str else None
        except (ValueError, TypeError, AttributeError):
            canonical = None
        if canonical != value:
            raise ExecutionPackageError("VALIDATION", reason)

    @staticmethod
    def _serialize(value: Mapping[str, object]) -> bytes:
        return (json.dumps(value, ensure_ascii=False, allow_nan=False, indent=2) + "\n").encode()

    def _trace(self, owner: str, event: str, reason: str) -> None:
        record = {"timestamp": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
                  "owner": owner, "event": event, "reason": reason}
        with self.trace_path.open("a", encoding="utf-8") as stream:
            stream.write(json.dumps(record, sort_keys=True) + "\n"); stream.flush(); os.fsync(stream.fileno())

    def _write_health(self, status: str, package: Mapping[str, object] | None,
                      owner: str | None, reason: str | None) -> None:
        value = {"status": status, "executor_ready": status == "VERIFIED",
                 "execution_uuid": package.get("execution_uuid") if package else None,
                 "decision_uuid": package.get("decision_uuid") if package else None,
                 "market_sequence": package.get("market_sequence") if package else None,
                 "failure_owner": owner, "failure_reason": reason,
                 "updated_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")}
        try:
            self._atomic_write(self.health_path, self._serialize(value))
        except OSError:
            # The original accountable failure remains authoritative.
            pass

    @staticmethod
    def _atomic_write(path: Path, payload: bytes) -> None:
        temporary = path.with_name(path.name + ".tmp")
        try:
            with temporary.open("wb") as stream:
                stream.write(payload); stream.flush(); os.fsync(stream.fileno())
            os.replace(temporary, path)
        finally:
            if temporary.exists():
                temporary.unlink()


def assemble_execution_package(decision_path: Path | str,
                               output_path: Path | str) -> dict[str, object]:
    """Convenience entry point for one governed assembly."""
    return ExecutionPackageAssembler(decision_path, output_path).assemble()
