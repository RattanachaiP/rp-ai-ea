"""Parity tests for the metadata-free V26 Brain Phase 1 boundaries."""

from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path
import sys


ENGINE_PATH = Path(__file__).parents[1] / "bridge" / "ai_decision_engine_xauusd_v26_execution_confidence_engine.py"
sys.path.insert(0, str(ENGINE_PATH.parent))
SPEC = spec_from_file_location("v26_brain_parity_engine", ENGINE_PATH)
ENGINE = module_from_spec(SPEC)
SPEC.loader.exec_module(ENGINE)


def test_brain_boundaries_preserve_object_identity_and_contents():
    payload = {"bid": 2350.25, "rsi": 58.0, "decision": "TRADE", "sl": 2340.25, "tp": 2365.25}
    original = dict(payload)

    for stage in (
        ENGINE.brain_market_perception,
        ENGINE.brain_market_understanding,
        ENGINE.brain_market_reasoning,
        ENGINE.brain_probability_engine,
        ENGINE.brain_expected_value_engine,
        ENGINE.brain_position_intelligence,
        ENGINE.brain_decision_publication,
    ):
        assert stage(payload) is payload
        assert payload == original


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
