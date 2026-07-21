"""Integration contracts for the WriterReadResult-only executor."""
from __future__ import annotations

import ast
from pathlib import Path

import pytest

from bridge.decision_writer import WriterReadResult
from runtime.broker_safety import BrokerOrderResult, BrokerSymbol
from runtime.executor import Executor


class Broker:
    def __init__(self, *, symbol=True, margin=100.0, responses=None):
        self.symbol = symbol; self.margin = margin; self.responses = list(responses or [BrokerOrderResult(True, "DONE", ticket="42")]); self.requests = []
    def symbol_info(self, _symbol): return BrokerSymbol(True, True, .01, 1.0, .01) if self.symbol else None
    def free_margin(self): return self.margin
    def required_margin(self, _instruction): return 10.0
    def send_order(self, request):
        self.requests.append(request)
        return self.responses.pop(0) if self.responses else BrokerOrderResult(True, "DONE", ticket="42")


def snapshot(sequence=1, **changes):
    payload = {"sequence_id": sequence, "decision": "BUY", "direction": "BUY", "entry_permission": True,
               "entry_state": "ENTRY_ALLOWED", "construction_action": "ALLOW_START", "fail_safe": False,
               "executable": True, "symbol": "XAUUSD", "volume": .01, "entry_price": 2300.0,
               "stop_loss": 2290.0, "take_profit": 2320.0}
    payload.update(changes)
    return WriterReadResult(payload, True, False, None)


@pytest.mark.parametrize(("direction", "sl", "tp"), [("BUY", 2290.0, 2320.0), ("SELL", 2310.0, 2280.0)])
def test_buy_and_sell_execution(direction, sl, tp):
    broker = Broker(); result = Executor(broker).execute(snapshot(direction=direction, decision=direction, stop_loss=sl, take_profit=tp))
    assert result.accepted and result.ticket == "42" and broker.requests[0].instruction.direction == direction
    assert broker.requests[0].comment.endswith(result.execution_id)


@pytest.mark.parametrize("changes", [{"decision": "WAIT", "executable": False}, {"decision": "BLOCK", "executable": False}, {"executable": False}, {"fail_safe": True}])
def test_non_executable_contracts_never_submit(changes):
    broker = Broker(); result = Executor(broker).execute(snapshot(**changes))
    assert not result.submitted and not broker.requests


def test_stale_snapshot_and_duplicate_execution_are_rejected():
    broker = Broker(); executor = Executor(broker)
    stale = WriterReadResult({"sequence_id": 1}, False, False, "STALE_HEARTBEAT")
    assert executor.execute(stale).reason == "STALE_HEARTBEAT"
    assert executor.execute(snapshot()).accepted
    assert executor.execute(snapshot()).reason == "DUPLICATE_EXECUTION"
    assert len(broker.requests) == 1


@pytest.mark.parametrize(("broker", "changes", "reason"), [(Broker(symbol=False), {}, "INVALID_SYMBOL"), (Broker(margin=1), {}, "INSUFFICIENT_MARGIN"), (Broker(), {"volume": .015}, "INVALID_LOT")])
def test_broker_safety_rejections_do_not_submit(broker, changes, reason):
    result = Executor(broker).execute(snapshot(**changes))
    assert result.reason == reason and not result.submitted and not broker.requests


def test_broker_rejection_and_retry_policy():
    broker = Broker(responses=[BrokerOrderResult(False, "REQUOTE", True), BrokerOrderResult(True, "DONE", ticket="43")])
    result = Executor(broker, max_retries=1).execute(snapshot())
    assert result.accepted and result.attempts == 2 and len(broker.requests) == 2
    rejected = Executor(Broker(responses=[BrokerOrderResult(False, "REJECTED")])).execute(snapshot())
    assert rejected.submitted and not rejected.accepted and rejected.reason == "REJECTED"


def test_execution_ids_are_unique_and_snapshot_is_immutable():
    executor = Executor(Broker())
    first = executor.execute(snapshot(1)); second = executor.execute(snapshot(2))
    assert first.execution_id != second.execution_id
    frozen = snapshot()
    with pytest.raises(TypeError): frozen.payload["direction"] = "SELL"
    assert frozen.payload["direction"] == "BUY"


def test_executor_has_no_brain_or_writer_publication_imports():
    root = Path(__file__).parents[1]
    for relative in ("runtime/executor.py", "runtime/broker_safety.py"):
        tree = ast.parse((root / relative).read_text(encoding="utf-8"))
        modules = [node.module or "" for node in ast.walk(tree) if isinstance(node, ast.ImportFrom)]
        assert not any(module == "brain" or module.startswith("brain.") or module in {"runtime.writer_adapter", "runtime.decision_publication"} for module in modules)
