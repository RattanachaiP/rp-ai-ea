"""PR204 production MT5 host producer for canonical completed-trade events.

This module is deliberately a post-completion adapter.  It accepts only a
complete set of final MT5/broker facts and exposes no broker, order, position,
or exit operation.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Callable

from runtime.completed_trade_event import CompletedTradeEvent, CompletedTradeEventPublisher


class MT5CompletedTradeEmissionError(ValueError):
    """The MT5 host has not supplied a final broker-confirmed completion."""


@dataclass(frozen=True, slots=True)
class MT5CompletedTradeFacts:
    """Unmodified final facts available at the MT5 host boundary.

    The three lifecycle markers are host assertions rather than event fields.
    Requiring each marker prevents an order acknowledgement, an intermediate
    deal, or a still-open position from being mistaken for completion.
    """

    broker_confirmed_closed: bool
    final_deal_available: bool
    trade_lifecycle_completed: bool
    decision_uuid: str
    execution_context_uuid: str
    order_ticket: int
    deal_ticket: int
    position_ticket: int
    publication_uuid: str | None
    open_time: str
    close_time: str
    capture_time: str
    publication_timestamp: str | None
    consumer_acceptance_timestamp: str
    activation_timestamp: str
    order_send_timestamp: str
    symbol: str
    direction: str
    volume: float
    entry_price: float
    exit_price: float
    exit_reason: str
    stop_loss: float
    take_profit: float
    broker_response_code: str
    account_number: int
    server_name: str
    gross_profit: float
    net_profit: float
    commission: float
    swap: float
    maximum_favorable_excursion: float | None
    maximum_adverse_excursion: float | None
    replay_identity: str


class MT5CompletedTradeEventProducer:
    """Sole canonical-event producer invoked by the production MT5 host."""

    def __init__(self, publisher: CompletedTradeEventPublisher) -> None:
        if type(publisher) is not CompletedTradeEventPublisher:
            raise TypeError("COMPLETED_TRADE_EVENT_PUBLISHER_REQUIRED")
        self._publisher = publisher

    def subscribe_completed_trade(
        self, observer: Callable[[CompletedTradeEvent], None]
    ) -> None:
        """Expose the existing passive subscription boundary to consumers."""
        self._publisher.subscribe_completed_trade(observer)

    def emit_after_completion(self, facts: MT5CompletedTradeFacts) -> CompletedTradeEvent:
        """Validate finality, create the canonical value, and publish it once."""
        if type(facts) is not MT5CompletedTradeFacts:
            raise TypeError("MT5_COMPLETED_TRADE_FACTS_REQUIRED")
        if facts.broker_confirmed_closed is not True:
            raise MT5CompletedTradeEmissionError("BROKER_CLOSURE_NOT_CONFIRMED")
        if facts.final_deal_available is not True:
            raise MT5CompletedTradeEmissionError("FINAL_DEAL_NOT_AVAILABLE")
        if facts.trade_lifecycle_completed is not True:
            raise MT5CompletedTradeEmissionError("TRADE_LIFECYCLE_NOT_COMPLETED")

        values = asdict(facts)
        values.pop("broker_confirmed_closed")
        values.pop("final_deal_available")
        values.pop("trade_lifecycle_completed")
        event = CompletedTradeEvent.create(**values)
        self._publisher.publish(event)
        return event


__all__ = [
    "MT5CompletedTradeEmissionError",
    "MT5CompletedTradeEventProducer",
    "MT5CompletedTradeFacts",
]
