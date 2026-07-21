"""Stateless final execution authority for immutable writer snapshots."""
from __future__ import annotations

from dataclasses import dataclass
from time import time_ns
from typing import Callable, Mapping
from uuid import uuid4

from bridge.decision_writer import WriterReadResult
from runtime.broker_safety import BrokerOrderResult, BrokerOutcome, BrokerSafety, ExecutionInstruction, MT5ExecutionInterface, OrderRequest


@dataclass(frozen=True)
class ExecutionResult:
    execution_id: str
    sequence_id: int | None
    submitted: bool
    accepted: bool
    reason: str | None
    attempts: int
    ticket: str | None = None


class Executor:
    """Submit an already validated instruction; never create trading intent."""

    def __init__(self, broker: MT5ExecutionInterface, *, broker_safety: BrokerSafety | None = None,
                 max_retries: int = 1, id_factory: Callable[[], str] | None = None,
                 logger: Callable[[str, Mapping[str, object]], None] | None = None) -> None:
        if type(max_retries) is not int or max_retries < 0:
            raise ValueError("INVALID_MAX_RETRIES")
        self._broker, self._safety = broker, broker_safety or BrokerSafety()
        self._max_retries = max_retries
        self._id_factory = id_factory or (lambda: f"exec-{time_ns():x}-{uuid4().hex}")
        self._logger = logger or (lambda _event, _data: None)
        self._processed_sequences: set[int] = set()

    def execute(self, snapshot: WriterReadResult) -> ExecutionResult:
        """Execute exactly one immutable snapshot and never read ``decision.json``."""
        execution_id = self._id_factory()
        if type(snapshot) is not WriterReadResult:
            return self._finish(execution_id, None, False, False, "INVALID_WRITER_READ_RESULT", 0)
        payload = snapshot.payload
        sequence_id = payload.get("sequence_id")
        if not snapshot.accepted or snapshot.ignored_duplicate:
            return self._finish(execution_id, sequence_id, False, False, snapshot.reason or "UNACCEPTED_SNAPSHOT", 0)
        if type(sequence_id) is not int:
            return self._finish(execution_id, None, False, False, "INVALID_SEQUENCE", 0)
        if sequence_id in self._processed_sequences:
            return self._finish(execution_id, sequence_id, False, False, "DUPLICATE_EXECUTION", 0)
        self._processed_sequences.add(sequence_id)
        contract_reason = self._contract_rejection(payload)
        if contract_reason:
            return self._finish(execution_id, sequence_id, False, False, contract_reason, 0)
        instruction, instruction_reason = self._instruction(payload)
        if instruction_reason:
            return self._finish(execution_id, sequence_id, False, False, instruction_reason, 0)
        safety_reason = self._safety.validate(instruction, self._broker)
        if safety_reason:
            return self._finish(execution_id, sequence_id, False, False, safety_reason, 0)
        return self._submit(instruction, execution_id, sequence_id)

    @staticmethod
    def _contract_rejection(payload: Mapping[str, object]) -> str | None:
        if payload.get("fail_safe") is not False:
            return "FAIL_SAFE"
        if payload.get("executable") is not True:
            return "NOT_EXECUTABLE"
        if payload.get("entry_permission") is not True:
            return "ENTRY_NOT_PERMITTED"
        if payload.get("direction") not in {"BUY", "SELL"}:
            return "INVALID_DIRECTION"
        if payload.get("construction_action") not in {"ALLOW_START", "ALLOW_SCALE"}:
            return "INVALID_CONSTRUCTION_ACTION"
        return None

    @staticmethod
    def _instruction(payload: Mapping[str, object]) -> tuple[ExecutionInstruction | None, str | None]:
        fields = ("symbol", "volume", "entry_price", "stop_loss", "take_profit")
        if any(field not in payload for field in fields):
            return None, "MISSING_EXECUTION_INSTRUCTION"
        values = (payload["volume"], payload["entry_price"], payload["stop_loss"], payload["take_profit"])
        if type(payload["symbol"]) is not str or not payload["symbol"] or any(type(value) not in (int, float) or isinstance(value, bool) for value in values):
            return None, "INVALID_EXECUTION_INSTRUCTION"
        return ExecutionInstruction(payload["symbol"], payload["direction"], *map(float, values)), None

    def _submit(self, instruction: ExecutionInstruction, execution_id: str, sequence_id: int) -> ExecutionResult:
        attempts = 0
        while True:
            attempts += 1
            try:
                result = self._broker.send_order(OrderRequest(instruction, execution_id, f"RP:{execution_id}"))
            except Exception:
                return self._finish(execution_id, sequence_id, True, False, "EXECUTION_OUTCOME_UNKNOWN", attempts)
            if type(result) is not BrokerOrderResult or not isinstance(result.outcome, BrokerOutcome) or type(result.code) is not str:
                return self._finish(execution_id, sequence_id, True, False, "EXECUTION_OUTCOME_UNKNOWN", attempts)
            if result.outcome is BrokerOutcome.ACCEPTED:
                return self._finish(execution_id, sequence_id, True, True, None, attempts, result.ticket)
            if result.outcome is BrokerOutcome.AMBIGUOUS:
                return self._finish(execution_id, sequence_id, True, False, "EXECUTION_OUTCOME_UNKNOWN", attempts, result.ticket)
            if result.outcome is not BrokerOutcome.CONFIRMED_REJECTED_RETRYABLE or attempts > self._max_retries:
                return self._finish(execution_id, sequence_id, True, False, result.code, attempts)

    def _finish(self, execution_id: str, sequence_id: int | None, submitted: bool, accepted: bool,
                reason: str | None, attempts: int, ticket: str | None = None) -> ExecutionResult:
        result = ExecutionResult(execution_id, sequence_id, submitted, accepted, reason, attempts, ticket)
        self._logger("EXECUTION_RESULT", {"execution_id": execution_id, "sequence_id": sequence_id,
                                           "submitted": submitted, "accepted": accepted, "reason": reason, "attempts": attempts})
        return result
