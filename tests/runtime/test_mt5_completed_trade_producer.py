from dataclasses import asdict, replace
from uuid import uuid4

import pytest

from runtime.completed_trade_event import CompletedTradeEventError, CompletedTradeEventPublisher
from runtime.mt5_completed_trade_producer import (
    MT5CompletedTradeEmissionError,
    MT5CompletedTradeEventProducer,
    MT5CompletedTradeFacts,
)


def facts() -> MT5CompletedTradeFacts:
    return MT5CompletedTradeFacts(
        broker_confirmed_closed=True, final_deal_available=True,
        trade_lifecycle_completed=True, decision_uuid=str(uuid4()),
        execution_context_uuid=str(uuid4()), order_ticket=101, deal_ticket=102,
        position_ticket=103, publication_uuid=str(uuid4()),
        open_time="2026-07-26T10:00:00.000000Z",
        close_time="2026-07-26T10:05:00.000000Z",
        capture_time="2026-07-26T10:05:00.000001Z",
        publication_timestamp="2026-07-26T09:59:56.000000Z",
        consumer_acceptance_timestamp="2026-07-26T09:59:57.000000Z",
        activation_timestamp="2026-07-26T09:59:58.000000Z",
        order_send_timestamp="2026-07-26T09:59:59.000000Z", symbol="XAUUSD",
        direction="SELL", volume=0.13, entry_price=2401.25, exit_price=2398.75,
        exit_reason="DEAL_REASON_TP", stop_loss=2405.0, take_profit=2398.75,
        broker_response_code="10009", account_number=123456,
        server_name="Broker-Live", gross_profit=32.5, net_profit=31.1,
        commission=-1.2, swap=-0.2, maximum_favorable_excursion=35.0,
        maximum_adverse_excursion=2.5, replay_identity=str(uuid4()),
    )


def test_emits_one_canonical_event_with_exact_broker_values() -> None:
    publisher, received = CompletedTradeEventPublisher(), []
    source = facts()
    producer = MT5CompletedTradeEventProducer(publisher)
    producer.subscribe_completed_trade(received.append)
    event = producer.emit_after_completion(source)

    assert received == [event]
    broker_values = asdict(source)
    for marker in ("broker_confirmed_closed", "final_deal_available", "trade_lifecycle_completed"):
        broker_values.pop(marker)
    for name, value in broker_values.items():
        assert getattr(event, name) == value
    assert event.to_canonical_bytes()


@pytest.mark.parametrize(("field", "code"), [
    ("broker_confirmed_closed", "BROKER_CLOSURE_NOT_CONFIRMED"),
    ("final_deal_available", "FINAL_DEAL_NOT_AVAILABLE"),
    ("trade_lifecycle_completed", "TRADE_LIFECYCLE_NOT_COMPLETED"),
])
def test_refuses_emission_before_final_broker_completion(field: str, code: str) -> None:
    publisher, received = CompletedTradeEventPublisher(), []
    publisher.subscribe_completed_trade(received.append)
    with pytest.raises(MT5CompletedTradeEmissionError, match=code):
        MT5CompletedTradeEventProducer(publisher).emit_after_completion(
            replace(facts(), **{field: False})
        )
    assert received == []


def test_duplicate_completion_is_rejected_and_not_reemitted() -> None:
    publisher, received = CompletedTradeEventPublisher(), []
    publisher.subscribe_completed_trade(received.append)
    producer, source = MT5CompletedTradeEventProducer(publisher), facts()
    first = producer.emit_after_completion(source)
    with pytest.raises(CompletedTradeEventError, match="DUPLICATE_COMPLETED_TRADE_EVENT"):
        producer.emit_after_completion(replace(source, capture_time="2026-07-26T10:05:01.000000Z"))
    assert received == [first]


def test_invalid_chronology_fails_closed_without_publication() -> None:
    publisher, received = CompletedTradeEventPublisher(), []
    publisher.subscribe_completed_trade(received.append)
    with pytest.raises(CompletedTradeEventError, match="INVALID_EVENT_TIMESTAMP_SEQUENCE"):
        MT5CompletedTradeEventProducer(publisher).emit_after_completion(
            replace(facts(), close_time="2026-07-26T09:59:00.000000Z")
        )
    assert received == []
