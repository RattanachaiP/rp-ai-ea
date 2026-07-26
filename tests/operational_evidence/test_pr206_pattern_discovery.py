from dataclasses import replace
import runpy

import pytest

from operational_evidence.outcome_attribution import OutcomeAttributionEngine
from operational_evidence.pattern_discovery import (
    PatternDiscoveryConfig, PatternDiscoveryEngine, PatternDiscoveryError,
    PatternRepository,
)
from runtime.completed_trade_event import CompletedTradeEvent
from runtime.live_outcome_capture import LiveOutcomeRecord


_sources = runpy.run_path("tests/operational_evidence/test_outcome_attribution.py")["sources"]


def evidence_batch(count=2, *, net_profit=8.0):
    first_event, first_outcome = _sources(net_profit=net_profit)
    events, outcomes = [], []
    for offset in range(count):
        event_values = first_event.to_dict()
        event_values.update(order_ticket=11 + offset, deal_ticket=12 + offset,
                            position_ticket=13 + offset)
        for key in ("event_uuid", "sha256_digest"):
            event_values.pop(key)
        event = CompletedTradeEvent.create(**event_values)
        outcome_values = first_outcome.to_dict()
        outcome_values.update(order_ticket=11 + offset, deal_ticket=12 + offset,
                              position_ticket=13 + offset, record_uuid="", record_digest="")
        outcome_values["replay_identity_chain"] = tuple(outcome_values["replay_identity_chain"])
        outcome = LiveOutcomeRecord(**outcome_values)
        events.append(event)
        outcomes.append(outcome)
    attributions = [OutcomeAttributionEngine().attribute(event, outcome)
                    for event, outcome in zip(events, outcomes)]
    return attributions, events, outcomes


def test_discovery_is_deterministic_and_evidence_only():
    inputs = evidence_batch()
    engine = PatternDiscoveryEngine(PatternDiscoveryConfig(minimum_sample_count=2))
    first = engine.discover(*inputs)
    second = engine.discover(*inputs)
    assert first == second
    assert {item.pattern_type for item in first} == {
        "ENTRY_TIMING_CLUSTER", "EXIT_TIMING_CLUSTER", "LATENCY_DISTRIBUTION",
        "MANUAL_INTERVENTION_FREQUENCY", "REPLAY_CONSISTENCY",
        "STOP_LOSS_DISTRIBUTION", "TAKE_PROFIT_DISTRIBUTION",
        "TRADE_DURATION_DISTRIBUTION", "WINNING_TRADE_CHARACTERISTICS",
    }
    assert all(item.sample_count == 2 and item.passive_observation_only for item in first)
    assert all(item.configured_confidence_level == 0.95 for item in first)
    assert all(len(item.sha256_digest) == 64 for item in first)


def test_configuration_is_identity_bound_but_not_reported_as_statistical_result():
    inputs = evidence_batch()
    baseline_engine = PatternDiscoveryEngine(
        PatternDiscoveryConfig(minimum_sample_count=2, confidence_level=0.95))
    changed_engine = PatternDiscoveryEngine(
        PatternDiscoveryConfig(minimum_sample_count=2, confidence_level=0.9))
    baseline = baseline_engine.discover(*inputs)
    replayed = baseline_engine.discover(*inputs)
    changed = changed_engine.discover(*inputs)
    assert baseline == replayed
    assert all(item.configured_confidence_level == 0.95 for item in baseline)
    assert all(item.configured_confidence_level == 0.9 for item in changed)
    assert [item.pattern_uuid for item in baseline] != [item.pattern_uuid for item in changed]
    assert [item.sha256_digest for item in baseline] != [item.sha256_digest for item in changed]


def test_losing_characteristics_are_emitted_at_the_sample_threshold():
    patterns = PatternDiscoveryEngine(
        PatternDiscoveryConfig(minimum_sample_count=2)).discover(
            *evidence_batch(net_profit=-8.0))
    losing = [item for item in patterns
              if item.pattern_type == "LOSING_TRADE_CHARACTERISTICS"]
    assert len(losing) == 1
    assert losing[0].sample_count == 2


def test_insufficient_integrity_replay_and_duplicates_fail_closed():
    attributions, events, outcomes = evidence_batch()
    engine = PatternDiscoveryEngine(PatternDiscoveryConfig(minimum_sample_count=2))
    with pytest.raises(PatternDiscoveryError, match="INSUFFICIENT_SAMPLE_SIZE"):
        engine.discover(attributions[:1], events[:1], outcomes[:1])
    with pytest.raises(PatternDiscoveryError, match="DUPLICATE_SOURCE_ATTRIBUTION"):
        engine.discover([attributions[0], attributions[0]], events, outcomes)
    with pytest.raises(PatternDiscoveryError, match="SOURCE_ATTRIBUTION_INTEGRITY_FAILURE"):
        engine.discover(attributions, events[:1], outcomes)


def test_repository_is_atomic_append_only_and_duplicate_rejecting(tmp_path):
    patterns = PatternDiscoveryEngine(
        PatternDiscoveryConfig(minimum_sample_count=2)).discover(*evidence_batch())
    repository = PatternRepository(tmp_path)
    path = repository.append(patterns[0])
    assert path.read_bytes().endswith(b"\n")
    with pytest.raises(PatternDiscoveryError, match="DUPLICATE_PATTERN_IDENTITY"):
        repository.append(patterns[0])
    with pytest.raises(PatternDiscoveryError, match="PATTERN_UUID_MISMATCH"):
        replace(patterns[0], configured_confidence_level=0.9)
