"""Atomically publish validated runtime decisions.

This module owns the ``decision.json`` lifecycle only.  It deliberately does
not evaluate, normalize, or otherwise change the trading decision supplied by
the Writer Adapter.
"""
from __future__ import annotations

from dataclasses import asdict
from datetime import datetime, timezone
import json
from math import isfinite
import os
from pathlib import Path
from typing import Callable

from runtime.writer_adapter import SCHEMA_VERSION as RUNTIME_PAYLOAD_SCHEMA_VERSION
from runtime.writer_adapter import RuntimeDecisionPayload


PUBLISHED_SCHEMA_VERSION = "2.0"
BRAIN_VERSION = "27.4"
RUNTIME_VERSION = "27.5"
# Canonical identity and freshness contract consumed by live publication
# verification.  This module owns decision.json, so observers import rather
# than duplicate these values.
DECISION_PRODUCER = "RP_AI_RUNTIME"
DECISION_HEARTBEAT_MAXIMUM_AGE_SECONDS = 120
GOVERNED_DECISION_LIFECYCLES = frozenset({
    "NORMAL_TRADE", "GOVERNED_NO_TRADE", "STALE_INPUT_FALLBACK",
    "LOGIC_ERROR_REJECTION",
})
_NUMERIC_FIELDS = (
    "confidence", "probability", "expected_value", "location_score",
    "position_budget_total", "position_budget_used", "position_budget_remaining",
    "volume", "entry_price", "stop_loss", "take_profit",
)


