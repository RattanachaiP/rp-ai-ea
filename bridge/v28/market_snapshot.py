"""Governed closed-bar validation and V28 intelligence orchestration."""
from __future__ import annotations
from dataclasses import dataclass
from math import isfinite
from types import MappingProxyType
from typing import Any, Mapping, Sequence
from .intelligence_policy import DEFAULT_POLICY, IntelligencePolicy


@dataclass(frozen=True)
class MarketSnapshot:
    symbol: str
    timeframe: str
    sequence_id: int
    mid: float
    bars: tuple[Mapping[str, Any], ...]
    ranges: tuple[float, ...]
    bodies: tuple[float, ...]
    input_bar_count: int
    valid_bar_count: int
    rejected_bar_count: int
    rejection_reasons: tuple[str, ...]
    data_quality: str
    policy_id: str
    policy_version: str


def _timeframe_seconds(value: str) -> int | None:
    units = {"M": 60, "H": 3600, "D": 86400}
    if len(value) < 2 or value[0] not in units or not value[1:].isdigit():
        return None
    return units[value[0]] * int(value[1:])


def build_market_snapshot(market: Mapping[str, Any], policy: IntelligencePolicy = DEFAULT_POLICY) -> MarketSnapshot:
    raw = market.get("bars", ())
    raw_bars = list(raw) if isinstance(raw, Sequence) and not isinstance(raw, (str, bytes)) else []
    reasons: list[str] = []
    bars: list[Mapping[str, Any]] = []
    expected_spacing = _timeframe_seconds(str(market["timeframe"]).upper())
    for index, item in enumerate(raw_bars):
        prefix = f"BAR_{index}"
        if not isinstance(item, Mapping):
            reasons.append(f"{prefix}_NOT_MAPPING"); continue
        missing = {"timestamp", "open", "high", "low", "close", "closed", "source_sequence_id"} - item.keys()
        if missing:
            reasons.append(f"{prefix}_MISSING_{'_'.join(sorted(missing)).upper()}"); continue
        try:
            values = {key: float(item[key]) for key in ("timestamp", "open", "high", "low", "close")}
        except (TypeError, ValueError, OverflowError):
            reasons.append(f"{prefix}_NON_NUMERIC"); continue
        if not all(isfinite(value) for value in values.values()) or values["timestamp"] <= 0:
            reasons.append(f"{prefix}_NON_FINITE"); continue
        if item["closed"] is not True:
            reasons.append(f"{prefix}_FORMING"); continue
        if type(item["source_sequence_id"]) is not int or item["source_sequence_id"] != market["sequence_id"]:
            reasons.append(f"{prefix}_SOURCE_SEQUENCE_MISMATCH"); continue
        if values["high"] < max(values["open"], values["close"]) or values["low"] > min(values["open"], values["close"]) or values["low"] <= 0:
            reasons.append(f"{prefix}_OHLC_INVALID"); continue
        bars.append(MappingProxyType({**values, "closed": True, "source_sequence_id": item["source_sequence_id"]}))
    timestamps = [bar["timestamp"] for bar in bars]
    if len(timestamps) != len(set(timestamps)):
        reasons.append("DUPLICATE_TIMESTAMP")
    if any(right <= left for left, right in zip(timestamps, timestamps[1:])):
        reasons.append("NON_MONOTONIC_ORDER")
    if expected_spacing is None:
        reasons.append("UNSUPPORTED_TIMEFRAME")
    elif any(right - left != expected_spacing for left, right in zip(timestamps, timestamps[1:])):
        reasons.append("TIMEFRAME_SPACING_MISMATCH")
    rejected = len(raw_bars) - len(bars)
    quality = "FAIL_CLOSED" if reasons else "INSUFFICIENT" if len(bars) < policy.minimum_bars else "VALID"
    if reasons:
        bars = []  # partial corruption can never reach classification
    return MarketSnapshot(str(market["symbol"]), str(market["timeframe"]), int(market["sequence_id"]),
                          float(market.get("mid", (float(market["bid"]) + float(market["ask"])) / 2)), tuple(bars),
                          tuple(bar["high"] - bar["low"] for bar in bars),
                          tuple(abs(bar["close"] - bar["open"]) for bar in bars), len(raw_bars),
                          len(bars) if not reasons else len(raw_bars) - rejected, rejected, tuple(reasons), quality,
                          policy.policy_id, policy.version)


def build_market_intelligence(market: Mapping[str, Any], policy: IntelligencePolicy = DEFAULT_POLICY) -> dict[str, Any]:
    from .liquidity_context import describe_liquidity
    from .market_regime import identify_regime
    from .market_structure import describe_structure
    from .momentum_context import describe_momentum
    from .opportunity_builder import build_opportunity
    from .trend_context import describe_trend
    from .volatility_context import describe_volatility
    snapshot = build_market_snapshot(market, policy)
    structure = describe_structure(snapshot, policy)
    volatility = describe_volatility(snapshot, policy)
    trend = describe_trend(snapshot, structure, policy)
    momentum = describe_momentum(snapshot, trend, policy)
    liquidity = describe_liquidity(snapshot, policy)
    regime = identify_regime(structure, volatility, momentum, policy)
    opportunity = build_opportunity(structure, regime, trend, momentum, volatility, liquidity, policy)
    return {"structure": structure, "regime": regime, "trend": trend, "momentum": momentum,
            "volatility": volatility, "liquidity": liquidity, "opportunity": opportunity}
