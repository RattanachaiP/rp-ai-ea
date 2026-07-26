"""PR192 canonical, immutable Runtime-to-Executor execution contract.

This module is deliberately independent of every governance package.  The wire
payload is the only object an executor is permitted to consume.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime
from hashlib import sha256
import json
from math import isfinite
from typing import Any, Mapping
from uuid import UUID


CONTRACT_VERSION = "PR192-EXECUTION-CONTEXT.1"
REQUIRED_FIELDS = frozenset({
    "execution_uuid", "decision_uuid", "package_uuid", "replay_uuid",
    "execution_confidence", "readiness_state", "environment_state",
    "feasibility_state", "policy_version", "engine_version", "advisory_only",
    "timestamp", "contract_version", "payload_digest",
})


class ExecutionContractError(ValueError):
    """A fail-closed execution-contract validation failure."""


def _canonical_bytes(value: Mapping[str, Any]) -> bytes:
    try:
        return json.dumps(value, sort_keys=True, separators=(",", ":"),
                          ensure_ascii=False, allow_nan=False).encode("utf-8")
    except (TypeError, ValueError, OverflowError) as exc:
        raise ExecutionContractError("SERIALIZATION_FAILURE") from exc


def _valid_uuid(value: object) -> bool:
    try:
        return isinstance(value, str) and str(UUID(value)) == value
    except (AttributeError, TypeError, ValueError):
        return False


def _valid_timestamp(value: object) -> bool:
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        return isinstance(value, str) and parsed.tzinfo is not None
    except (TypeError, ValueError):
        return False


def _digest(payload: Mapping[str, Any]) -> str:
    return sha256(_canonical_bytes(payload)).hexdigest()


@dataclass(frozen=True, slots=True)
class ExecutionContext:
    """The complete and only immutable payload exposed to an MT5 executor."""

    execution_uuid: str
    decision_uuid: str
    package_uuid: str
    replay_uuid: str
    execution_confidence: float
    readiness_state: str
    environment_state: str
    feasibility_state: str
    policy_version: str
    engine_version: str
    advisory_only: bool
    timestamp: str
    contract_version: str
    payload_digest: str

    def __post_init__(self) -> None:
        uuids = (self.execution_uuid, self.decision_uuid, self.package_uuid, self.replay_uuid)
        strings = (self.readiness_state, self.environment_state, self.feasibility_state,
                   self.policy_version, self.engine_version)
        confidence = self.execution_confidence
        if not all(_valid_uuid(value) for value in uuids):
            raise ExecutionContractError("INVALID_UUID")
        if (type(confidence) not in (int, float) or isinstance(confidence, bool)
                or not isfinite(confidence) or not 0.0 <= confidence <= 1.0):
            raise ExecutionContractError("INVALID_EXECUTION_CONFIDENCE")
        if not all(isinstance(value, str) and value.strip() == value and value for value in strings):
            raise ExecutionContractError("INVALID_EXECUTION_METADATA")
        if self.advisory_only is not True:
            raise ExecutionContractError("INVALID_ADVISORY_STATE")
        if not _valid_timestamp(self.timestamp):
            raise ExecutionContractError("INVALID_TIMESTAMP")
        if self.contract_version != CONTRACT_VERSION:
            raise ExecutionContractError("CONTRACT_VERSION_MISMATCH")
        if (not isinstance(self.payload_digest, str) or len(self.payload_digest) != 64
                or any(character not in "0123456789abcdef" for character in self.payload_digest)):
            raise ExecutionContractError("CORRUPTED_PAYLOAD")
        if _digest(self.unsigned_payload()) != self.payload_digest:
            raise ExecutionContractError("CORRUPTED_PAYLOAD")

    def unsigned_payload(self) -> dict[str, Any]:
        """Return a fresh wire mapping excluding its integrity digest."""
        return {key: value for key, value in asdict(self).items() if key != "payload_digest"}

    def to_dict(self) -> dict[str, Any]:
        """Return a fresh mapping; mutation cannot alter this context."""
        return asdict(self)

    @classmethod
    def create(cls, **values: Any) -> "ExecutionContext":
        """Create a context and bind every field to its SHA-256 digest."""
        if set(values) != REQUIRED_FIELDS - {"payload_digest"}:
            raise ExecutionContractError("INVALID_FIELD_SET")
        return cls(payload_digest=_digest(values), **values)


def serialize_execution_context(context: ExecutionContext) -> bytes:
    """Serialize exactly one validated context to canonical UTF-8 JSON."""
    if type(context) is not ExecutionContext:
        raise ExecutionContractError("INVALID_EXECUTION_CONTEXT")
    # Reconstruction prevents a forged/subclassed or post-construction object.
    verified = ExecutionContext(**context.to_dict())
    return _canonical_bytes(verified.to_dict())


def deserialize_execution_context(payload: bytes | str, *, expected_engine_version: str,
                                  expected_replay_uuid: str) -> ExecutionContext:
    """Strictly load a canonical payload with explicit compatibility bindings."""
    if type(payload) not in (bytes, str):
        raise ExecutionContractError("DESERIALIZATION_FAILURE")
    if not isinstance(expected_engine_version, str) or not expected_engine_version:
        raise ExecutionContractError("ENGINE_VERSION_MISMATCH")
    if not _valid_uuid(expected_replay_uuid):
        raise ExecutionContractError("REPLAY_MISMATCH")
    try:
        wire = payload.encode("utf-8") if isinstance(payload, str) else payload
        raw = json.loads(wire.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError, AttributeError) as exc:
        raise ExecutionContractError("DESERIALIZATION_FAILURE") from exc
    if not isinstance(raw, dict) or set(raw) != REQUIRED_FIELDS:
        raise ExecutionContractError("INVALID_FIELD_SET")
    if _canonical_bytes(raw) != wire:
        raise ExecutionContractError("NON_CANONICAL_PAYLOAD")
    context = ExecutionContext(**raw)
    if context.engine_version != expected_engine_version:
        raise ExecutionContractError("ENGINE_VERSION_MISMATCH")
    if context.replay_uuid != expected_replay_uuid:
        raise ExecutionContractError("REPLAY_MISMATCH")
    return context
