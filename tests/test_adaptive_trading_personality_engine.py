"""ATPE is an immutable, private, non-executable shadow layer."""

from dataclasses import FrozenInstanceError
from pathlib import Path

import pytest

from brain.adaptive_trading_personality_engine import TradingPersonalityAssessment, select_trading_personality
from brain.expected_value_engine import evaluate_expected_value
from brain.market_perception import extract_market_perception
from brain.market_reasoning import reason_about_market
from brain.market_understanding import interpret_market_understanding
from brain.position_intelligence import assess_position_intelligence
from brain.probability_engine import estimate_market_probabilities


def _inputs(state=None):
    state = state or {"bid": 2355, "ma50": 2354, "ma90": 2352, "ma200": 2350,
                      "opens": [2350, 2349], "highs": [2360, 2355], "lows": [2348, 2345],
                      "closes": [2358, 2351], "rsi": 60, "macd_hist": 0.5, "atr_raw": 8}
    understanding = interpret_market_understanding(extract_market_perception(state))
    reasoning = reason_about_market(understanding)
    probabilities = estimate_market_probabilities(understanding, reasoning)
    expected_value = evaluate_expected_value(understanding, reasoning, probabilities)
    position = assess_position_intelligence(understanding, reasoning, probabilities, expected_value)
    return understanding, reasoning, probabilities, expected_value, position


def test_atpe_selects_trend_rider_with_all_requested_analytical_outputs():
    assessment = select_trading_personality(*_inputs())
    assert isinstance(assessment, TradingPersonalityAssessment)
    assert assessment.trading_personality == "TREND_RIDER"
    assert 0 <= assessment.personality_confidence <= 1
    assert assessment.management_policy == "ANALYTICAL_TREND_CONTINUATION"
    assert assessment.allowed_actions == ("MONITOR_CONTEXT", "REASSESS_INVALIDATION")
    assert assessment.risk_aggression == "ANALYTICAL_STANDARD"
    assert assessment.protection_level == "STRUCTURE_AWARE"
    assert assessment.runner_policy == "CONTEXTUAL_RUNNER_ELIGIBLE"
    assert assessment.break_even_policy == "CONTEXTUAL_REVIEW"
    assert assessment.take_profit_policy == "CONTINUATION_CONTEXT"
    assert assessment.partial_exit_policy == "CONTEXTUAL_PARTIAL_REVIEW"
    with pytest.raises(FrozenInstanceError):
        assessment.trading_personality = "OBSERVER"


def test_atpe_uses_observer_for_insufficient_context():
    assessment = select_trading_personality(*_inputs({"bid": 0}))
    assert assessment.trading_personality == "OBSERVER"
    assert assessment.allowed_actions == ("OBSERVE_CONTEXT", "WAIT_FOR_COHERENCE")
    assert assessment.runner_policy == "NO_RUNNER_CONTEXT"


def test_atpe_rejects_mismatched_lineage_and_has_no_runtime_connection():
    inputs = _inputs()
    other = _inputs()
    with pytest.raises(ValueError):
        select_trading_personality(other[0], *inputs[1:])
    with pytest.raises(TypeError):
        select_trading_personality(*inputs[:4], {})
    source = (Path(__file__).parents[1] / "bridge" / "ai_decision_engine_xauusd_v26_execution_confidence_engine.py").read_text(encoding="utf-8")
    assert "adaptive_trading_personality_engine import" not in source
    assert "select_trading_personality" not in source
