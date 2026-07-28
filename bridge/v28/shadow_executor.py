"""No-I/O shadow execution recorder for BUY, SELL, and HOLD."""
from dataclasses import dataclass
from .execution_plan import ExecutionPlan


@dataclass(frozen=True)
class ShadowExecutionRecord:
    action: str; expected_execution: bool; expected_fill: float | None
    expected_stop: float | None; expected_target: float | None
    decision_replay_identity: str; execution_replay_identity: str
    ordersend_permitted: bool = False


class ShadowExecutor:
    def __init__(self, logger=lambda _event, _payload: None): self._logger = logger
    def execute(self, plan: ExecutionPlan) -> ShadowExecutionRecord:
        action = plan.direction if plan.execution_ready else "HOLD"
        record = ShadowExecutionRecord(action, plan.execution_ready, plan.executable_entry_price,
            plan.protective_stop, plan.target, plan.decision_replay_identity, plan.replay_identity)
        self._logger("V28_SHADOW_EXECUTION", record.__dict__)
        return record

