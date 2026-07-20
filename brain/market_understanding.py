"""Private Market Understanding interpretation for the V26 compatibility runtime.

This module translates Market Perception observations into descriptive market
context.  It deliberately has no decision, scoring, confidence, probability,
or execution dependencies and is never published in ``decision.json``.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

from brain.market_perception import MarketPerception


@dataclass(frozen=True)
class MarketUnderstanding:
    """Interpreted, internal-only market context with no trade intent."""

    perception: MarketPerception
    market_regime: str
    trend_state: str
    market_structure: str
    expansion_compression: str
    pullback_state: str
    transition_state: str
    liquidity_context: str
    momentum_context: str
    volatility_context: str
    market_narrative: str
    invalid_conditions: tuple[str, ...]
    context_quality: str

    @property
    def market_state(self) -> Mapping[str, Any]:
        """Expose the original object for the unchanged authoritative V26 path."""
        return self.perception.market_state


def _invalid_conditions(perception: MarketPerception) -> tuple[str, ...]:
    data = perception.market_state
    conditions: list[str] = []
    if not isinstance(data, Mapping):
        conditions.append("MARKET_STATE_NOT_MAPPING")
    if not data:
        conditions.append("MARKET_STATE_EMPTY")
    if not data.get("bid"):
        conditions.append("BID_UNAVAILABLE")
    if perception.trend == "NEUTRAL":
        conditions.append("TREND_OBSERVATION_INCOMPLETE")
    if perception.market_structure == "UNKNOWN":
        conditions.append("STRUCTURE_OBSERVATION_INCOMPLETE")
    if perception.volatility == "UNKNOWN":
        conditions.append("VOLATILITY_OBSERVATION_INCOMPLETE")
    return tuple(conditions)


def interpret_market_understanding(perception: MarketPerception) -> MarketUnderstanding:
    """Interpret observations into context only; do not evaluate a trade."""
    if not isinstance(perception, MarketPerception):
        raise TypeError("Market Understanding requires a MarketPerception object")

    trend = perception.trend
    structure = perception.market_structure
    if trend == "UP" and structure == "HH_HL":
        regime, trend_state = "TRENDING", "ESTABLISHED_UP"
    elif trend == "DOWN" and structure == "LH_LL":
        regime, trend_state = "TRENDING", "ESTABLISHED_DOWN"
    elif trend in {"UP", "DOWN"}:
        regime, trend_state = "TRANSITION", f"{trend}_STRUCTURE_UNCONFIRMED"
    elif structure in {"HH_HL", "LH_LL"}:
        regime, trend_state = "STRUCTURAL_TRANSITION", "MA_TREND_UNCONFIRMED"
    else:
        regime, trend_state = "RANGE_OR_UNDEFINED", "NEUTRAL"

    impulse = perception.impulse_detection
    if trend == "UP" and impulse == "BEARISH":
        pullback_state = "PULLBACK_WITHIN_UP_CONTEXT"
    elif trend == "DOWN" and impulse == "BULLISH":
        pullback_state = "PULLBACK_WITHIN_DOWN_CONTEXT"
    elif impulse == "UNKNOWN":
        pullback_state = "UNKNOWN"
    else:
        pullback_state = "NO_PULLBACK_OBSERVED"

    transition_state = (
        "TRANSITION_OBSERVED"
        if regime in {"TRANSITION", "STRUCTURAL_TRANSITION"} or perception.liquidity_sweep != "NONE"
        else "STABLE_CONTEXT"
    )
    liquidity_context = (
        f"{perception.liquidity_sweep}_OBSERVED"
        if perception.liquidity_sweep != "NONE"
        else "NO_LIQUIDITY_SWEEP_OBSERVED"
    )
    if impulse in {"BULLISH", "BEARISH"} and perception.momentum_observation == impulse:
        momentum_context = f"{impulse}_MOMENTUM_ALIGNED"
    elif perception.momentum_observation == "MIXED":
        momentum_context = "MIXED_MOMENTUM"
    else:
        momentum_context = "MOMENTUM_IMPULSE_DIVERGENCE"
    volatility_context = f"{perception.volatility}_VOLATILITY_ATR_{perception.atr_state}"

    invalid_conditions = _invalid_conditions(perception)
    if "MARKET_STATE_EMPTY" in invalid_conditions or "BID_UNAVAILABLE" in invalid_conditions:
        context_quality = "INSUFFICIENT"
    elif invalid_conditions:
        context_quality = "PARTIAL"
    else:
        context_quality = "COMPLETE"
    narrative = (
        f"{regime}; {trend_state}; structure={structure}; "
        f"{perception.compression_expansion}; {pullback_state}; {momentum_context}; "
        f"{liquidity_context}; {volatility_context}."
    )
    return MarketUnderstanding(
        perception=perception,
        market_regime=regime,
        trend_state=trend_state,
        market_structure=structure,
        expansion_compression=perception.compression_expansion,
        pullback_state=pullback_state,
        transition_state=transition_state,
        liquidity_context=liquidity_context,
        momentum_context=momentum_context,
        volatility_context=volatility_context,
        market_narrative=narrative,
        invalid_conditions=invalid_conditions,
        context_quality=context_quality,
    )
