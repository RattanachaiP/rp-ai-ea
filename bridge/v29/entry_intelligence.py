"""Deterministic, auditable AI entry-intelligence contract for V29.

This module deliberately owns only pre-entry setup qualification.  It does not
resize positions, manage exits, add cooldowns, or change any V28/V27 path.
"""
from __future__ import annotations

from typing import Any, Dict


REQUIRED_CONFIRMATIONS = ("structure", "momentum", "location")


def _number(market: Dict[str, Any], name: str, default: float = 0.0) -> float:
    try:
        return float(market.get(name, default))
    except (TypeError, ValueError):
        return default


def assess_entry(market: Dict[str, Any]) -> Dict[str, Any]:
    """Return a single candidate and explainable three-confirmation result.

    Existing upstream BUY/SELL scores nominate direction.  V29 adds no score
    tuning: it verifies that the nominated direction has aligned structure,
    momentum, and a non-exhausted location before permitting the entry.
    """
    buy_score, sell_score = _number(market, "buy_score"), _number(market, "sell_score")
    if buy_score == sell_score:
        return {"entry_intelligence_status": "NO_DIRECTION", "candidate_direction": "NONE",
                "entry_allowed": False, "entry_intelligence_reason": "NO_DIRECTIONAL_EDGE"}
    direction = "BUY" if buy_score > sell_score else "SELL"
    structure = str(market.get("structure_trend", market.get("market_structure", ""))).upper()
    bb_state = str(market.get("bb_state", "")).upper()
    rsi, macd = _number(market, "rsi", 50), _number(market, "macd_histogram")
    expected_structure = "UP" if direction == "BUY" else "DOWN"
    structure_ok = expected_structure in structure or (direction == "BUY" and bb_state == "WALK_UP") or (direction == "SELL" and bb_state == "WALK_DOWN")
    momentum_ok = (direction == "BUY" and macd > 0 and rsi >= 50) or (direction == "SELL" and macd < 0 and rsi <= 50)
    exhausted = (direction == "BUY" and rsi >= 75) or (direction == "SELL" and rsi <= 25)
    location_ok = not exhausted and bb_state not in {"EXTREME_UP", "EXTREME_DOWN"}
    confirmations = {"structure": structure_ok, "momentum": momentum_ok, "location": location_ok}
    failed = [name.upper() for name in REQUIRED_CONFIRMATIONS if not confirmations[name]]
    return {
        "entry_intelligence_status": "ENTRY_CONFIRMED" if not failed else "ENTRY_REJECTED",
        "candidate_direction": direction,
        "entry_allowed": not failed,
        "entry_intelligence_reason": "THREE_CONFIRMATIONS_ALIGNED" if not failed else "ENTRY_" + "_AND_".join(failed) + "_NOT_CONFIRMED",
        "entry_confirmations": confirmations,
        "entry_evidence": {"structure_trend": structure, "bb_state": bb_state, "rsi": rsi, "macd_histogram": macd},
    }
