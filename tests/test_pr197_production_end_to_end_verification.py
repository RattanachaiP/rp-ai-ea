"""PR197 certification checks across the existing production boundaries.

These checks deliberately use a deterministic broker double.  They certify the
repository integration boundary, not connectivity to a live MT5 terminal.
"""
from pathlib import Path
from time import perf_counter_ns
from uuid import uuid4

from bridge.decision_writer import WriterReadResult
from runtime.broker_safety import BrokerOrderResult, BrokerOutcome, BrokerSymbol
from runtime.executor import Executor
from runtime.executor_activation import RuntimeActivationState
from runtime.production_wiring import ProductionExecutionWiring, ProductionPathConfiguration


class RecordingBroker:
    """Deterministic implementation of the existing MT5 execution interface."""

    def __init__(self) -> None:
        self.requests = []

    def symbol_info(self, _symbol: str) -> BrokerSymbol:
        return BrokerSymbol(True, True, 0.01, 1.0, 0.01)

    def free_margin(self) -> float:
        return 1_000.0

    def required_margin(self, _instruction: object) -> float:
        return 10.0

    def send_order(self, request: object) -> BrokerOrderResult:
        self.requests.append(request)
        return BrokerOrderResult(BrokerOutcome.ACCEPTED, "DONE", ticket="PR197-1")


def runtime_values(replay_uuid: str) -> dict[str, object]:
    return {
        "execution_uuid": str(uuid4()),
        "decision_uuid": str(uuid4()),
        "package_uuid": str(uuid4()),
        "replay_uuid": replay_uuid,
        "execution_confidence": 0.8,
        "readiness_state": "EXECUTION_READY_FOR_ENVIRONMENT_CHECK",
        "environment_state": "ENVIRONMENT_READY_FOR_FEASIBILITY",
        "feasibility_state": "EXECUTION_FEASIBLE",
        "policy_version": "policy-1",
        "engine_version": "V26.6.2A",
        "advisory_only": True,
    }


def executable_snapshot() -> WriterReadResult:
    return WriterReadResult({
        "sequence_id": 197,
        "decision": "BUY",
        "direction": "BUY",
        "entry_permission": True,
        "entry_state": "ENTRY_ALLOWED",
        "construction_action": "ALLOW_START",
        "fail_safe": False,
        "executable": True,
        "symbol": "XAUUSD",
        "volume": 0.01,
        "entry_price": 2300.0,
        "stop_loss": 2290.0,
        "take_profit": 2320.0,
    }, True, False, None)


def test_approved_startup_reaches_existing_executor_and_order_submission(tmp_path: Path) -> None:
    common_files = tmp_path / "Common" / "Files"
    common_files.mkdir(parents=True)
    replay_uuid = str(uuid4())
    broker = RecordingBroker()
    execution_results = []

    def start_existing_executor() -> None:
        execution_results.append(Executor(broker).execute(executable_snapshot()))

    wiring = ProductionExecutionWiring(
        ProductionPathConfiguration(common_files),
        engine_version="V26.6.2A",
        replay_uuid=replay_uuid,
        runtime_state=lambda: RuntimeActivationState.READY,
        executor_start=start_existing_executor,
    )
    started_at = perf_counter_ns()
    startup = wiring.start(runtime_values(replay_uuid))
    elapsed_ns = perf_counter_ns() - started_at

    assert startup.activation.authorized is True
    assert startup.activation.execution_uuid == startup.context.execution_uuid
    assert startup.context.replay_uuid == replay_uuid
    assert execution_results[0].accepted is True
    assert execution_results[0].ticket == "PR197-1"
    assert len(broker.requests) == 1
    assert elapsed_ns > 0


def test_invalid_contract_never_reaches_broker() -> None:
    broker = RecordingBroker()
    invalid = executable_snapshot()
    payload = dict(invalid.payload)
    payload["fail_safe"] = True

    result = Executor(broker).execute(WriterReadResult(payload, True, False, None))

    assert result.reason == "FAIL_SAFE"
    assert result.submitted is False
    assert broker.requests == []
