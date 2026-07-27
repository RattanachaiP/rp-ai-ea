"""Governed live-environment observation policy regression coverage."""
import json
from pathlib import Path
import pytest
from learning.execution_environment.policy import ENVIRONMENT_DIMENSIONS
from runtime.environment_observation import (
    EXPECTED_PRODUCER, EXPECTED_PRODUCER_VERSION, EXPECTED_SCHEMA_VERSION,
    EXPECTED_SOURCE_UUID, EnvironmentObservationError, EnvironmentObservationPolicy,
    GovernedEnvironmentObservationProducer,
)


def payload(sequence=1, heartbeat=1000.0, **changes):
    value = {"symbol": "XAUUSD", "producer": EXPECTED_PRODUCER,
             "producer_version": EXPECTED_PRODUCER_VERSION,
             "schema_version": EXPECTED_SCHEMA_VERSION, "source_uuid": EXPECTED_SOURCE_UUID,
             "heartbeat_unix": heartbeat, "sequence_id": sequence, "bid": 2400.0,
             "spread_points": 20.0, "market_session_quality": 0.9,
             "slippage_expectation": 10.0, "market_liquidity_quality": 0.9}
    value.update(changes)
    return value


class Feed:
    def __init__(self, path: Path, states):
        self.path, self.states, self.index, self.elapsed = path, states, 0, 0.0
        self.write()
    def write(self):
        state = self.states[min(self.index, len(self.states) - 1)]
        self.path.write_text(state if isinstance(state, str) else json.dumps(state))
    def sleep(self, seconds):
        self.elapsed += seconds
        self.index += 1
        self.write()
    def wall(self): return 1000.0 + self.elapsed
    def monotonic(self): return self.elapsed


def collect(tmp_path, states, *, policy=None):
    feed = Feed(tmp_path / "market_state.json", states)
    return GovernedEnvironmentObservationProducer(
        feed.path, window_seconds=0.03, sample_interval=0.01, policy=policy,
        clock=feed.wall, monotonic=feed.monotonic, sleep=feed.sleep).collect()


def test_policy_based_derivation_is_deterministic_and_direct(tmp_path):
    states = [payload(1, 999.9), payload(2, 999.95, spread_points=50.0,
              slippage_expectation=30.0, market_session_quality=0.8,
              market_liquidity_quality=0.8), payload(3, 1000.0), payload(3, 1000.0)]
    first = collect(tmp_path, states)
    second = collect(tmp_path, states)
    values = dict(first.observations)
    assert tuple(values) == ENVIRONMENT_DIMENSIONS
    assert values["spread_quality"] == 50.0
    assert values["slippage_expectation"] == 30.0
    assert values["market_session_quality"] == 0.8
    assert values["market_liquidity_quality"] == 0.8
    assert first.observations == second.observations
    assert first.observation_policy_uuid == second.observation_policy_uuid
    assert first.observation_policy_digest == second.observation_policy_digest
    assert first.unique_sequence_ids == (1, 2, 3)


@pytest.mark.parametrize("heartbeat,error", [(990.0, "HEARTBEAT_STALE"), (1001.0, "HEARTBEAT_FUTURE")])
def test_stale_and_future_heartbeat_fail_closed(tmp_path, heartbeat, error):
    with pytest.raises(EnvironmentObservationError, match=error):
        collect(tmp_path, [payload(1, heartbeat)])


@pytest.mark.parametrize("sequences,error", [([1, 1, 1, 1], "INSUFFICIENT_UNIQUE"),
                                               ([3, 2, 1, 1], "SEQUENCE_NOT_PROGRESSING")])
def test_unchanged_and_decreasing_sequences_fail_closed(tmp_path, sequences, error):
    states = [payload(seq, 999.9 + i * .01) for i, seq in enumerate(sequences)]
    if len(set(sequences)) == 1:
        states = [states[0]] * len(states)
    elif sequences[-1] == sequences[-2]:
        states[-1] = states[-2]
    with pytest.raises(EnvironmentObservationError, match=error): collect(tmp_path, states)


def test_configured_minimum_unique_observations_is_enforced(tmp_path):
    policy = EnvironmentObservationPolicy(minimum_unique_observations=4)
    with pytest.raises(EnvironmentObservationError, match="INSUFFICIENT_UNIQUE"):
        collect(tmp_path, [payload(1), payload(2), payload(3), payload(3)], policy=policy)


def test_malformed_atomic_replacement_is_tracked_not_counted_as_observation(tmp_path):
    result = collect(tmp_path, [payload(1), "{", payload(2, 1000.01), payload(3, 1000.02)])
    assert result.malformed_reads == 1
    assert result.successful_reads == 3
    assert result.unique_sequence_ids == (1, 2, 3)
    assert dict(result.observations)["feed_stability"] == 0.75


@pytest.mark.parametrize("changes", [{"symbol": "EURUSD"}, {"producer": "OTHER"},
                                      {"producer_version": "V2"}, {"schema_version": "2.0"},
                                      {"source_uuid": "00000000-0000-0000-0000-000000000000"}])
def test_wrong_source_identity_fails_closed(tmp_path, changes):
    with pytest.raises(EnvironmentObservationError, match="SOURCE_IDENTITY_MISMATCH"):
        collect(tmp_path, [payload(**changes)])


def test_no_fabricated_slippage_evidence(tmp_path):
    state = payload(); state.pop("slippage_expectation")
    with pytest.raises(EnvironmentObservationError, match="INSUFFICIENT_UNIQUE"):
        collect(tmp_path, [state])


def test_policy_records_definitions_thresholds_and_provenance():
    policy = EnvironmentObservationPolicy()
    assert tuple(row[0] for row in policy.dimensions) == ENVIRONMENT_DIMENSIONS
    assert all(len(row) == 5 for row in policy.dimensions)
    assert len(policy.policy_digest) == 64
    assert policy.policy_uuid
