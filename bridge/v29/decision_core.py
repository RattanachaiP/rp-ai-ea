"""V29 decision producer with V29.1 entry-quality timing gate."""
from __future__ import annotations

import time
from typing import Any, Dict

from .entry_intelligence import assess_entry
from .entry_quality_engine import evaluate_entry_quality
from .progressive_tp_be import (
    PROFIT_LOCK_POINTS,
    PROFIT_LOCK_TRIGGER_POINTS,
    TP_POINTS,
    adaptive_contract,
    progressive_contract,
)


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
    initial_r_points = float(market.get("initial_r_points", 100.0) or 100.0)
    # These trader-authorized values are intentionally not market-overridable.
    base_tp = float(TP_POINTS)
    base_be = float(PROFIT_LOCK_POINTS)
    enable_tp = bool(market.get("EnableAIProgressiveTP", market.get("enable_ai_progressive_tp", True)))
    enable_be = bool(market.get("EnableAIProgressiveBE", market.get("enable_ai_progressive_be", True)))
    contract = None
    if enable_tp or enable_be:
        contract = adaptive_contract(base_tp, base_be if enable_be else 0.0, initial_r_points,
                                     trend_strength=float(market.get("trend_strength", 0.0) or 0.0),
                                     volatility=float(market.get("volatility", 0.0) or 0.0),
                                     entry_quality=float(market.get("entry_quality_score", 0.0) or 0.0))
    base = {"schema_version": "V29_3_BASE_TPBE_1", "runtime_version": "V29.3", "symbol": market.get("symbol", "XAUUSD"),
            "sequence_id": int(market.get("sequence_id", 0)), "heartbeat_unix": int(market.get("heartbeat_unix", now)),
            "final_authority": "V29_3_AI_TPBE_CONTRACT", "base_take_profit_points": base_tp,
            "base_break_even_points": base_be,
            "profit_lock_trigger_points": PROFIT_LOCK_TRIGGER_POINTS, "profit_lock_points": PROFIT_LOCK_POINTS,
            "enable_ai_progressive_tp": enable_tp,
            "enable_ai_progressive_be": enable_be,
            # Retained as an additive V29 compatibility field. The executor
            # selects adaptive_tp_be_contract whenever it is present.
            "progressive_tp_be": progressive_contract(), **intelligence}
    if contract is not None:
        base["adaptive_tp_be_contract"] = contract
    if intelligence["candidate_direction"] not in {"BUY", "SELL"}:
        return {**base, "decision": "NO_TRADE", "reason": intelligence["entry_intelligence_reason"],
                "entry_score": 0, "entry_confidence": "LOW", "waiting_reason": "NO_DIRECTIONAL_EDGE", "entry_components": {}}

    quality = evaluate_entry_quality(intelligence["candidate_direction"], market)
    enriched = {**base, **_quality_payload(quality)}
    if not quality["accepted"]:
        return {**enriched, "decision": "WAIT_FOR_BETTER_ENTRY", "direction": intelligence["candidate_direction"],
                "entry_allowed": False, "reason": quality["waiting_reason"]}
    entry = float(market.get("price", market.get("bid", 0.0)) or 0.0)
    if entry <= 0 or initial_r_points <= 0:
        return {**enriched, "decision": "NO_TRADE", "entry_allowed": False, "reason": "INVALID_INITIAL_RISK_BOUNDARY"}
    return {**enriched, "decision": "TRADE", "direction": intelligence["candidate_direction"], "entry_price": entry,
            "lot": float(market.get("lot", 0.01) or 0.01), "initial_r_points": initial_r_points,
            "reason": "V29_ENTRY_CONFIRMED_WITH_PROGRESSIVE_TP_BE"}
