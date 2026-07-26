"""PR201 regression coverage for immutable live outcome capture."""
from dataclasses import replace
import json
from uuid import uuid4

import pytest

from runtime.execution_contract import CONTRACT_VERSION, ExecutionContext
from runtime.completed_trade_event import CompletedTradeEvent
from runtime.live_outcome_capture import (
    BrokerCompletedTrade,
    LiveOutcomeCapture,
    LiveOutcomeCaptureError,
    LiveOutcomeRepository,
)


def context() -> ExecutionContext:
    return ExecutionContext.create(execution_uuid=str(uuid4()), decision_uuid=str(uuid4()),
        package_uuid=str(uuid4()), replay_uuid=str(uuid4()), execution_confidence=.8,
        readiness_state="READY", environment_state="READY", feasibility_state="FEASIBLE",
        policy_version="1", engine_version="1", advisory_only=True,
        timestamp="2026-07-26T10:00:00.000000Z", contract_version=CONTRACT_VERSION)


def completion(source: ExecutionContext, **changes) -> CompletedTradeEvent:
    values = dict(decision_uuid=source.decision_uuid, execution_context_uuid=source.execution_uuid,
        publication_uuid=str(uuid4()), order_ticket=11, deal_ticket=12, position_ticket=13,
        publication_timestamp="2026-07-26T10:00:01.000000Z",
        consumer_acceptance_timestamp="2026-07-26T10:00:02.000000Z",
        activation_timestamp="2026-07-26T10:00:03.000000Z",
        order_send_timestamp="2026-07-26T10:00:04.000000Z",
        position_open_timestamp="2026-07-26T10:00:04.250000Z",
        position_close_timestamp="2026-07-26T10:05:04.250000Z", symbol="XAUUSD",
        direction="BUY", volume=.1, entry_price=2400, exit_price=2402, stop_loss=2395,
        take_profit=2410, exit_reason="TAKE_PROFIT", broker_response_code="10009",
        broker_execution_status="COMPLETED", account_number=123456, server_name="Broker-Live",
        gross_profit=20, net_profit=18.5, commission=-1, swap=-.5,
        maximum_favorable_excursion=25, maximum_adverse_excursion=None,
        replay_uuid=source.replay_uuid, parent_decision_uuid=source.decision_uuid,
        parent_execution_context_uuid=source.execution_uuid)
    values.update(changes)
    broker = BrokerCompletedTrade(**values)
    return CompletedTradeEvent.create(decision_uuid=broker.decision_uuid,
        execution_context_uuid=broker.execution_context_uuid, order_ticket=broker.order_ticket,
        deal_ticket=broker.deal_ticket, position_ticket=broker.position_ticket,
        publication_uuid=broker.publication_uuid,
        open_time=broker.position_open_timestamp, close_time=broker.position_close_timestamp,
        capture_time="2026-07-26T10:05:05.000000Z",
        publication_timestamp=broker.publication_timestamp,
        consumer_acceptance_timestamp=broker.consumer_acceptance_timestamp,
        activation_timestamp=broker.activation_timestamp,
        order_send_timestamp=broker.order_send_timestamp, symbol=broker.symbol,
        direction=broker.direction, volume=broker.volume, entry_price=broker.entry_price,
        exit_price=broker.exit_price, exit_reason=broker.exit_reason,
        stop_loss=broker.stop_loss, take_profit=broker.take_profit,
        broker_response_code=broker.broker_response_code, account_number=broker.account_number,
        server_name=broker.server_name,
        gross_profit=broker.gross_profit, net_profit=broker.net_profit,
        commission=broker.commission, swap=broker.swap,
        maximum_favorable_excursion=broker.maximum_favorable_excursion,
        maximum_adverse_excursion=broker.maximum_adverse_excursion,
        replay_identity=broker.replay_uuid)


