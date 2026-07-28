from dataclasses import FrozenInstanceError

import pytest

from bridge.v28.market_snapshot import build_market_intelligence
from bridge.v28.runtime_context import construct_runtime_context


def market(bars):
    return {"symbol": "XAUUSD", "timeframe": "M1", "sequence_id": 11, "heartbeat_unix": 100.0,
            "bid": 109.9, "ask": 110.1, "mid": 110.0, "bars": bars}


def advancing_bars():
    return [
        {"open": 100, "high": 102, "low": 99, "close": 101},
        {"open": 101, "high": 104, "low": 100, "close": 103},
        {"open": 103, "high": 106, "low": 102, "close": 105},
        {"open": 105, "high": 108, "low": 104, "close": 107},
        {"open": 107, "high": 111, "low": 106, "close": 110},
    ]


def test_complete_intelligence_is_descriptive_and_explainable():
    value = build_market_intelligence(market(advancing_bars()))
    assert set(value) == {"structure", "regime", "trend", "momentum", "volatility", "liquidity", "opportunity"}
    assert value["structure"]["condition"] == "ADVANCING"
    assert value["trend"]["direction"] == "UPWARD"
    assert value["opportunity"]["state"] in {"OPPORTUNITY_EXISTS", "NO_OPPORTUNITY"}
    assert all(context["explanation"] for context in value.values())
    forbidden = {"BUY", "SELL", "HOLD", "RISK", "CONFIDENCE", "ENTRY_PERMISSION"}
    assert forbidden.isdisjoint(str(value).upper().replace("'", " ").replace(":", " ").split())


def test_insufficient_history_fails_descriptively_without_inventing_context():
    value = build_market_intelligence(market(advancing_bars()[:2]))
    assert value["structure"]["condition"] == "UNDETERMINED"
    assert value["regime"]["state"] == "UNDETERMINED"
    assert value["opportunity"] == {"state": "NO_OPPORTUNITY", "reason": "INSUFFICIENT_MARKET_EVIDENCE",
                                    "explanation": "opportunity requires all descriptive contexts"}


def test_replay_is_deterministic_and_runtime_context_is_deeply_immutable():
    source = market(advancing_bars())
    assert build_market_intelligence(source) == build_market_intelligence(source)
    context = construct_runtime_context(source, now=101.0)
    assert context.structure["condition"] == "ADVANCING"
    with pytest.raises(TypeError):
        context.structure["condition"] = "RANGE"
    with pytest.raises(FrozenInstanceError):
        context.trend = {}


def test_invalid_bars_are_ignored_deterministically():
    bars = advancing_bars() + [{"open": 1, "high": 0, "low": 2, "close": 1}, {"bad": 1}]
    value = build_market_intelligence(market(bars))
    assert value["structure"]["condition"] == "ADVANCING"
