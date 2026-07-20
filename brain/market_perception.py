"""Observation-only Market Perception for the V26 compatibility runtime.

This module deliberately has no decision, scoring, or execution dependencies.
Its output is an in-process object; it is never merged into ``decision.json``.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Mapping


def _number(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _series(data: Mapping[str, Any], names: tuple[str, ...]) -> list[float]:
    for name in names:
        value = data.get(name)
        if isinstance(value, list):
            values = [_number(item) for item in value]
            return [item for item in values if item]
    values = []
    for index in range(1, 11):
        for name in names:
            key = f"{name}{index}"
            if key in data:
                value = _number(data[key])
                if value:
                    values.append(value)
                break
    return values


def _session(value: Any) -> str:
    """Classify time only; this is not an entry/session eligibility rule."""
    text = str(value or "").strip()
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
        hour = (parsed.astimezone(timezone.utc) if parsed.tzinfo else parsed).hour
    except ValueError:
        return "UNKNOWN"
    if 0 <= hour < 7:
        return "ASIA"
    if 7 <= hour < 12:
        return "LONDON"
    if 12 <= hour < 17:
        return "NEW_YORK"
    if 17 <= hour < 21:
        return "NEW_YORK_LATE"
    return "OFF_HOURS"


@dataclass(frozen=True)
class MarketPerception:
    """Raw market reference plus descriptive observations, with no trade intent."""

    market_state: Mapping[str, Any]
    trend: str
    swing_high: float | None
    swing_low: float | None
    market_structure: str
    liquidity_sweep: str
    volatility: str
    atr_state: str
    vwap_relation: str
    session: str
    momentum_observation: str
    compression_expansion: str
    impulse_detection: str


def extract_market_perception(market_state: Mapping[str, Any]) -> MarketPerception:
    """Extract descriptive observations without selecting or evaluating a trade."""
    data = market_state if isinstance(market_state, Mapping) else {}
    bid = _number(data.get("bid"))
    highs = _series(data, ("highs", "high"))
    lows = _series(data, ("lows", "low"))
    opens = _series(data, ("opens", "open"))
    closes = _series(data, ("closes", "close"))

    ma50, ma90, ma200 = (_number(data.get(key)) for key in ("ma50", "ma90", "ma200"))
    if ma50 and ma90 and ma200 and ma50 > ma90 > ma200:
        trend = "UP"
    elif ma50 and ma90 and ma200 and ma50 < ma90 < ma200:
        trend = "DOWN"
    else:
        trend = "NEUTRAL"

    if len(highs) >= 2 and len(lows) >= 2 and highs[0] > highs[-1] and lows[0] > lows[-1]:
        structure = "HH_HL"
    elif len(highs) >= 2 and len(lows) >= 2 and highs[0] < highs[-1] and lows[0] < lows[-1]:
        structure = "LH_LL"
    else:
        structure = "UNKNOWN"

    prior_high = max(highs[1:], default=0.0)
    prior_low = min(lows[1:], default=0.0)
    if highs and prior_high and highs[0] > prior_high and closes and closes[0] < prior_high:
        sweep = "SWEEP_HIGH"
    elif lows and prior_low and lows[0] < prior_low and closes and closes[0] > prior_low:
        sweep = "SWEEP_LOW"
    else:
        sweep = "NONE"

    bb_upper, bb_lower = _number(data.get("bb_upper")), _number(data.get("bb_lower"))
    bb_width = bb_upper - bb_lower if bb_upper > bb_lower else 0.0
    recent_ranges = [high - low for high, low in zip(highs, lows) if high >= low]
    range_average = sum(recent_ranges) / len(recent_ranges) if recent_ranges else 0.0
    if bb_width and range_average and bb_width <= range_average * 2:
        compression = "COMPRESSION"
    elif recent_ranges and range_average and recent_ranges[0] >= range_average * 1.5:
        compression = "EXPANSION"
    else:
        compression = "NORMAL"
    volatility = "HIGH" if recent_ranges and recent_ranges[0] >= max(range_average * 1.5, 0.0) else "NORMAL" if recent_ranges else "UNKNOWN"

    atr = _number(data.get("atr_raw", data.get("atr_value_raw", data.get("atr", data.get("atr_value", 0)))))
    atr_state = "AVAILABLE" if atr > 0 else "UNAVAILABLE"
    vwap = _number(data.get("vwap", data.get("VWAP", 0)))
    vwap_relation = "ABOVE" if bid and vwap and bid > vwap else "BELOW" if bid and vwap and bid < vwap else "AT" if bid and vwap else "UNAVAILABLE"

    rsi, macd = _number(data.get("rsi")), _number(data.get("macd_hist", data.get("macdHist", 0)))
    momentum = "BULLISH" if rsi > 50 and macd > 0 else "BEARISH" if rsi < 50 and macd < 0 else "MIXED"
    if opens and highs and lows and closes:
        candle_range = max(highs[0] - lows[0], 0.0)
        body = closes[0] - opens[0]
        impulse = "BULLISH" if candle_range and body / candle_range >= 0.65 else "BEARISH" if candle_range and body / candle_range <= -0.65 else "NONE"
    else:
        impulse = "UNKNOWN"

    return MarketPerception(data, trend, max(highs) if highs else None, min(lows) if lows else None,
                            structure, sweep, volatility, atr_state, vwap_relation,
                            _session(data.get("server_time", data.get("updated_at", data.get("bar_time")))),
                            momentum, compression, impulse)
