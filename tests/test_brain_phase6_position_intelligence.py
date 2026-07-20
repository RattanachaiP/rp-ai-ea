"""Position Intelligence is immutable shadow analysis, not trade authority."""

from dataclasses import FrozenInstanceError
from pathlib import Path

import pytest

from brain.expected_value_engine import evaluate_expected_value
from brain.market_perception import extract_market_perception
from brain.market_reasoning import reason_about_market
from brain.market_understanding import interpret_market_understanding
from brain.position_intelligence import PositionIntelligenceAssessment, assess_position_intelligence
from brain.probability_engine import estimate_market_probabilities


def _inputs():
    understanding = interpret_market_understanding(extract_market_perception({
        "bid": 2355, "ma50": 2354, "ma90": 2352, "ma200": 2350,
        "opens": [2350, 2349], "highs": [2360, 2355], "lows": [2348, 2345],
        "closes": [2358, 2351], "rsi": 60, "macd_hist": 0.5, "atr_raw": 8,
    }))
    reasoning = reason_about_market(understanding)
    probabilities = estimate_market_probabilities(understanding, reasoning)
    return understanding, reasoning, probabilities, evaluate_expected_value(understanding, reasoning, probabilities)


def test_position_intelligence_is_immutable_non_executable_shadow_analysis():
    assessment = assess_position_intelligence(*_inputs())
    assert isinstance(assessment, PositionIntelligenceAssessment)
    assert assessment.position_eligibility == "CONTEXTUALLY_ELIGIBLE"
    assert assessment.risk_budget_class == "ANALYTICAL_STANDARD"
    assert assessment.stop_loss_context == "STRUCTURE_INVALIDATION_CONTEXT"
    assert assessment.target_context == "CONTINUATION_OR_EXPANSION_CONTEXT"
    assert assessment.risk_reward_feasibility == "FAVOURABLE_NORMALIZED_FEASIBILITY"
    assert assessment.position_style == "TREND_CONTEXT"
    assert assessment.runner_suitability == "SUITABLE"
    assert assessment.invalidation_context
    assert not any(hasattr(assessment, name) for name in ("buy", "sell", "entry", "sl", "tp", "lot_size"))
    with pytest.raises(FrozenInstanceError):
        assessment.position_quality = "changed"


def test_position_intelligence_rejects_mismatched_lineage_and_has_no_runtime_connection():
    understanding, reasoning, probabilities, expected_value = _inputs()
    other = interpret_market_understanding(extract_market_perception({"bid": 1.0}))
    with pytest.raises(ValueError):
        assess_position_intelligence(other, reasoning, probabilities, expected_value)
    with pytest.raises(TypeError):
        assess_position_intelligence(understanding, reasoning, probabilities, {})
    source = (Path(__file__).parents[1] / "bridge" / "ai_decision_engine_xauusd_v26_execution_confidence_engine.py").read_text(encoding="utf-8")
    assert "position_intelligence import" not in source
    assert "assess_position_intelligence" not in source
