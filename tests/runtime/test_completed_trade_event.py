from dataclasses import FrozenInstanceError, replace
from uuid import uuid4

import pytest

from runtime.completed_trade_event import (
    CompletedTradeEvent, CompletedTradeEventError, CompletedTradeEventPublisher,
)


def event(**changes: object) -> CompletedTradeEvent:
    values = dict(decision_uuid=str(uuid4()), execution_context_uuid=str(uuid4()),
        order_ticket=11, deal_ticket=12, position_ticket=13,
        open_time="2026-07-26T10:00:00.000000Z", close_time="2026-07-26T10:05:00.000000Z",
        capture_time="2026-07-26T10:05:01.000000Z", symbol="XAUUSD", direction="BUY",
        volume=.1, entry_price=2400, exit_price=2402, exit_reason="TAKE_PROFIT",
        gross_profit=20, net_profit=18.5, commission=-1, swap=-.5,
        replay_identity=str(uuid4()))
    values.update(changes)
    return CompletedTradeEvent.create(**values)


def test_event_is_immutable_canonical_and_integrity_bound() -> None:
    completed = event()
    assert completed.to_canonical_bytes() == completed.to_canonical_bytes()
    assert CompletedTradeEvent(**completed.to_dict()) == completed
    with pytest.raises(FrozenInstanceError):
        completed.symbol = "EURUSD"  # type: ignore[misc]
    with pytest.raises(CompletedTradeEventError, match="EVENT_DIGEST_MISMATCH"):
        replace(completed, net_profit=999)


def test_publisher_emits_once_and_rejects_duplicate() -> None:
    publisher, received = CompletedTradeEventPublisher(), []
    publisher.subscribe_completed_trade(received.append)
    completed = event()
    publisher.publish(completed)
    with pytest.raises(CompletedTradeEventError, match="DUPLICATE_COMPLETED_TRADE_EVENT"):
        publisher.publish(completed)
    assert received == [completed]


@pytest.mark.parametrize("changes", [
    {"close_time": "2026-07-26T09:59:00.000000Z"}, {"order_ticket": 0},
    {"direction": "HOLD"}, {"volume": float("nan")},
])
def test_invalid_event_fails_closed(changes: dict[str, object]) -> None:
    with pytest.raises(CompletedTradeEventError):
        event(**changes)
