"""Runtime validation bridge between published decisions and the executor.

This module consumes the versioned ``decision.json`` document emitted by
:mod:`runtime.decision_publication`.  It never evaluates market data or creates,
changes, or upgrades a trading intent.
"""
from __future__ import annotations

from dataclasses import dataclass
from types import MappingProxyType
import json
from math import isfinite
from pathlib import Path
import time
from typing import Any, Callable, Mapping


PUBLISHED_SCHEMA_VERSION = "2.0"
_DEFAULT_HEARTBEAT_MAX_AGE_SECONDS = 30.0
_DEFAULT_ALLOWED_FUTURE_SKEW_SECONDS = 2.0
_REQUIRED_FIELDS = frozenset({
    "schema_version", "brain_version", "runtime_version", "sequence_id", "heartbeat_unix", "published_at",
    "decision", "direction", "entry_permission", "entry_state", "construction_action", "confidence",
    "probability", "expected_value", "location_score", "position_budget_total", "position_budget_used",
    "position_budget_remaining", "decision_reasons", "decision_trace", "fail_safe", "executable",
    "symbol", "volume", "entry_price", "stop_loss", "take_profit",
})


@dataclass(frozen=True)
class WriterReadResult:
    """The executor-facing result of one read attempt."""

    payload: Mapping[str, Any]
    accepted: bool
    ignored_duplicate: bool
    reason: str | None

    def __post_init__(self) -> None:
        """Freeze the accepted document before it crosses into execution.

        A writer result is a cycle snapshot, not a handle back to the JSON
        file.  Freezing it here makes accidental mutation by any consumer
        immediately visible instead of silently changing the instruction.
        """
        object.__setattr__(self, "payload", _freeze_mapping(self.payload))

    @property
    def legacy_payload(self) -> dict[str, Any]:
        """Provide direct-name compatibility fields without reinterpreting intent."""
        return map_legacy_runtime_decision(self.payload)


