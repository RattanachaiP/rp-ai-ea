"""Pure progressive take-profit / break-even state machine for V29."""
from __future__ import annotations

from typing import Any, Dict


DEFAULT_LADDER = (
    {"name": "TP1", "trigger_r": 1.0, "close_fraction": 0.50, "be_offset_r": 0.0},
    {"name": "TP2", "trigger_r": 2.0, "close_fraction": 0.25, "be_offset_r": 0.50},
    {"name": "TP3", "trigger_r": 3.0, "close_fraction": 0.25, "be_offset_r": 1.00},
)


def management_instruction(unrealized_r: float, completed_levels: list[str] | None = None) -> Dict[str, Any]:
    """Yield idempotent next action; never moves a protective stop backwards."""
    completed = set(completed_levels or [])
    for level in DEFAULT_LADDER:
        if unrealized_r >= level["trigger_r"] and level["name"] not in completed:
            return {"management_action": "PARTIAL_CLOSE_AND_PROTECT", "level": level["name"],
                    "close_fraction": level["close_fraction"], "breakeven_offset_r": level["be_offset_r"],
                    "reason": f"{level['name']}_PROGRESSIVE_TARGET_REACHED"}
    return {"management_action": "HOLD", "level": "NONE", "close_fraction": 0.0,
            "breakeven_offset_r": None, "reason": "NEXT_PROGRESSIVE_TARGET_NOT_REACHED"}


def progressive_contract() -> Dict[str, Any]:
    return {"enabled": True, "risk_unit": "INITIAL_R", "levels": list(DEFAULT_LADDER),
            "stop_rule": "MOVE_ONLY_IN_FAVORABLE_DIRECTION", "final_runner": False}
