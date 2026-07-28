"""Backward-compatible, HOLD-only executor contract for V28 PR-A."""
from __future__ import annotations
from datetime import datetime, timezone
from math import isfinite
from typing import Any, Mapping
from .runtime_context import RuntimeContext

SCHEMA_VERSION = "2.0"
FIELDS = frozenset({"schema_version", "brain_version", "runtime_version", "sequence_id", "heartbeat_unix",
"published_at", "decision", "direction", "entry_permission", "entry_state", "construction_action", "confidence",
"probability", "expected_value", "location_score", "position_budget_total", "position_budget_used",
"position_budget_remaining", "decision_reasons", "decision_trace", "fail_safe", "executable", "symbol", "volume",
"entry_price", "stop_loss", "take_profit"})


def build_decision(context: RuntimeContext, *, now: float) -> dict[str, Any]:
    """Build the sole PR-A outcome; there is deliberately no action input."""
    decision = {
        "schema_version": SCHEMA_VERSION, "brain_version": "V28.PR-A", "runtime_version": context.runtime_version,
        "sequence_id": int(context.market["sequence_id"]),
        # Executor compatibility: heartbeat remains the source Writer heartbeat; published_at is decision time.
        "heartbeat_unix": context.source_heartbeat_unix,
        "published_at": datetime.fromtimestamp(now, timezone.utc).isoformat().replace("+00:00", "Z"),
        "decision": "HOLD", "direction": "NONE", "entry_permission": False, "entry_state": "HOLD",
        "construction_action": "NO_ACTION", "confidence": 0.0, "probability": 0.0, "expected_value": 0.0,
        "location_score": 0.0, "position_budget_total": 0.0, "position_budget_used": 0.0,
        "position_budget_remaining": 0.0, "decision_reasons": ["V28_PR_A_FOUNDATION_HOLD"],
        "decision_trace": ["MARKET_VALID", "HEARTBEAT_VALID", "FRESHNESS_VALID", "NORMALIZED"],
        # Existing Executor semantics reserve fail_safe=true for its WAIT/FAIL_SAFE envelope. This governed HOLD
        # is non-executable but schema-valid, so false avoids violating the unchanged Executor contract.
        "fail_safe": False, "executable": False, "symbol": str(context.market["symbol"]), "volume": 0.0,
        "entry_price": 0.0, "stop_loss": 0.0, "take_profit": 0.0,
    }
    validate_pr_a_decision(decision)
    return decision


def validate_pr_a_decision(value: object) -> None:
    """Deterministic complete validator used at construction and publication."""
    if type(value) is not dict or set(value) != FIELDS:
        raise ValueError("DECISION_SCHEMA_FIELDS")
    consts = {"schema_version": "2.0", "brain_version": "V28.PR-A", "runtime_version": "V28.PR-A",
              "decision": "HOLD", "direction": "NONE", "entry_permission": False, "entry_state": "HOLD",
              "construction_action": "NO_ACTION", "fail_safe": False, "executable": False, "volume": 0.0,
              "entry_price": 0.0, "stop_loss": 0.0, "take_profit": 0.0, "confidence": 0.0,
              "probability": 0.0, "expected_value": 0.0, "location_score": 0.0,
              "position_budget_total": 0.0, "position_budget_used": 0.0, "position_budget_remaining": 0.0}
    if any(value[key] != expected or type(value[key]) is not type(expected) for key, expected in consts.items()):
        raise ValueError("DECISION_SCHEMA_CONST")
    if type(value["sequence_id"]) is not int or value["sequence_id"] < 0:
        raise ValueError("DECISION_SCHEMA_SEQUENCE")
    numeric = ("heartbeat_unix", "confidence", "probability", "expected_value", "location_score",
               "position_budget_total", "position_budget_used", "position_budget_remaining")
    if any(type(value[key]) not in (int, float) or not isfinite(value[key]) for key in numeric):
        raise ValueError("DECISION_SCHEMA_NUMBER")
    if value["heartbeat_unix"] <= 0 or type(value["symbol"]) is not str or not value["symbol"]:
        raise ValueError("DECISION_SCHEMA_VALUE")
    if not isinstance(value["published_at"], str) or not value["published_at"].endswith("Z"):
        raise ValueError("DECISION_SCHEMA_TIMESTAMP")
    try:
        parsed_timestamp = datetime.fromisoformat(value["published_at"].replace("Z", "+00:00"))
    except ValueError as error:
        raise ValueError("DECISION_SCHEMA_TIMESTAMP") from error
    if parsed_timestamp.tzinfo is None:
        raise ValueError("DECISION_SCHEMA_TIMESTAMP")
    for key in ("decision_reasons", "decision_trace"):
        if type(value[key]) is not list or not all(type(item) is str for item in value[key]):
            raise ValueError("DECISION_SCHEMA_ARRAY")
