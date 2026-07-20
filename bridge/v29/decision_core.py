"""V29 shadow decision producer joining the two approved scopes only."""
from __future__ import annotations

import time
from typing import Any, Dict

from .entry_intelligence import assess_entry
from .progressive_tp_be import progressive_contract


def decide(market: Dict[str, Any], now: int | None = None) -> Dict[str, Any]:
    now = int(time.time()) if now is None else now
    intelligence = assess_entry(market)
    base = {"schema_version": "V29_ENTRY_TPBE_1", "runtime_version": "V29", "symbol": market.get("symbol", "XAUUSD"),
            "sequence_id": int(market.get("sequence_id", 0)), "heartbeat_unix": int(market.get("heartbeat_unix", now)),
            "final_authority": "V29_AI_ENTRY_INTELLIGENCE", "progressive_tp_be": progressive_contract(), **intelligence}
    if not intelligence["entry_allowed"]:
        return {**base, "decision": "NO_TRADE", "reason": intelligence["entry_intelligence_reason"]}
    entry = float(market.get("price", market.get("bid", 0.0)) or 0.0)
    initial_r_points = float(market.get("initial_r_points", 100.0) or 100.0)
    if entry <= 0 or initial_r_points <= 0:
        return {**base, "decision": "NO_TRADE", "entry_allowed": False, "reason": "INVALID_INITIAL_RISK_BOUNDARY"}
    return {**base, "decision": "TRADE", "direction": intelligence["candidate_direction"], "entry_price": entry,
            "lot": float(market.get("lot", 0.01) or 0.01), "initial_r_points": initial_r_points,
            "reason": "V29_ENTRY_CONFIRMED_WITH_PROGRESSIVE_TP_BE"}