def test_capture_writes_complete_canonical_authoritative_record(tmp_path):
    source = context()
    record = LiveOutcomeCapture(LiveOutcomeRepository(tmp_path)).capture(
        completion(source), source, captured_at="2026-07-26T10:05:05.000000Z")
    assert record.execution_latency_seconds == .25
    assert record.trade_duration_seconds == 300
    assert record.replay_identity_chain == (source.replay_uuid, source.decision_uuid, source.execution_uuid)
    path = tmp_path / "live_outcomes" / f"live_outcome_{record.record_uuid}.json"
    wire = path.read_bytes()
    assert wire.endswith(b"\n")
    assert json.loads(wire)["record_digest"] == record.record_digest
    assert json.dumps(json.loads(wire), sort_keys=True, separators=(",", ":")).encode() + b"\n" == wire


def test_duplicate_capture_fails_instead_of_modifying_evidence(tmp_path):
    source = context()
    capture = LiveOutcomeCapture(LiveOutcomeRepository(tmp_path))
    completed = completion(source)
    capture.capture(completed, source, captured_at="2026-07-26T10:05:05.000000Z")
    with pytest.raises(LiveOutcomeCaptureError, match="DUPLICATE_RECORD"):
        capture.capture(completed, source, captured_at="2026-07-26T10:05:05.000000Z")
    with pytest.raises(LiveOutcomeCaptureError, match="CAPTURE_TIMESTAMP_MISMATCH"):
        capture.capture(completed, source, captured_at="2026-07-26T10:05:06.000000Z")


@pytest.mark.parametrize("changes, error", [
    ({"order_ticket": 0}, "MISSING_TICKET"),
    ({"broker_execution_status": "PENDING"}, "BROKER_CONFIRMATION_UNAVAILABLE"),
    ({"publication_uuid": None}, "BROKEN_PUBLICATION_IDENTITY"),
])
def test_fail_conditions_are_closed(tmp_path, changes, error):
    source = context()
    with pytest.raises(LiveOutcomeCaptureError, match=error):
        completion(source, **changes)


def test_broken_execution_lineage_and_corruption_fail_closed(tmp_path):
    source = context()
    with pytest.raises(LiveOutcomeCaptureError, match="BROKEN_IDENTITY_CHAIN"):
        LiveOutcomeCapture(LiveOutcomeRepository(tmp_path)).capture(
            completion(source, execution_context_uuid=str(uuid4())), source,
            captured_at="2026-07-26T10:05:05.000000Z")
    record = LiveOutcomeCapture(LiveOutcomeRepository(tmp_path)).capture(
        completion(source), source, captured_at="2026-07-26T10:05:05.000000Z")
    with pytest.raises(LiveOutcomeCaptureError, match="RECORD_DIGEST_MISMATCH"):
        replace(record, net_profit=999)


def test_publication_and_excursions_may_be_unavailable(tmp_path):
    source = context()
    record = LiveOutcomeCapture(LiveOutcomeRepository(tmp_path)).capture(
        completion(source, publication_uuid=None, publication_timestamp=None,
                   maximum_favorable_excursion=None, maximum_adverse_excursion=None), source,
        captured_at="2026-07-26T10:05:05.000000Z")
    assert record.publication_uuid is None and record.maximum_favorable_excursion is None


def test_broker_facts_are_preserved_without_synthetic_placeholders(tmp_path):
    source = context()
    completed = completion(source, stop_loss=0, take_profit=0,
                           maximum_favorable_excursion=None,
                           maximum_adverse_excursion=None)
    record = LiveOutcomeCapture(LiveOutcomeRepository(tmp_path)).capture(
        completed, source, captured_at=completed.capture_time)
    wire = json.loads((tmp_path / "live_outcomes" /
                       f"live_outcome_{record.record_uuid}.json").read_bytes())

    assert wire["account_number"] == 123456
    assert wire["server_name"] == "Broker-Live"
    assert wire["stop_loss"] == 0.0 and completed.stop_loss == 0.0
    assert wire["take_profit"] == 0.0 and completed.take_profit == 0.0
    assert wire["execution_latency_seconds"] == .25
    assert wire["order_send_timestamp"] == "2026-07-26T10:00:04.000000Z"
    assert wire["order_send_timestamp"] != wire["position_open_timestamp"]
    assert wire["broker_response_code"] == "10009"
    assert wire["maximum_favorable_excursion"] is None
    assert wire["maximum_adverse_excursion"] is None
    assert CompletedTradeEvent(**completed.to_dict()) == completed
