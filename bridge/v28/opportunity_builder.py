"""Combine descriptive contexts into opportunity presence, never trade intent."""
from __future__ import annotations
from typing import Any, Mapping


def build_opportunity(*, structure: Mapping[str, Any], regime: Mapping[str, Any], trend: Mapping[str, Any],
                      momentum: Mapping[str, Any], volatility: Mapping[str, Any], liquidity: Mapping[str, Any]) -> dict[str, Any]:
    contexts = (structure["condition"], regime["state"], trend["direction"], momentum["state"], volatility["state"], liquidity["nearest_pool"])
    if "UNDETERMINED" in contexts:
        return {"state": "NO_OPPORTUNITY", "reason": "INSUFFICIENT_MARKET_EVIDENCE",
                "explanation": "opportunity requires all descriptive contexts"}
    coherent = regime["state"] in ("TREND", "EXPANSION") and trend["direction"] in ("UPWARD", "DOWNWARD") and momentum["alignment"] == "ALIGNED"
    return {"state": "OPPORTUNITY_EXISTS" if coherent else "NO_OPPORTUNITY",
            "reason": "COHERENT_MARKET_CONTEXT" if coherent else "CONTEXT_NOT_COHERENT",
            "explanation": "structure, regime, trend, momentum, volatility, and liquidity were evaluated without trade direction"}
