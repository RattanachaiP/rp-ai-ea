"""V29 decision producer with V29.1 entry-quality timing gate."""
from __future__ import annotations

import time
from typing import Any, Dict

from .entry_intelligence import assess_entry
from .entry_quality_engine import evaluate_entry_quality
from .progressive_tp_be import progressive_contract


def _quality_payload(quality: Dict[str, Any]) -> Dict[str, Any]:
    """Map the V29.1 contract into additive V29 payload fields."""
    return {
        "entry_score": quality["entry_score"],
        "entry_confidence": quality["confidence"],
        "waiting_reason": quality["waiting_reason"],
        "entry_components": quality["component_scores"],
        "entry_quality": quality,
        "entry_quality_telemetry": quality["telemetry"],
    }


def decide(market: Dict[str, Any], now: int | None = None) -> Dict[str, Any]:
    now = int(time.time()) if now is None else now
    intelligence = assess_entry(market)
    base = {"schema_version": "V29_ENTRY_TPBE_1", "runtime_version": "V29", "symbol": market.get("symbol", "XAUUSD"),
            "sequence_id": int(market.get("sequence_id", 0)), "heartbeat_unix": int(market.get("heartbeat_unix", now)),
            "final_authority": "V29_AI_ENTRY_INTELLIGENCE", "progressive_tp_be": progressive_contract(), **intelligence}
    if intelligence["candidate_direction"] not in {"BUY", "SELL"}:
        return {**base, "decision": "NO_TRADE", "reason": intelligence["entry_intelligence_reason"],
                "entry_score": 0, "entry_confidence": "LOW", "waiting_reason": "NO_DIRECTIONAL_EDGE", "entry_components": {}}

    quality = evaluate_entry_quality(intelligence["candidate_direction"], market)
    enriched = {**base, **_quality_payload(quality)}
    if not quality["accepted"]:
        return {**enriched, "decision": "WAIT_FOR_BETTER_ENTRY", "direction": intelligence["candidate_direction"],
                "entry_allowed": False, "reason": quality["waiting_reason"]}
    entry = float(market.get("price", market.get("bid", 0.0)) or 0.0)
    initial_r_points = float(market.get("initial_r_points", 100.0) or 100.0)
    if entry <= 0 or initial_r_points <= 0:
        return {**enriched, "decision": "NO_TRADE", "entry_allowed": False, "reason": "INVALID_INITIAL_RISK_BOUNDARY"}
    return {**enriched, "decision": "TRADE", "direction": intelligence["candidate_direction"], "entry_price": entry,
            "lot": float(market.get("lot", 0.01) or 0.01), "initial_r_points": initial_r_points,
            "reason": "V29_ENTRY_CONFIRMED_WITH_PROGRESSIVE_TP_BE"}
