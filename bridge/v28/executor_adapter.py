"""Validated compatibility contract; the adapter itself creates no authority."""
from __future__ import annotations
from dataclasses import dataclass
from bridge.decision_writer import WriterReadResult
from .execution_plan import identity
from .executor_contract import ExecutorContract


@dataclass(frozen=True)
class V27ExecutorCompatibilityContract:
    sequence_id: int; decision: str; direction: str; entry_permission: bool; entry_state: str
    construction_action: str; fail_safe: bool; executable: bool; symbol: str; volume: float
    entry_price: float; stop_loss: float; take_profit: float
    execution_plan_replay_identity: str; executor_contract_replay_identity: str
    source_policy_reference: str; compatibility_policy_reference: str; replay_identity: str

    def canonical_payload(self): return {k:getattr(self,k) for k in self.__dataclass_fields__ if k != "replay_identity"}
    def __post_init__(self):
        if self.decision not in {"BUY","SELL"} or self.direction != self.decision: raise ValueError("V27_COMPATIBILITY_DIRECTION_INVALID")
        if (self.entry_permission,self.entry_state,self.construction_action,self.fail_safe,self.executable) != (True,"ENTRY_ALLOWED","ALLOW_START",False,True): raise ValueError("V27_COMPATIBILITY_AUTHORITY_INVALID")
        if not all((self.symbol,self.execution_plan_replay_identity,self.executor_contract_replay_identity,self.source_policy_reference,self.compatibility_policy_reference)): raise ValueError("V27_COMPATIBILITY_LINEAGE_INVALID")
        if self.replay_identity != identity("V28_V27_COMPATIBILITY_REPLAY",self.canonical_payload()): raise ValueError("V27_COMPATIBILITY_REPLAY_INVALID")


def build_v27_compatibility_contract(contract: ExecutorContract, *, compatibility_policy_reference: str) -> V27ExecutorCompatibilityContract:
    if contract.replay_identity != identity("V28_EXECUTOR_CONTRACT_REPLAY",contract.canonical_payload()): raise ValueError("EXECUTOR_CONTRACT_INVALID")
    values=dict(sequence_id=contract.runtime_sequence_id,decision=contract.direction,direction=contract.direction,
        entry_permission=True,entry_state="ENTRY_ALLOWED",construction_action="ALLOW_START",fail_safe=False,executable=True,
        symbol=contract.symbol,volume=contract.approved_volume,entry_price=contract.executable_entry_price,
        stop_loss=contract.protective_stop,take_profit=contract.target,execution_plan_replay_identity=contract.execution_plan_replay_identity,
        executor_contract_replay_identity=contract.replay_identity,source_policy_reference=contract.policy_reference,
        compatibility_policy_reference=compatibility_policy_reference)
    return V27ExecutorCompatibilityContract(**values,replay_identity=identity("V28_V27_COMPATIBILITY_REPLAY",values))


@dataclass(frozen=True)
class AdapterResult:
    valid: bool; snapshot: WriterReadResult | None; reason: str | None


def adapt_executor_contract(contract: V27ExecutorCompatibilityContract) -> AdapterResult:
    if type(contract) is not V27ExecutorCompatibilityContract: return AdapterResult(False,None,"V27_COMPATIBILITY_CONTRACT_REQUIRED")
    if contract.replay_identity != identity("V28_V27_COMPATIBILITY_REPLAY",contract.canonical_payload()): return AdapterResult(False,None,"V27_COMPATIBILITY_REPLAY_INVALID")
    projected={field:getattr(contract,field) for field in ("sequence_id","decision","direction","entry_permission","entry_state","construction_action","fail_safe","executable","symbol","volume","entry_price","stop_loss","take_profit")}
    return AdapterResult(True,WriterReadResult(projected,True,False,None),None)
