from dataclasses import replace
from uuid import uuid4

import pytest

from operational_evidence.outcome_attribution import (
    OutcomeAttribution,
    OutcomeAttributionEngine,
    OutcomeAttributionError,
    OutcomeAttributionRepository,
)
from runtime.completed_trade_event import CompletedTradeEvent
from runtime.live_outcome_capture import LiveOutcomeRecord


def sources(*, net_profit: float = 8.0, exit_reason: str = "TAKE_PROFIT"):
    replay, decision, execution = (str(uuid4()) for _ in range(3))
    event = CompletedTradeEvent.create(
        decision_uuid=decision, execution_context_uuid=execution,
        order_ticket=11, deal_ticket=12, position_ticket=13,
        publication_uuid=None, publication_timestamp=None,
        consumer_acceptance_timestamp="2026-07-26T10:00:00.000000Z",
        activation_timestamp="2026-07-26T10:00:01.000000Z",
        order_send_timestamp="2026-07-26T10:00:02.000000Z",
        open_time="2026-07-26T10:00:03.000000Z",
        close_time="2026-07-26T10:05:03.000000Z",
        capture_time="2026-07-26T10:05:04.000000Z", symbol="XAUUSD",
        direction="BUY", volume=0.1, entry_price=2300, exit_price=2310,
        exit_reason=exit_reason, stop_loss=2290, take_profit=2310,
        broker_response_code="DONE", account_number=99, server_name="test",
        gross_profit=10, net_profit=net_profit, commission=-2, swap=0,
        maximum_favorable_excursion=11, maximum_adverse_excursion=2,
        replay_identity=replay)
    record = LiveOutcomeRecord(
        decision_uuid=decision, execution_context_uuid=execution,
        publication_uuid=None, order_ticket=11, deal_ticket=12, position_ticket=13,
        runtime_timestamp="2026-07-26T09:59:59.000000Z", publication_timestamp=None,
        consumer_acceptance_timestamp="2026-07-26T10:00:00.000000Z",
        activation_timestamp="2026-07-26T10:00:01.000000Z",
        order_send_timestamp="2026-07-26T10:00:02.000000Z",
        position_open_timestamp="2026-07-26T10:00:03.000000Z",
        position_close_timestamp="2026-07-26T10:05:03.000000Z",
        symbol="XAUUSD", direction="BUY", volume=0.1, entry_price=2300,
        exit_price=2310, stop_loss=2290, take_profit=2310,
        exit_reason=exit_reason, execution_latency_seconds=1,
        broker_response_code="DONE", broker_execution_status="COMPLETED",
        account_number=99, server_name="test", gross_profit=10,
        net_profit=net_profit, commission=-2, swap=0, trade_duration_seconds=300,
        maximum_favorable_excursion=11, maximum_adverse_excursion=2,
        replay_identity_chain=(replay, decision, execution),
        parent_decision_uuid=decision, parent_execution_context_uuid=execution,
        captured_at="2026-07-26T10:05:04.000000Z")
    return event, record


def test_deterministic_complete_fact_attribution():
    event, record = sources()
    first = OutcomeAttributionEngine().attribute(event, record)
    second = OutcomeAttributionEngine().attribute(event, record)
    assert first == second
    assert first.classification == "PROFITABLE"
    assert first.parent_completed_trade_event_uuid == event.event_uuid
    assert first.timestamp == event.capture_time
    assert len(first.supporting_evidence) == 10
    assert first.supporting_evidence[0].observation == "UNAVAILABLE"
    assert first.supporting_evidence[4].to_dict()["facts"]["exit_reason_indicates_take_profit"] is True
    assert first.supporting_evidence[-1].to_dict()["facts"]["replay_identity_verified"] is True
    assert OutcomeAttribution.from_dict(first.to_dict()) == first


@pytest.mark.parametrize(("profit", "expected"), [(-0.01, "LOSS"), (0, "BREAKEVEN")])
def test_classification_is_derived_only_from_observed_net_result(profit, expected):
    event, record = sources(net_profit=profit)
    assert OutcomeAttributionEngine().attribute(event, record).classification == expected


def test_manual_intervention_is_only_reported_when_exit_evidence_says_manual():
    event, record = sources(exit_reason="MANUAL_CLOSE")
    attribution = OutcomeAttributionEngine().attribute(event, record)
    manual = attribution.supporting_evidence[5]
    assert manual.observation == "OBSERVED"
    assert manual.to_dict()["facts"]["exit_reason_indicates_manual"] is True


def test_mt5_deal_reason_tp_is_attributed_as_take_profit():
    event, record = sources(exit_reason="DEAL_REASON_TP")
    take_profit = OutcomeAttributionEngine().attribute(event, record).supporting_evidence[4]
    assert take_profit.to_dict()["facts"] == {
        "configured_take_profit": event.take_profit,
        "exit_reason": "DEAL_REASON_TP",
        "exit_reason_indicates_take_profit": True,
    }


def test_mt5_deal_reason_sl_is_attributed_as_stop_loss():
    event, record = sources(exit_reason="DEAL_REASON_SL")
    stop_loss = OutcomeAttributionEngine().attribute(event, record).supporting_evidence[3]
    assert stop_loss.to_dict()["facts"] == {
        "configured_stop_loss": event.stop_loss,
        "exit_reason": "DEAL_REASON_SL",
        "exit_reason_indicates_stop_loss": True,
    }


def test_mismatched_operational_evidence_and_replay_fail_closed():
    event, record = sources()
    other_event, _ = sources()
    with pytest.raises(OutcomeAttributionError, match="OPERATIONAL_EVIDENCE_MISMATCH"):
        OutcomeAttributionEngine().attribute(other_event, record)
    broken_replay = replace(record,
                            replay_identity_chain=(str(uuid4()), event.decision_uuid,
                                                   event.execution_context_uuid),
                            record_digest="", record_uuid="")
    with pytest.raises(OutcomeAttributionError, match="REPLAY_IDENTITY_MISMATCH"):
        OutcomeAttributionEngine().attribute(event, broken_replay)


def test_repository_is_canonical_append_only_and_duplicate_rejecting(tmp_path):
    event, record = sources()
    attribution = OutcomeAttributionEngine().attribute(event, record)
    repository = OutcomeAttributionRepository(tmp_path)
    path = repository.append(attribution)
    assert path.read_bytes().endswith(b"\n")
    with pytest.raises(OutcomeAttributionError, match="DUPLICATE_ATTRIBUTION"):
        repository.append(attribution)
    with pytest.raises(OutcomeAttributionError, match="ATTRIBUTION_DIGEST_MISMATCH"):
        replace(attribution, classification="LOSS")
