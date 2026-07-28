"""Canonical price observations used by the V28 intelligence modules."""
from __future__ import annotations

from math import isfinite
from typing import Any, Mapping, Sequence


def build_market_snapshot(market: Mapping[str, Any]) -> dict[str, Any]:
    """Normalize optional closed bars into one replay-stable observation snapshot."""
    raw_bars = market.get("bars", ())
    bars: list[dict[str, float]] = []
    if isinstance(raw_bars, Sequence) and not isinstance(raw_bars, (str, bytes)):
        for raw in raw_bars:
            if not isinstance(raw, Mapping):
                continue
            try:
                bar = {key: float(raw[key]) for key in ("open", "high", "low", "close")}
            except (KeyError, TypeError, ValueError, OverflowError):
                continue
            if (all(isfinite(value) for value in bar.values()) and bar["high"] >= max(bar["open"], bar["close"])
                    and bar["low"] <= min(bar["open"], bar["close"]) and bar["low"] > 0):
                bars.append(bar)

    ranges = [bar["high"] - bar["low"] for bar in bars]
    bodies = [abs(bar["close"] - bar["open"]) for bar in bars]
    return {
        "symbol": str(market["symbol"]),
        "timeframe": str(market["timeframe"]),
        "sequence_id": int(market["sequence_id"]),
        "mid": float(market.get("mid", (float(market["bid"]) + float(market["ask"])) / 2)),
        "bars": tuple(bars),
        "ranges": tuple(ranges),
        "bodies": tuple(bodies),
        "data_state": "SUFFICIENT" if len(bars) >= 5 else "INSUFFICIENT",
        "explanation": f"{len(bars)} valid closed bars observed; 5 required for classification",
    }


def build_market_intelligence(market: Mapping[str, Any]) -> dict[str, Any]:
    """Run the explicit description pipeline and return its complete snapshot."""
    from .liquidity_context import describe_liquidity
    from .market_regime import identify_regime
    from .market_structure import describe_structure
    from .momentum_context import describe_momentum
    from .opportunity_builder import build_opportunity
    from .trend_context import describe_trend
    from .volatility_context import describe_volatility

    observation = build_market_snapshot(market)
    structure = describe_structure(observation)
    volatility = describe_volatility(observation)
    trend = describe_trend(observation, structure)
    momentum = describe_momentum(observation, trend)
    liquidity = describe_liquidity(observation)
    regime = identify_regime(structure, volatility, momentum)
    opportunity = build_opportunity(structure=structure, regime=regime, trend=trend, momentum=momentum,
                                    volatility=volatility, liquidity=liquidity)
    return {"structure": structure, "regime": regime, "trend": trend, "momentum": momentum,
            "volatility": volatility, "liquidity": liquidity, "opportunity": opportunity}
