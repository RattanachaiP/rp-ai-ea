"""Narrow immutable handoff to the governed Executor; no order API exists here."""
from dataclasses import dataclass
from .execution_plan import ExecutionPlan

@dataclass(frozen=True)
class ExecutorContract:
    execution_plan_replay_identity: str
    decision_replay_identity: str
    symbol: str
    direction: str
    volume: float
    protective_stop: float
    target: float
    execution_ready: bool
    contract_version: str = "V28.EXECUTOR_CONTRACT.1.0"

def build_executor_contract(plan: ExecutionPlan) -> ExecutorContract:
    if not plan.execution_ready:
        raise ValueError("EXECUTION_PLAN_NOT_READY")
    return ExecutorContract(plan.replay_identity, plan.decision_replay_identity, plan.symbol, plan.direction,
                            plan.volume, plan.protective_stop, plan.target, True)
