"""PR162 regression coverage for passive Decision Outcome Observation."""
from dataclasses import replace
from uuid import uuid4

import pytest

from runtime.decision_knowledge_interface import DecisionKnowledgeInterface
from runtime.decision_knowledge_observation import DecisionKnowledgeObserver
from runtime.decision_outcome_observation import (
    CompletedTradeResult,
    DecisionOutcomeObservationError,
    DecisionOutcomeObservationRepository,
    DecisionOutcomeObserver,
)
from runtime.knowledge_applicability import KnowledgeApplicabilityEngine
from tests.learning.test_knowledge_applicability import context, descriptor, snapshot


def observation():
    report = KnowledgeApplicabilityEngine().evaluate(snapshot((descriptor("knowledge-a"),)), context())
    return DecisionKnowledgeObserver().observe(
        DecisionKnowledgeInterface.load(report), decision_uuid=str(uuid4()), decision_cycle_uuid=str(uuid4()),
        decision_digest="a" * 64, observation_timestamp="2026-01-01T00:00:00.000000Z")


def result(record, **changes):
    values = dict(decision_uuid=record.decision_uuid, decision_observation_uuid=record.observation_uuid,
        position_ticket=81234, symbol="XAUUSD", direction="BUY", entry_price=2500.0, exit_price=2501.0,
        entry_time="2026-01-01T00:00:00.000000Z", exit_time="2026-01-01T00:03:00.000000Z",
        gross_profit=10.0, net_profit=8.5, commission=-1.0, swap=-0.5,
        maximum_favorable_excursion=12.0, maximum_adverse_excursion=3.0, exit_reason="TAKE_PROFIT")
    values.update(changes)
    return CompletedTradeResult(**values)


def test_completed_trade_creates_deterministic_immutable_outcome():
    source = observation()
    trade = result(source)
    first = DecisionOutcomeObserver().observe(trade, source)
    second = DecisionOutcomeObserver().observe(trade, source)
    assert first == second
    assert first.observation_uuid == second.observation_uuid
    assert first.holding_time_seconds == 180
    assert first.decision_observation_uuid == source.observation_uuid


@pytest.mark.parametrize("gross, net, reason", [
    (10.0, 8.5, "TAKE_PROFIT"), (-10.0, -11.5, "STOP_LOSS"), (0.0, 0.0, "MANUAL_CLOSE"),
    (2.0, 1.0, "TRAILING_STOP"), (1.0, 0.5, "PARTIAL_CLOSE"),
])
def test_outcomes_cover_trade_results_and_exit_reasons(gross, net, reason):
    source = observation()
    record = DecisionOutcomeObserver().observe(result(source, gross_profit=gross, net_profit=net, exit_reason=reason), source)
    assert record.gross_profit == gross and record.net_profit == net and record.exit_reason == reason


def test_append_only_atomic_replay_safe_storage(tmp_path):
    source = observation()
    observer = DecisionOutcomeObserver(DecisionOutcomeObservationRepository(tmp_path))
    record = observer.observe(result(source), source)
    path = tmp_path / "decision_outcomes" / f"outcome_{record.observation_uuid}.json"
    assert path.exists() and observer.observe(result(source), source) == record
    path.write_text("tampered\n", encoding="utf-8")
    with pytest.raises(FileExistsError, match="APPEND_ONLY"):
        observer.observe(result(source), source)


def test_fails_closed_for_invalid_trade_and_correlation():
    source = observation()
    with pytest.raises(DecisionOutcomeObservationError, match="INVALID_POSITION_TICKET"):
        result(source, position_ticket=0)
    with pytest.raises(DecisionOutcomeObservationError, match="INVALID_EXIT_REASON"):
        result(source, exit_reason="BROKER_UNKNOWN")
    with pytest.raises(DecisionOutcomeObservationError, match="INVALID_TIME"):
        result(source, exit_time="2025-12-31T23:59:59.000000Z")
    with pytest.raises(DecisionOutcomeObservationError, match="DECISION_CORRELATION"):
        DecisionOutcomeObserver().observe(result(source, decision_uuid=str(uuid4())), source)
    with pytest.raises(DecisionOutcomeObservationError, match="OBSERVATION_CORRELATION"):
        DecisionOutcomeObserver().observe(result(source, decision_observation_uuid=str(uuid4())), source)


def test_mae_mfe_and_holding_time_are_integrity_bound():
    source = observation()
    record = DecisionOutcomeObserver().observe(result(source), source)
    with pytest.raises(DecisionOutcomeObservationError, match="INVALID_HOLDING_TIME"):
        replace(record, holding_time_seconds=1)
    with pytest.raises(DecisionOutcomeObservationError, match="INVALID_TRADE_RESULT"):
        result(source, maximum_adverse_excursion=-1)
