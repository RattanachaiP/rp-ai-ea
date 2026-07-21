"""Translate immutable Brain decisions into safe runtime payload contracts.

This module is deliberately limited to contract validation and normalization.
It does not serialize, publish, execute, or evaluate a trading decision.
"""
from __future__ import annotations

from dataclasses import dataclass
from math import isfinite

from brain.decision_pipeline import DecisionPackage


SCHEMA_VERSION = "V27_RUNTIME_DECISION_PAYLOAD_1"
_DECISIONS = frozenset({"TRADE", "BUY", "SELL", "WAIT", "BLOCK", "HOLD_EXISTING", "NO_ACTION"})
_DIRECTIONS = frozenset({"BUY", "SELL"})
_ENTRY_STATES = frozenset({
    "ENTRY_ALLOWED", "WAIT_PULLBACK", "WAIT_CONFIRMATION", "BLOCK_SWING_EXTREME",
    "BLOCK_ATR_EXTENSION", "BLOCK_POOR_RR", "BLOCK_INVALID_GEOMETRY",
})
_ACTIONS = frozenset({"ALLOW_START", "ALLOW_SCALE", "WAIT_LOCATION", "BLOCK_LOCATION", "HOLD_EXISTING", "NO_ACTION"})
_WAIT_STATES = frozenset({"WAIT_PULLBACK", "WAIT_CONFIRMATION"})
_BLOCK_STATES = frozenset({"BLOCK_SWING_EXTREME", "BLOCK_ATR_EXTENSION", "BLOCK_POOR_RR", "BLOCK_INVALID_GEOMETRY"})
_ALLOW_ACTIONS = frozenset({"ALLOW_START", "ALLOW_SCALE"})
_BUDGET_TOLERANCE = 1e-8


@dataclass(frozen=True)
class RuntimeDecisionPayload:
    """Immutable, JSON-ready data for a future publication owner."""

    schema_version: str
    decision: str
    direction: str
    entry_permission: bool
    entry_state: str
    construction_action: str
    confidence: float
    probability: float
    expected_value: float
    location_score: float
    position_budget_total: float
    position_budget_used: float
    position_budget_remaining: float
    decision_reasons: tuple[str, ...]
    decision_trace: tuple[str, ...]
    fail_safe: bool
    executable: bool


