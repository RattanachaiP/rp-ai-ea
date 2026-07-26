"""PR202 production post-completion integration verification."""
from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from uuid import uuid4

from operational_evidence.production_outcome_capture import (
    CaptureDisposition,
    ProductionOutcomeCaptureIntegration,
)
from runtime.execution_contract import CONTRACT_VERSION, ExecutionContext
from runtime.completed_trade_event import CompletedTradeEvent
from runtime.live_outcome_capture import BrokerCompletedTrade, LiveOutcomeCapture, LiveOutcomeRepository


class ProductionLifecycle:
    def __init__(self) -> None:
        self.observer: Callable[[CompletedTradeEvent], None] | None = None
        self.events: list[str] = []

    def subscribe_completed_trade(self, observer: Callable[[CompletedTradeEvent], None]) -> None:
        assert self.observer is None
        self.observer = observer

    def broker_closes_and_executor_finishes(self, trade: CompletedTradeEvent) -> None:
        self.events.extend(["BROKER_CONFIRMED", "RESULT_FINALIZED", "AUTHORITY_COMPLETED"])
        assert self.observer is not None
        self.observer(trade)
        self.events.append("PRODUCER_RETURNED")


def context() -> ExecutionContext:
    return ExecutionContext.create(
        execution_uuid=str(uuid4()), decision_uuid=str(uuid4()), package_uuid=str(uuid4()),
        replay_uuid=str(uuid4()), execution_confidence=.8, readiness_state="READY",
        environment_state="READY", feasibility_state="FEASIBLE", policy_version="1",
        engine_version="1", advisory_only=True, timestamp="2026-07-26T10:00:00.000000Z",
        contract_version=CONTRACT_VERSION,
    )


def completion(source: ExecutionContext, **changes: object) -> CompletedTradeEvent:
    values: dict[str, object] = {
        "decision_uuid": source.decision_uuid, "execution_context_uuid": source.execution_uuid,
        "publication_uuid": str(uuid4()), "order_ticket": 11, "deal_ticket": 12,
        "position_ticket": 13, "publication_timestamp": "2026-07-26T10:00:01.000000Z",
        "consumer_acceptance_timestamp": "2026-07-26T10:00:02.000000Z",
        "activation_timestamp": "2026-07-26T10:00:03.000000Z",
        "order_send_timestamp": "2026-07-26T10:00:04.000000Z",
        "position_open_timestamp": "2026-07-26T10:00:04.250000Z",
        "position_close_timestamp": "2026-07-26T10:05:04.250000Z", "symbol": "XAUUSD",
        "direction": "BUY", "volume": .1, "entry_price": 2400, "exit_price": 2402,
        "stop_loss": 2395, "take_profit": 2410, "exit_reason": "TAKE_PROFIT",
        "broker_response_code": "10009", "broker_execution_status": "COMPLETED",
        "account_number": 123456, "server_name": "Broker-Live", "gross_profit": 20,
        "net_profit": 18.5, "commission": -1, "swap": -.5,
        "maximum_favorable_excursion": 25, "maximum_adverse_excursion": None,
        "replay_uuid": source.replay_uuid, "parent_decision_uuid": source.decision_uuid,
        "parent_execution_context_uuid": source.execution_uuid,
    }
    values.update(changes)
    broker = BrokerCompletedTrade(**values)  # type: ignore[arg-type]
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


def integration(tmp_path: Path, lifecycle: ProductionLifecycle, source: ExecutionContext, results: list):
    return ProductionOutcomeCaptureIntegration(
        lifecycle, LiveOutcomeCapture(LiveOutcomeRepository(tmp_path)), source,
        clock=lambda: "2026-07-26T10:05:05.000000Z", result_observer=results.append,
    )


def test_automatic_capture_occurs_only_after_completed_lifecycle(tmp_path: Path) -> None:
    lifecycle, source, results = ProductionLifecycle(), context(), []
    integration(tmp_path, lifecycle, source, results)
    assert not list(tmp_path.rglob("*.json"))

    lifecycle.broker_closes_and_executor_finishes(completion(source))

    assert lifecycle.events == ["BROKER_CONFIRMED", "RESULT_FINALIZED", "AUTHORITY_COMPLETED", "PRODUCER_RETURNED"]
    assert results[0].disposition is CaptureDisposition.CAPTURED
    record = results[0].record
    assert record.replay_identity_chain == (source.replay_uuid, source.decision_uuid, source.execution_uuid)
    assert record.execution_latency_seconds == .25
    assert len(list((tmp_path / "live_outcomes").glob("*.json"))) == 1


def test_duplicate_notification_is_suppressed_without_replacement(tmp_path: Path) -> None:
    lifecycle, source, results = ProductionLifecycle(), context(), []
    integration(tmp_path, lifecycle, source, results)
    trade = completion(source)
    lifecycle.broker_closes_and_executor_finishes(trade)
    path = next((tmp_path / "live_outcomes").glob("*.json"))
    original = path.read_bytes()
    lifecycle.broker_closes_and_executor_finishes(trade)
    assert [result.disposition for result in results] == [
        CaptureDisposition.CAPTURED, CaptureDisposition.DUPLICATE_SUPPRESSED]
    assert path.read_bytes() == original
    assert len(list((tmp_path / "live_outcomes").glob("*.json"))) == 1


def test_capture_failure_and_diagnostic_failure_never_escape_to_lifecycle(tmp_path: Path) -> None:
    lifecycle, source, results = ProductionLifecycle(), context(), []

    def failing_diagnostic(result: object) -> None:
        results.append(result)
        raise RuntimeError("diagnostic unavailable")

    ProductionOutcomeCaptureIntegration(
        lifecycle, LiveOutcomeCapture(LiveOutcomeRepository(tmp_path)), source,
        clock=lambda: "2026-07-26T10:05:05.000000Z", result_observer=failing_diagnostic,
    )
    lifecycle.broker_closes_and_executor_finishes(
        completion(source, execution_context_uuid=str(uuid4()))
    )
    assert lifecycle.events[-1] == "PRODUCER_RETURNED"
    assert results[0].disposition is CaptureDisposition.CAPTURE_FAILED
    assert not list(tmp_path.rglob("*.json"))
