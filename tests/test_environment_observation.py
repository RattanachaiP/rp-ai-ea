"""Operator-free governed live-environment observation coverage."""

import json
import os
from pathlib import Path

import pytest

from learning.execution_environment.policy import ENVIRONMENT_DIMENSIONS
from runtime.environment_observation import (
    EnvironmentObservationError,
    GovernedEnvironmentObservationProducer,
)


def _market_state(path: Path, **changes):
    values = {"bid": 2400.0, "spread_points": 20.0, "sequence_id": 42}
    values.update(changes)
    path.write_text(json.dumps(values), encoding="utf-8")
    os.utime(path, None)


def test_producer_measures_complete_ordered_ready_observations(tmp_path):
    path = tmp_path / "market_state.json"
    _market_state(path)

    result = GovernedEnvironmentObservationProducer(
        path, window_seconds=0.02, sample_interval=0.001
    ).collect()

    measured = dict(result.observations)
    assert tuple(measured) == ENVIRONMENT_DIMENSIONS
    assert measured["feed_stability"] == 1.0
    assert measured["price_stream_continuity"] == 1.0
    assert measured["spread_quality"] == 20.0
    assert measured["slippage_expectation"] == 10.0
    assert measured["environment_completeness"] == 1.0
    assert result.captured_at.endswith("Z")


@pytest.mark.parametrize(
    "payload",
    [
        {},
        {"bid": 2400.0, "sequence_id": 1},
        {"bid": 0.0, "spread_points": 20.0, "sequence_id": 1},
        {"bid": 2400.0, "spread_points": "20", "sequence_id": 1},
    ],
)
def test_missing_or_fabrication_requiring_telemetry_fails_closed(tmp_path, payload):
    path = tmp_path / "market_state.json"
    path.write_text(json.dumps(payload), encoding="utf-8")
    with pytest.raises(EnvironmentObservationError, match="ENVIRONMENT_OBSERVATION_INCOMPLETE"):
        GovernedEnvironmentObservationProducer(
            path, window_seconds=0.005, sample_interval=0.001
        ).collect()


def test_missing_market_state_fails_closed(tmp_path):
    with pytest.raises(EnvironmentObservationError, match="ENVIRONMENT_OBSERVATION_INCOMPLETE"):
        GovernedEnvironmentObservationProducer(
            tmp_path / "missing.json", window_seconds=0.005, sample_interval=0.001
        ).collect()