class WriterAdapter:
    """The sole approved DecisionPackage-to-runtime translation boundary."""

    def adapt(self, decision_package: DecisionPackage | None) -> RuntimeDecisionPayload:
        """Return a valid non-executable payload when the input contract is invalid."""
        try:
            return self._adapt_validated(decision_package)
        except Exception as error:  # Boundary containment is required for a future loop.
            return self._fail_safe(self._failure_reason(error))

    def _adapt_validated(self, package: DecisionPackage | None) -> RuntimeDecisionPayload:
        if not isinstance(package, DecisionPackage):
            raise ValueError("MISSING_OR_INVALID_DECISION_PACKAGE")
        decision = self._text(package.decision, "INVALID_DECISION")
        direction = self._text(package.direction, "INVALID_DIRECTION")
        state = self._text(package.entry_state, "UNKNOWN_ENTRY_STATE")
        action = self._text(package.construction_action, "UNKNOWN_CONSTRUCTION_ACTION")
        if decision not in _DECISIONS:
            raise ValueError("INVALID_DECISION")
        if direction not in _DIRECTIONS:
            raise ValueError("INVALID_DIRECTION")
        if state not in _ENTRY_STATES:
            raise ValueError("UNKNOWN_ENTRY_STATE")
        if action not in _ACTIONS:
            raise ValueError("UNKNOWN_CONSTRUCTION_ACTION")
        if not isinstance(package.entry_permission, bool):
            raise ValueError("INVALID_ENTRY_PERMISSION")
        confidence = self._bounded_number(package.confidence, "INVALID_CONFIDENCE", 0.0, 100.0)
        probability = self._bounded_number(package.probability, "INVALID_PROBABILITY", 0.0, 1.0)
        expected_value = self._finite_number(package.expected_value, "INVALID_EXPECTED_VALUE")
        location_score = self._bounded_number(package.location_score, "INVALID_LOCATION_SCORE", 0.0, 100.0)
        total, used, remaining = self._budget(package)
        trace = self._trace(package.decision_trace)
        self._validate_consistency(decision, direction, package.entry_permission, state, action)
        runtime_decision = direction if decision == "TRADE" else decision
        executable = runtime_decision in _DIRECTIONS and package.entry_permission and action in _ALLOW_ACTIONS
        return RuntimeDecisionPayload(
            SCHEMA_VERSION, runtime_decision, direction, package.entry_permission, state, action,
            confidence, probability, expected_value, location_score, total, used, remaining,
            (), trace + ("WriterAdapter=VALID",), False, executable,
        )

    @staticmethod
    def _text(value: object, reason: str) -> str:
        if not isinstance(value, str):
            raise ValueError(reason)
        return value

    @staticmethod
    def _finite_number(value: object, reason: str) -> float:
        if isinstance(value, bool) or not isinstance(value, (int, float)) or not isfinite(value):
            raise ValueError(reason)
        return float(value)

    def _bounded_number(self, value: object, reason: str, lower: float, upper: float) -> float:
        result = self._finite_number(value, reason)
        if not lower <= result <= upper:
            raise ValueError(reason)
        return result

    def _budget(self, package: DecisionPackage) -> tuple[float, float, float]:
        total = self._finite_number(package.position_budget_total, "INVALID_BUDGET")
        used = self._finite_number(package.position_budget_used, "INVALID_BUDGET")
        remaining = self._finite_number(package.position_budget_remaining, "INVALID_BUDGET")
        if min(total, used, remaining) < 0 or used > total or remaining > total:
            raise ValueError("INVALID_BUDGET")
        if abs((used + remaining) - total) > _BUDGET_TOLERANCE:
            raise ValueError("INCONSISTENT_BUDGET")
        return total, used, remaining

    @staticmethod
    def _trace(value: object) -> tuple[str, ...]:
        if not isinstance(value, tuple) or not all(isinstance(item, str) for item in value):
            raise ValueError("MALFORMED_TRACE")
        return value

    @staticmethod
    def _validate_consistency(decision: str, direction: str, permission: bool, state: str, action: str) -> None:
        if decision in {"BUY", "SELL"} and decision != direction:
            raise ValueError("DECISION_DIRECTION_MISMATCH")
        if decision in {"TRADE", "BUY", "SELL"}:
            if not permission or state != "ENTRY_ALLOWED" or action not in _ALLOW_ACTIONS:
                raise ValueError("CONTRADICTORY_ENTRY_PERMISSION")
        if decision == "WAIT" and permission:
            raise ValueError("CONTRADICTORY_WAIT_PERMISSION")
        if state in _WAIT_STATES and (permission or action in _ALLOW_ACTIONS):
            raise ValueError("CONTRADICTORY_WAIT_STATE")
        if state in _BLOCK_STATES and (permission or action in _ALLOW_ACTIONS):
            raise ValueError("CONTRADICTORY_BLOCK_STATE")
        if action in _ALLOW_ACTIONS and (not permission or state != "ENTRY_ALLOWED"):
            raise ValueError("CONTRADICTORY_CONSTRUCTION_ACTION")
        if action == "BLOCK_LOCATION" and permission:
            raise ValueError("CONTRADICTORY_CONSTRUCTION_ACTION")
        if decision == "BLOCK" and (permission or action in _ALLOW_ACTIONS):
            raise ValueError("CONTRADICTORY_BLOCK_DECISION")
        if decision in {"HOLD_EXISTING", "NO_ACTION"} and (permission or action in _ALLOW_ACTIONS):
            raise ValueError("CONTRADICTORY_NON_EXECUTABLE_DECISION")

    @staticmethod
    def _failure_reason(error: Exception) -> str:
        message = str(error)
        return message if message and all(character.isupper() or character == "_" for character in message) else "UNEXPECTED_ADAPTER_ERROR"

    @staticmethod
    def _fail_safe(reason: str) -> RuntimeDecisionPayload:
        return RuntimeDecisionPayload(
            SCHEMA_VERSION, "WAIT", "NONE", False, "FAIL_SAFE", "NO_ACTION",
            0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0,
            ("WRITER_ADAPTER_FAIL_SAFE", reason),
            ("WriterAdapter=FAIL_SAFE", f"FAIL_SAFE={reason}"), True, False,
        )


def adapt_decision_package(decision_package: DecisionPackage | None) -> RuntimeDecisionPayload:
    """Convenience entry point for the explicit translation boundary."""
    return WriterAdapter().adapt(decision_package)
