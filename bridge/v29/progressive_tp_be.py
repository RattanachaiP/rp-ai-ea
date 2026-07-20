"""AI-owned progressive TP/BE contracts for V29.3.

The executor consumes a validated contract and never derives a ladder from
market data.  ``DEFAULT_LADDER`` is retained exclusively for V29 payloads
that do not contain an adaptive contract.
"""
from __future__ import annotations

from typing import Any, Dict, Iterable


DEFAULT_LADDER = (
    {"name": "TP1", "trigger_r": 1.0, "close_fraction": 0.50, "be_offset_r": 0.0},
    {"name": "TP2", "trigger_r": 2.0, "close_fraction": 0.25, "be_offset_r": 0.50},
    {"name": "TP3", "trigger_r": 3.0, "close_fraction": 0.25, "be_offset_r": 1.00},
)


def _points_to_r(points: float, initial_r_points: float) -> float:
    return round(points / initial_r_points, 6)


def adaptive_contract(
    base_take_profit_points: float,
    base_break_even_points: float,
    initial_r_points: float,
    *,
    trend_strength: float = 0.0,
    volatility: float = 0.0,
    entry_quality: float = 0.0,
) -> Dict[str, Any]:
    """Generate the complete management contract from trader base objectives.

    Inputs are deliberately limited to the two base objectives plus AI market
    telemetry.  The output is self-contained in points so MT5 does not need to
    calculate targets, BE, or locks.
    """
    if base_take_profit_points <= 0 or base_break_even_points < 0 or initial_r_points <= 0:
        raise ValueError("base TP/BE and initial R must be valid point distances")
    # Strong, high-quality trends retain more size for the final target.  This
    # is an AI policy decision, published as data rather than recreated by MT5.
    runner_friendly = trend_strength >= 7.0 and entry_quality >= 70.0 and volatility >= 0.0
    fractions = (0.35, 0.25, 0.40) if runner_friendly else (0.50, 0.25, 0.25)
    targets = (0.60, 1.00, 1.40) if runner_friendly else (0.50, 1.00, 1.50)
    locks = (base_break_even_points, max(base_break_even_points, base_take_profit_points * 0.25),
             max(base_break_even_points, base_take_profit_points * 0.60))
    levels = [
        {
            "name": f"AI_TP{index + 1}",
            "trigger_points": round(base_take_profit_points * target, 6),
            "close_fraction": fraction,
            "lock_points": round(lock, 6),
        }
        for index, (target, fraction, lock) in enumerate(zip(targets, fractions, locks))
    ]
    return {
        "schema_version": "V29_3_ADAPTIVE_TPBE_1",
        "enabled": True,
        "base_take_profit_points": base_take_profit_points,
        "base_break_even_points": base_break_even_points,
        "risk_unit": "POINTS",
        "levels": levels,
        "stop_rule": "MOVE_ONLY_IN_FAVORABLE_DIRECTION",
        "ai_owned": True,
        "generation_inputs": {"trend_strength": trend_strength, "volatility": volatility, "entry_quality": entry_quality},
    }


def management_instruction(unrealized_r: float, completed_levels: list[str] | None = None,
                           contract: Dict[str, Any] | None = None, initial_r_points: float = 100.0) -> Dict[str, Any]:
    """Yield an idempotent next action for an adaptive or legacy contract."""
    completed = set(completed_levels or [])
    levels: Iterable[Dict[str, Any]] = (contract or {}).get("levels", DEFAULT_LADDER)
    for level in levels:
        trigger_r = float(level["trigger_r"]) if "trigger_r" in level else _points_to_r(float(level["trigger_points"]), initial_r_points)
        if unrealized_r >= trigger_r and level["name"] not in completed:
            lock_r = float(level["be_offset_r"]) if "be_offset_r" in level else _points_to_r(float(level.get("lock_points", 0.0)), initial_r_points)
            return {"management_action": "PARTIAL_CLOSE_AND_PROTECT", "level": level["name"],
                    "close_fraction": level["close_fraction"], "breakeven_offset_r": lock_r,
                    "reason": f"{level['name']}_PROGRESSIVE_TARGET_REACHED"}
    return {"management_action": "HOLD", "level": "NONE", "close_fraction": 0.0,
            "breakeven_offset_r": None, "reason": "NEXT_PROGRESSIVE_TARGET_NOT_REACHED"}


def progressive_contract() -> Dict[str, Any]:
    """Legacy V29 deterministic fallback contract."""
    return {"enabled": True, "risk_unit": "INITIAL_R", "levels": list(DEFAULT_LADDER),
            "stop_rule": "MOVE_ONLY_IN_FAVORABLE_DIRECTION", "final_runner": False, "legacy_fallback": True}
