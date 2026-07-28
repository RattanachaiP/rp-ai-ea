"""Independently validated, immutable ready-only governed Executor handoff."""
from dataclasses import dataclass
from .execution_plan import ExecutionPlan, POLICY_ID, POLICY_VERSION, _finite, identity

@dataclass(frozen=True)
class ExecutorContract:
    execution_plan_replay_identity: str; decision_replay_identity: str; runtime_sequence_id: int
    symbol: str; direction: str; approved_volume: float; executable_entry_price: float
    volume_step: float; tick_size: float
    protective_stop: float; target: float; execution_model_id: str
    policy_reference: str; replay_identity: str
    schema_version: str="V28.EXECUTOR_CONTRACT.1.1"
    def canonical_payload(self): return {k:getattr(self,k) for k in self.__dataclass_fields__ if k!="replay_identity"}
    def __post_init__(self):
        if not all((self.execution_plan_replay_identity,self.decision_replay_identity,self.symbol,self.execution_model_id,self.policy_reference)): raise ValueError("EXECUTOR_CONTRACT_LINEAGE_INVALID")
        if self.direction not in {"BUY","SELL"} or type(self.runtime_sequence_id) is not int: raise ValueError("EXECUTOR_CONTRACT_DIRECTION_INVALID")
        for v in (self.approved_volume,self.volume_step,self.tick_size,self.executable_entry_price,self.protective_stop,self.target): _finite(v,positive=True)
        from decimal import Decimal
        if Decimal(str(self.approved_volume))%Decimal(str(self.volume_step))!=0: raise ValueError("EXECUTOR_CONTRACT_VOLUME_INVALID")
        if any(Decimal(str(v))%Decimal(str(self.tick_size))!=0 for v in (self.executable_entry_price,self.protective_stop,self.target)): raise ValueError("EXECUTOR_CONTRACT_PRICE_INVALID")
        if self.direction=="BUY" and not self.protective_stop<self.executable_entry_price<self.target: raise ValueError("EXECUTOR_CONTRACT_PRICE_SIDES_INVALID")
        if self.direction=="SELL" and not self.target<self.executable_entry_price<self.protective_stop: raise ValueError("EXECUTOR_CONTRACT_PRICE_SIDES_INVALID")
        if self.replay_identity!=identity("V28_EXECUTOR_CONTRACT_REPLAY",self.canonical_payload()): raise ValueError("EXECUTOR_CONTRACT_REPLAY_INVALID")

def build_executor_contract(plan: ExecutionPlan):
    if not plan.execution_ready: raise ValueError("EXECUTION_PLAN_NOT_READY")
    # Revalidate the plan in case a frozen object was maliciously mutated.
    if plan.replay_identity!=identity("V28_EXECUTION_PLAN_REPLAY",plan.canonical_payload()): raise ValueError("EXECUTION_PLAN_REPLAY_INVALID")
    values=dict(execution_plan_replay_identity=plan.replay_identity,decision_replay_identity=plan.decision_replay_identity,
        runtime_sequence_id=plan.runtime_sequence_id,symbol=plan.symbol,direction=plan.direction,
        approved_volume=plan.approved_volume,executable_entry_price=plan.executable_entry_price,
        volume_step=plan.volume_step,tick_size=plan.tick_size,
        protective_stop=plan.protective_stop,target=plan.target,execution_model_id=plan.execution_model_id,
        policy_reference=f"{POLICY_ID}@{POLICY_VERSION}",schema_version="V28.EXECUTOR_CONTRACT.1.1")
    return ExecutorContract(**values,replay_identity=identity("V28_EXECUTOR_CONTRACT_REPLAY",values))
