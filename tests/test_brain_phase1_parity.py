"""Parity tests for private Brain interpretation and explanation layers."""

from dataclasses import FrozenInstanceError

from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path
import sys


ENGINE_PATH = Path(__file__).parents[1] / "bridge" / "ai_decision_engine_xauusd_v26_execution_confidence_engine.py"
sys.path.insert(0, str(ENGINE_PATH.parent))
SPEC = spec_from_file_location("v26_brain_parity_engine", ENGINE_PATH)
ENGINE = module_from_spec(SPEC)
SPEC.loader.exec_module(ENGINE)


def test_candidate_decision_brain_boundaries_preserve_object_identity_and_contents():
    payload = {"bid": 2350.25, "rsi": 58.0, "decision": "TRADE", "sl": 2340.25, "tp": 2365.25}
    original = dict(payload)

    for stage in (
        ENGINE.brain_probability_engine,
        ENGINE.brain_expected_value_engine,
        ENGINE.brain_position_intelligence,
        ENGINE.brain_decision_publication,
    ):
        assert stage(payload) is payload
        assert payload == original


def test_market_perception_extracts_observations_without_mutating_or_deciding():
    market_state = {
        "bid": 2355, "ma50": 2354, "ma90": 2352, "ma200": 2350,
        "opens": [2350, 2349], "highs": [2360, 2355], "lows": [2348, 2345],
        "closes": [2358, 2351], "rsi": 60, "macd_hist": 0.5,
        "vwap": 2352, "atr_raw": 8, "server_time": "2026-01-01T08:00:00Z",
    }
    original = dict(market_state)
    perception = ENGINE.brain_market_perception(market_state)

    assert perception.market_state is market_state
    assert perception.trend == "UP"
    assert perception.market_structure == "HH_HL"
    assert perception.vwap_relation == "ABOVE"
    assert perception.session == "LONDON"
    assert not hasattr(perception, "decision")
    assert market_state == original
    understanding = ENGINE.brain_market_understanding(perception)
    assert understanding.market_state is market_state
    assert understanding.market_regime == "TRENDING"
    assert understanding.trend_state == "ESTABLISHED_UP"
    assert understanding.market_structure == "HH_HL"
    assert understanding.expansion_compression in {"COMPRESSION", "EXPANSION", "NORMAL"}
    assert understanding.pullback_state == "NO_PULLBACK_OBSERVED"
    assert understanding.transition_state == "STABLE_CONTEXT"
    assert understanding.liquidity_context == "NO_LIQUIDITY_SWEEP_OBSERVED"
    assert understanding.momentum_context == "BULLISH_MOMENTUM_ALIGNED"
    assert understanding.volatility_context == "NORMAL_VOLATILITY_ATR_AVAILABLE"
    assert understanding.market_narrative
    assert understanding.invalid_conditions == ()
    assert understanding.context_quality == "COMPLETE"
    assert not hasattr(understanding, "decision")
    reasoning = ENGINE.brain_market_reasoning(understanding)
    assert reasoning.understanding is understanding
    assert reasoning.supporting_evidence
    assert reasoning.continuation_case
    assert reasoning.reversal_case
    assert reasoning.wait_case
    assert reasoning.narrative
    assert not hasattr(reasoning, "decision")
    try:
        reasoning.narrative = "changed"
    except FrozenInstanceError:
        pass
    else:
        raise AssertionError("MarketReasoning must be immutable")


def test_brain_phase1_build_path_matches_direct_v26_build_for_wait_fixture():
    # Invalid bid follows a deterministic V26 WAIT/NO_TRADE path and avoids
    # time-dependent trade UUID/publication metadata.
    market_state = {"bid": 0, "ma50": 2300, "bar_time": "brain-parity-fixture"}

    direct = ENGINE.build_decision(dict(market_state))
    understanding = ENGINE.brain_market_understanding(
        ENGINE.brain_market_perception(dict(market_state))
    )
    reasoning = ENGINE.brain_market_reasoning(understanding)
    staged_input = reasoning.understanding.market_state
    staged = ENGINE.build_decision(staged_input)
    staged_decision = ENGINE.brain_position_intelligence(
        ENGINE.brain_expected_value_engine(
            ENGINE.brain_probability_engine(staged[2])
        )
    )

    assert staged[:2] == direct[:2]
    assert staged_decision == direct[2]