class DecisionWriter:
    """Read and validate published runtime decisions in publication order."""

    def __init__(self, decision_path: Path | str, *, heartbeat_max_age_seconds: float = _DEFAULT_HEARTBEAT_MAX_AGE_SECONDS,
                 allowed_future_skew_seconds: float = _DEFAULT_ALLOWED_FUTURE_SKEW_SECONDS,
                 clock: Callable[[], float] | None = None) -> None:
        self.decision_path = Path(decision_path)
        self.heartbeat_max_age_seconds = self._non_negative_finite_config(
            heartbeat_max_age_seconds, "HEARTBEAT_MAX_AGE_MUST_BE_NON_NEGATIVE"
        )
        self.allowed_future_skew_seconds = self._non_negative_finite_config(
            allowed_future_skew_seconds, "FUTURE_SKEW_MUST_BE_NON_NEGATIVE"
        )
        self._clock = clock or time.time
        self._most_recent_sequence_id: int | None = None

    def read(self) -> WriterReadResult:
        """Return an accepted publication, or a non-executable safe result.

        Validation stages intentionally remain discrete so an operator can
        identify whether JSON, schema, sequence, heartbeat, or executable
        contract validation rejected the publication.
        """
        try:
            document = self._read_json()
            self._validate_schema(document)
            sequence_state = self._validate_sequence(document)
            if sequence_state == "DUPLICATE":
                return WriterReadResult(self._safe_payload("DUPLICATE_SEQUENCE"), False, True, "DUPLICATE_SEQUENCE")
            self._validate_heartbeat(document)
            self._validate_executable_contract(document)
            self._most_recent_sequence_id = document["sequence_id"]
        except _ValidationError as error:
            return WriterReadResult(self._safe_payload(error.reason), False, False, error.reason)
        return WriterReadResult(dict(document), True, False, None)

    def _read_json(self) -> dict[str, Any]:
        try:
            document = json.loads(self.decision_path.read_text(encoding="utf-8"))
        except (OSError, UnicodeDecodeError, json.JSONDecodeError) as error:
            raise _ValidationError("MALFORMED_JSON") from error
        if type(document) is not dict:
            raise _ValidationError("UNKNOWN_PAYLOAD_STRUCTURE")
        return document

    @staticmethod
    def _validate_schema(document: Mapping[str, Any]) -> None:
        if set(document) != _REQUIRED_FIELDS:
            raise _ValidationError("UNKNOWN_PAYLOAD_STRUCTURE")
        if document.get("schema_version") != PUBLISHED_SCHEMA_VERSION:
            raise _ValidationError("UNSUPPORTED_SCHEMA_VERSION")
        strings = ("brain_version", "runtime_version", "published_at", "decision", "direction", "entry_state", "construction_action")
        if any(type(document[field]) is not str for field in strings):
            raise _ValidationError("MALFORMED_RUNTIME_FIELDS")
        booleans = ("entry_permission", "fail_safe", "executable")
        if any(type(document[field]) is not bool for field in booleans):
            raise _ValidationError("MALFORMED_RUNTIME_FIELDS")
        if type(document["sequence_id"]) is not int or document["sequence_id"] < 0:
            raise _ValidationError("MALFORMED_SEQUENCE")
        heartbeat = document["heartbeat_unix"]
        if type(heartbeat) not in (int, float) or not isfinite(heartbeat):
            raise _ValidationError("MALFORMED_HEARTBEAT")
        numeric_fields = ("confidence", "probability", "expected_value", "location_score", "position_budget_total",
                          "position_budget_used", "position_budget_remaining", "volume", "entry_price", "stop_loss", "take_profit")
        if any(type(document[field]) not in (int, float) or not isfinite(document[field]) for field in numeric_fields):
            raise _ValidationError("MALFORMED_RUNTIME_FIELDS")
        if type(document["symbol"]) is not str:
            raise _ValidationError("MALFORMED_RUNTIME_FIELDS")
        for field in ("decision_reasons", "decision_trace"):
            if type(document[field]) is not list or not all(type(item) is str for item in document[field]):
                raise _ValidationError("MALFORMED_RUNTIME_FIELDS")

    def _validate_sequence(self, document: Mapping[str, Any]) -> str:
        sequence_id = document["sequence_id"]
        if self._most_recent_sequence_id is not None:
            if sequence_id == self._most_recent_sequence_id:
                return "DUPLICATE"
            if sequence_id < self._most_recent_sequence_id:
                raise _ValidationError("STALE_SEQUENCE")
        return "ACCEPT"

    def _validate_heartbeat(self, document: Mapping[str, Any]) -> None:
        try:
            now = self._clock()
        except Exception as error:
            raise _ValidationError("INVALID_CLOCK") from error
        if type(now) not in (int, float) or not isfinite(now):
            raise _ValidationError("INVALID_CLOCK")
        age = now - document["heartbeat_unix"]
        if age > self.heartbeat_max_age_seconds:
            raise _ValidationError("STALE_HEARTBEAT")
        if age < -self.allowed_future_skew_seconds:
            raise _ValidationError("FUTURE_HEARTBEAT")

    @staticmethod
    def _validate_executable_contract(document: Mapping[str, Any]) -> None:
        # This only checks internal publisher contract consistency; it never
        # derives a decision or changes intent from analytical fields.
        if document["fail_safe"] and any((
            document["decision"] != "WAIT", document["direction"] != "NONE",
            document["entry_permission"] is not False, document["executable"] is not False,
            document["entry_state"] != "FAIL_SAFE", document["construction_action"] != "NO_ACTION",
        )):
            raise _ValidationError("INCONSISTENT_FAIL_SAFE_CONTRACT")
        if document["executable"] and any((
            document["decision"] not in {"BUY", "SELL"},
            document["direction"] != document["decision"], document["entry_permission"] is not True,
            document["fail_safe"] is not False, document["entry_state"] != "ENTRY_ALLOWED",
            document["construction_action"] not in {"ALLOW_START", "ALLOW_SCALE"},
            not document["symbol"], document["volume"] <= 0,
        )):
            raise _ValidationError("INCONSISTENT_EXECUTABLE_CONTRACT")

    @staticmethod
    def _non_negative_finite_config(value: object, reason: str) -> float:
        if type(value) not in (int, float) or not isfinite(value) or value < 0:
            raise ValueError(reason)
        return float(value)

    @staticmethod
    def _safe_payload(reason: str) -> dict[str, Any]:
        return {"decision": "WAIT", "direction": "NONE", "entry_permission": False,
                "entry_state": "FAIL_SAFE", "construction_action": "NO_ACTION", "fail_safe": True,
                "executable": False, "symbol": "", "volume": 0.0, "entry_price": 0.0,
                "stop_loss": 0.0, "take_profit": 0.0,
                "decision_reasons": ["WRITER_FAIL_SAFE", reason], "decision_trace": []}


class _ValidationError(Exception):
    def __init__(self, reason: str) -> None:
        self.reason = reason
        super().__init__(reason)


def map_legacy_runtime_decision(payload: Mapping[str, Any]) -> dict[str, Any]:
    """Map direct runtime fields to legacy names; preserve the decision verbatim."""
    return {
        "decision": payload["decision"], "bias": payload["direction"],
        "allowed": payload["entry_permission"], "executable": payload["executable"],
        "fail_safe": payload["fail_safe"], "confidence": payload.get("confidence", 0.0),
        "sequence_id": payload.get("sequence_id"), "heartbeat_unix": payload.get("heartbeat_unix"),
    }


def _freeze_mapping(value: Mapping[str, Any]) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise TypeError("WRITER_RESULT_PAYLOAD_MUST_BE_MAPPING")
    return MappingProxyType({key: _freeze_value(item) for key, item in value.items()})


def _freeze_value(value: Any) -> Any:
    if isinstance(value, Mapping):
        return _freeze_mapping(value)
    if isinstance(value, list):
        return tuple(_freeze_value(item) for item in value)
    if isinstance(value, tuple):
        return tuple(_freeze_value(item) for item in value)
    return value
