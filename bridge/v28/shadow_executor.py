"""Governed, broker-free and independently replay-validating shadow recorder."""
from dataclasses import dataclass
from .execution_plan import ExecutionPlan,identity,parse_utc
from .publisher_contract import PublishedExecutionPlan,canonical_json

@dataclass(frozen=True)
class ShadowExecutionRecord:
    symbol: str; runtime_sequence_id: int; action: str; expected_entry: float|None
    expected_stop: float|None; expected_target: float|None; decision_replay_identity: str
    execution_plan_replay_identity: str; publication_replay_identity: str; mode: str
    recorded_at: str; ordersend_permitted: bool; replay_identity: str
    def canonical_payload(self): return {k:getattr(self,k) for k in self.__dataclass_fields__ if k!="replay_identity"}
    def __post_init__(self):
        if self.mode!="SHADOW" or self.ordersend_permitted is not False: raise ValueError("SHADOW_AUTHORITY_INVALID")
        parse_utc(self.recorded_at)
        if self.replay_identity!=identity("V28_SHADOW_EXECUTION_REPLAY",self.canonical_payload()): raise ValueError("SHADOW_REPLAY_INVALID")

class ShadowExecutor:
    def __init__(self,logger=lambda _event,_payload:None): self._logger=logger
    def execute(self,plan:ExecutionPlan,publication:PublishedExecutionPlan|None,*,recorded_at:str):
        if plan.replay_identity!=identity("V28_EXECUTION_PLAN_REPLAY",plan.canonical_payload()): raise ValueError("EXECUTION_PLAN_INVALID")
        if publication is not None and (publication.execution_plan_replay_identity!=plan.replay_identity or publication.canonical_plan_json!=canonical_json(plan.canonical_payload())): raise ValueError("PUBLICATION_INVALID")
        values=dict(symbol=plan.symbol,runtime_sequence_id=plan.runtime_sequence_id,action=plan.direction if plan.execution_ready else "HOLD",
            expected_entry=plan.executable_entry_price,expected_stop=plan.protective_stop,expected_target=plan.target,
            decision_replay_identity=plan.decision_replay_identity,execution_plan_replay_identity=plan.replay_identity,
            publication_replay_identity=publication.publication_replay_identity if publication else "IN_MEMORY_VALIDATION",
            mode="SHADOW",recorded_at=recorded_at,ordersend_permitted=False)
        record=ShadowExecutionRecord(**values,replay_identity=identity("V28_SHADOW_EXECUTION_REPLAY",values)); self._logger("V28_SHADOW_EXECUTION",record.canonical_payload()); return record
