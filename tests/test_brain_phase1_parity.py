"""Parity tests for the V26 Brain boundaries and Phase 2A perception object."""

from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path
import sys


ENGINE_PATH = Path(__file__).parents[1] / "bridge" / "ai_decision_engine_xauusd_v26_execution_confidence_engine.py"
sys.path.insert(0, str(ENGINE_PATH.parent))
SPEC = spec_from_file_location("v26_brain_parity_engine", ENGINE_PATH)
ENGINE = module_from_spec(SPEC)
SPEC.loader.exec_module(ENGINE)


def test_non_perception_brain_boundaries_preserve_object_identity_and_contents():
    payload = {"bid": 2350.25, "rsi": 58.0, "decision": "TRADE", "sl": 2340.25, "tp": 2365.25}
    original = dict(payload)

    for stage in (
        ENGINE.brain_market_understanding,
        ENGINE.brain_market_reasoning,
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
    assert ENGINE.brain_market_understanding(perception) is market_state


def test_brain_phase1_build_path_matches_direct_v26_build_for_wait_fixture():
    # Invalid bid follows a deterministic V26 WAIT/NO_TRADE path and avoids
    # time-dependent trade UUID/publication metadata.
    market_state = {"bid": 0, "ma50": 2300, "bar_time": "brain-parity-fixture"}

    direct = ENGINE.build_decision(dict(market_state))
    staged_input = ENGINE.brain_market_understanding(
        ENGINE.brain_market_perception(dict(market_state))
    )
    staged = ENGINE.build_decision(staged_input)
    staged_decision = ENGINE.brain_position_intelligence(
        ENGINE.brain_expected_value_engine(
            ENGINE.brain_probability_engine(ENGINE.brain_market_reasoning(staged[2]))
        )
    )

    assert staged[:2] == direct[:2]
    assert staged_decision == direct[2]