class DecisionPublisher:
    """The sole owner of atomic, versioned ``decision.json`` publication."""

    def __init__(self, output_path: Path | str, *, clock: Callable[[], datetime] | None = None) -> None:
        self.output_path = Path(output_path)
        if self.output_path.name != "decision.json":
            raise ValueError("DECISION_OUTPUT_MUST_BE_DECISION_JSON")
        self._clock = clock or (lambda: datetime.now(timezone.utc))
        self._sequence_id = self._existing_sequence_id()

    def publish(self, payload: RuntimeDecisionPayload | object) -> dict[str, object]:
        """Validate and atomically publish one decision, returning its JSON object.

        An invalid adapter payload is replaced by a valid, non-executable
        fail-safe payload.  Filesystem failures are intentionally propagated:
        claiming a publication succeeded when it did not would violate the
        publication contract.
        """
        now = self._utc_now()
        sequence_id = self._next_sequence_id()
        try:
            document = self._document(payload, sequence_id, now)
            serialized = self._serialize(document)
        except Exception as error:
            document = self._fail_safe_document(sequence_id, now, self._failure_reason(error))
            serialized = self._serialize(document)
        self._atomic_write(serialized)
        self._sequence_id = sequence_id
        return document

    def _document(self, payload: RuntimeDecisionPayload | object, sequence_id: int,
                  now: datetime) -> dict[str, object]:
        self._validate_payload(payload)
        source = asdict(payload)
        source["decision_reasons"] = list(source["decision_reasons"])
        source["decision_trace"] = list(source["decision_trace"])
        source.pop("schema_version")
        return {
            "schema_version": PUBLISHED_SCHEMA_VERSION,
            "brain_version": BRAIN_VERSION,
            "runtime_version": RUNTIME_VERSION,
            "sequence_id": sequence_id,
            "heartbeat_unix": int(now.timestamp()),
            "published_at": self._published_at(now),
            **source,
        }

    @staticmethod
    def _validate_payload(payload: object) -> None:
        if type(payload) is not RuntimeDecisionPayload:
            raise ValueError("INVALID_RUNTIME_DECISION_PAYLOAD")
        if payload.schema_version != RUNTIME_PAYLOAD_SCHEMA_VERSION:
            raise ValueError("INVALID_RUNTIME_PAYLOAD_SCHEMA")
        for field in _NUMERIC_FIELDS:
            value = getattr(payload, field)
            if isinstance(value, bool) or not isinstance(value, (int, float)) or not isfinite(value):
                raise ValueError(f"INVALID_{field.upper()}")
        for field in ("decision", "direction", "entry_state", "construction_action"):
            if type(getattr(payload, field)) is not str:
                raise ValueError(f"INVALID_{field.upper()}")
        if type(payload.symbol) is not str:
            raise ValueError("INVALID_SYMBOL")
        if type(payload.entry_permission) is not bool or type(payload.fail_safe) is not bool or type(payload.executable) is not bool:
            raise ValueError("INVALID_BOOLEAN_FIELD")
        for field in ("decision_reasons", "decision_trace"):
            value = getattr(payload, field)
            if type(value) is not tuple or not all(type(item) is str for item in value):
                raise ValueError(f"INVALID_{field.upper()}")
        if payload.executable and (
            payload.fail_safe or not payload.entry_permission
            or payload.decision not in {"BUY", "SELL"} or payload.direction != payload.decision
            or not payload.symbol or payload.volume <= 0
        ):
            raise ValueError("INCONSISTENT_EXECUTABLE_PAYLOAD")
        if payload.fail_safe and (
            payload.decision != "WAIT" or payload.direction != "NONE" or payload.executable
        ):
            raise ValueError("INCONSISTENT_FAIL_SAFE_PAYLOAD")

    def _fail_safe_document(self, sequence_id: int, now: datetime, reason: str) -> dict[str, object]:
        return {
            "schema_version": PUBLISHED_SCHEMA_VERSION,
            "brain_version": BRAIN_VERSION,
            "runtime_version": RUNTIME_VERSION,
            "sequence_id": sequence_id,
            "heartbeat_unix": int(now.timestamp()),
            "published_at": self._published_at(now),
            "decision": "WAIT",
            "direction": "NONE",
            "entry_permission": False,
            "entry_state": "FAIL_SAFE",
            "construction_action": "NO_ACTION",
            "confidence": 0.0,
            "probability": 0.0,
            "expected_value": 0.0,
            "location_score": 0.0,
            "position_budget_total": 0.0,
            "position_budget_used": 0.0,
            "position_budget_remaining": 0.0,
            "decision_reasons": ["DECISION_PUBLICATION_FAIL_SAFE", reason],
            "decision_trace": ["DecisionPublication=FAIL_SAFE", f"FAIL_SAFE={reason}"],
            "fail_safe": True,
            "executable": False,
            "symbol": "",
            "volume": 0.0,
            "entry_price": 0.0,
            "stop_loss": 0.0,
            "take_profit": 0.0,
        }

    @staticmethod
    def _serialize(document: dict[str, object]) -> bytes:
        return (json.dumps(document, allow_nan=False, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode("utf-8")

    def _atomic_write(self, serialized: bytes) -> None:
        self.output_path.parent.mkdir(parents=True, exist_ok=True)
        temporary_path = self.output_path.with_name("decision.tmp")
        with temporary_path.open("wb") as handle:
            handle.write(serialized)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary_path, self.output_path)

    def _existing_sequence_id(self) -> int:
        try:
            parsed = json.loads(self.output_path.read_text(encoding="utf-8"))
            value = parsed.get("sequence_id") if type(parsed) is dict else None
            return value if type(value) is int and value >= 0 else 0
        except (OSError, ValueError, TypeError):
            return 0

    def _next_sequence_id(self) -> int:
        return self._sequence_id + 1

    def _utc_now(self) -> datetime:
        value = self._clock()
        if not isinstance(value, datetime):
            raise ValueError("INVALID_CLOCK")
        return value.astimezone(timezone.utc) if value.tzinfo else value.replace(tzinfo=timezone.utc)

    @staticmethod
    def _published_at(value: datetime) -> str:
        return value.replace(microsecond=0).isoformat().replace("+00:00", "Z")

    @staticmethod
    def _failure_reason(error: Exception) -> str:
        message = str(error)
        return message if message and all(character.isupper() or character == "_" for character in message) else "INVALID_PUBLICATION_PAYLOAD"


def publish_decision(payload: RuntimeDecisionPayload | object, output_path: Path | str) -> dict[str, object]:
    """Publish one payload through a short-lived :class:`DecisionPublisher`."""
    return DecisionPublisher(output_path).publish(payload)
