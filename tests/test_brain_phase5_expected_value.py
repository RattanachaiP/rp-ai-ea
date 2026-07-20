"""Expected Value Engine tests: immutable, analytical, and detached from V26."""

from dataclasses import FrozenInstanceError
from pathlib import Path

import pytest

from brain.expected_value_engine import ExpectedValueAssessment, evaluate_expected_value
from brain.market_perception import extract_market_perception
from brain.market_reasoning import reason_about_market
from brain.market_understanding import interpret_market_understanding
from brain.probability_engine import estimate_market_probabilities


def _context():
    understanding = interpret_market_understanding(extract_market_perception({
        "bid": 2355, "ma50": 2354, "ma90": 2352, "ma200": 2350,
        "opens": [2350, 2349], "highs": [2360, 2355], "lows": [2348, 2345],
        "closes": [2358, 2351], "rsi": 60, "macd_hist": 0.5, "atr_raw": 8,
    }))
    reasoning = reason_about_market(understanding)
    return understanding, reasoning, estimate_market_probabilities(understanding, reasoning)


def test_expected_value_assessment_is_immutable_and_non_directional():
    understanding, reasoning, probabilities = _context()
    assessment = evaluate_expected_value(understanding, reasoning, probabilities)

    assert isinstance(assessment, ExpectedValueAssessment)
    assert assessment.understanding is understanding
    assert assessment.reasoning is reasoning
    assert assessment.probability_assessment is probabilities
    assert assessment.risk == 0.25
    assert assessment.reward == 0.625
    assert assessment.risk_reward_ratio == 2.5
    assert assessment.expected_value == 0.375
    assert assessment.uncertainty_impact == 0.0875
    assert assessment.confidence_interval.lower == 0.2875
    assert assessment.confidence_interval.upper == 0.4625
    assert assessment.opportunity_quality == "POSITIVE_EDGE_OBSERVED"
    assert not hasattr(assessment, "buy")
    assert not hasattr(assessment, "sell")
    with pytest.raises(FrozenInstanceError):
        assessment.expected_value = 0.0


def test_expected_value_engine_rejects_unmatched_inputs():
    understanding, reasoning, probabilities = _context()
    other = interpret_market_understanding(extract_market_perception({"bid": 1.0}))
    with pytest.raises(ValueError):
        evaluate_expected_value(other, reasoning, probabilities)
    with pytest.raises(TypeError):
        evaluate_expected_value(understanding, reasoning, {})


def test_expected_value_engine_has_no_production_runtime_connection():
    engine_source = (Path(__file__).parents[1] / "bridge" /
                     "ai_decision_engine_xauusd_v26_execution_confidence_engine.py").read_text(
                         encoding="utf-8")
    assert "expected_value_engine import" not in engine_source
    assert "evaluate_expected_value" not in engine_source
