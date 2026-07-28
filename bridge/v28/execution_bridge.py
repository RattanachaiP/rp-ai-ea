"""Governed final boundary; only the existing Executor may communicate with a broker."""
from dataclasses import dataclass
from .execution_replay_validator import validate_execution_replay
from .executor_adapter import adapt_executor_contract


@dataclass(frozen=True)
class BridgeResult:
    delivered: bool; reason: str; executor_result: object | None = None


class ExecutionBridge:
    def __init__(self, executor) -> None: self._executor = executor
    def deliver(self, plan, contract, health, broker, publication, *, demo_approved=False) -> BridgeResult:
        validation = validate_execution_replay(plan, contract, health, broker, publication)
        if not validation.valid: return BridgeResult(False, validation.reasons[0])
        if not demo_approved: return BridgeResult(False, "HUMAN_APPROVAL_REQUIRED")
        if not plan.execution_ready: return BridgeResult(False, "EXECUTION_PLAN_NOT_READY")
        result = self._executor.execute(adapt_executor_contract(contract))
        return BridgeResult(True, "DELIVERED_TO_V27_EXECUTOR", result)

