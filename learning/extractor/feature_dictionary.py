"""Versioned, declarative feature contract for the learning pipeline."""
from __future__ import annotations
from dataclasses import dataclass
from typing import Literal

FeatureType = Literal["ENUM", "BOOLEAN", "NUMBER"]

@dataclass(frozen=True)
class FeatureDefinition:
    name: str
    description: str
    type: FeatureType
    allowed_values: tuple[object, ...]
    source: str
    version: str = "1.0"

# Definitions, including the canonical tokens, are deliberately centralized here.
def _enum(name: str, values: tuple[str, ...], source: str) -> FeatureDefinition:
    return FeatureDefinition(name, name.replace("_", " "), "ENUM", values, source)
def _bool(name: str, source: str) -> FeatureDefinition:
    return FeatureDefinition(name, name.replace("_", " "), "BOOLEAN", (True, False), source)
def _number(name: str, source: str) -> FeatureDefinition:
    return FeatureDefinition(name, name.replace("_", " "), "NUMBER", (), source)

FEATURE_DEFINITIONS = (
    _enum("trend_direction", ("UP", "DOWN", "SIDEWAYS", "UNKNOWN"), "market.trend"),
    _enum("trend_strength", ("WEAK", "MODERATE", "STRONG", "UNKNOWN"), "ADX"),
    _enum("trend_persistence", ("LOW", "MEDIUM", "HIGH", "UNKNOWN"), "trend_bars"),
    _enum("higher_tf_alignment", ("ALIGNED", "OPPOSED", "MIXED", "UNKNOWN"), "higher_tf_trend"),
    _enum("rsi_zone", ("OVERSOLD", "LOW", "NORMAL", "HIGH", "OVERBOUGHT", "UNKNOWN"), "RSI14"),
    _enum("macd_state", ("POSITIVE", "NEGATIVE", "NEUTRAL", "UNKNOWN"), "MACD"),
    _enum("macd_cross", ("BULLISH", "BEARISH", "NONE", "UNKNOWN"), "MACD.signal"),
    _enum("ao_state", ("BULLISH", "BEARISH", "NEUTRAL", "UNKNOWN"), "AO"),
    _enum("momentum_strength", ("WEAK", "MODERATE", "STRONG", "UNKNOWN"), "momentum"),
    _enum("atr_state", ("LOW", "NORMAL", "HIGH", "UNKNOWN"), "ATR"),
    _enum("bb_state", ("EXPANDING", "CONTRACTING", "NEUTRAL", "UNKNOWN"), "BollingerBands"),
    _enum("bb_width_state", ("NARROW", "NORMAL", "WIDE", "UNKNOWN"), "BollingerBands.width"),
    _enum("volatility_level", ("LOW", "NORMAL", "HIGH", "UNKNOWN"), "volatility"),
    _enum("expansion_state", ("EXPANDING", "CONTRACTING", "NEUTRAL", "UNKNOWN"), "range"),
    _enum("market_phase", ("TREND", "RANGE", "BREAKOUT", "REVERSAL", "UNKNOWN"), "market_state"),
    _bool("bos_detected", "structure.bos"), _bool("choch_detected", "structure.choch"),
    _enum("swing_position", ("HIGH", "LOW", "MIDDLE", "UNKNOWN"), "structure.swing"),
    _enum("structure_quality", ("LOW", "MEDIUM", "HIGH", "UNKNOWN"), "structure.quality"),
    _enum("liquidity_zone", ("SUPPORT", "RESISTANCE", "NEUTRAL", "UNKNOWN"), "liquidity"),
    _enum("vwap_position", ("ABOVE", "BELOW", "AT", "UNKNOWN"), "VWAP"),
    _number("distance_from_vwap", "VWAP"), _number("support_distance", "support"), _number("resistance_distance", "resistance"),
    _bool("asia", "timestamp"), _bool("london", "timestamp"), _bool("new_york", "timestamp"), _bool("overlap", "timestamp"), _bool("pre_news", "news"), _bool("post_news", "news"),
    _enum("spread_state", ("TIGHT", "NORMAL", "WIDE", "UNKNOWN"), "spread"),
    _number("sl_distance", "stop_loss"), _number("tp_distance", "take_profit"),
    _enum("rr_bucket", ("LOW", "MEDIUM", "HIGH", "UNKNOWN"), "r_multiple"),
    _enum("entry_delay", ("IMMEDIATE", "SHORT", "LONG", "UNKNOWN"), "entry_delay_seconds"),
    _enum("execution_quality", ("POOR", "FAIR", "GOOD", "UNKNOWN"), "execution"),
    _enum("win_loss", ("WIN", "LOSS", "BREAKEVEN", "UNKNOWN"), "result"),
    _enum("profit_bucket", ("LOSS", "SMALL_WIN", "LARGE_WIN", "BREAKEVEN", "UNKNOWN"), "net_profit"),
    _enum("holding_bucket", ("SHORT", "MEDIUM", "LONG", "UNKNOWN"), "duration_seconds"),
    _enum("mae_bucket", ("LOW", "MEDIUM", "HIGH", "UNKNOWN"), "MAE"),
    _enum("mfe_bucket", ("LOW", "MEDIUM", "HIGH", "UNKNOWN"), "MFE"),
)
