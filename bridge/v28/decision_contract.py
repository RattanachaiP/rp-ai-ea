"""Backward-compatible executor contract for PR-A HOLD decisions."""
from __future__ import annotations
from datetime import datetime, timezone
from typing import Any
from .runtime_context import RuntimeContext

SCHEMA_VERSION = "2.0"
ACTIONS = frozenset({"BUY", "SELL", "HOLD"})


def build_decision(context: RuntimeContext, action: str = "HOLD", *, now: float) -> dict[str, Any]:
    action = action.upper()
    if action not in ACTIONS:
        raise ValueError("INVALID_DECISION_ACTION")
    # PR-A deliberately has no path that makes BUY/SELL executable.
    executable = False
    direction = action if action in {"BUY", "SELL"} else "NONE"
    return {
        "schema_version": SCHEMA_VERSION,
        "brain_version": "V28.PR-A",
        "runtime_version": context.runtime_version,
        "sequence_id": int(context.market["sequence_id"]),
        "heartbeat_unix": now,
        "published_at": datetime.fromtimestamp(now, timezone.utc).isoformat().replace("+00:00", "Z"),
        "decision": action,
        "direction": direction,
        "entry_permission": False,
        "entry_state": "HOLD",
        "construction_action": "NO_ACTION",
        "confidence": 0.0, "probability": 0.0, "expected_value": 0.0,
        "location_score": 0.0, "position_budget_total": 0.0,
        "position_budget_used": 0.0, "position_budget_remaining": 0.0,
        "decision_reasons": ["V28_PR_A_FOUNDATION_HOLD"],
        "decision_trace": ["MARKET_VALID", "HEARTBEAT_VALID", "FRESHNESS_VALID", "NORMALIZED"],
        "fail_safe": False, "executable": executable,
        "symbol": str(context.market["symbol"]), "volume": 0.0,
        "entry_price": 0.0, "stop_loss": 0.0, "take_profit": 0.0,
    }
