"""Complete, distinct and broker-free BUY/SELL/HOLD campaign validation."""
from dataclasses import dataclass
from typing import Iterable
from .execution_plan import ExecutionPlan, identity
from .pipeline_validator import Campaign, PR265_POLICY, certification_identity
from .publisher_contract import PublishedExecutionPlan
from .shadow_executor import ShadowExecutionRecord, ShadowExecutor

@dataclass(frozen=True)
class ShadowCase:
    expected_action: str; plan: ExecutionPlan; publication: PublishedExecutionPlan|None

@dataclass(frozen=True)
class ShadowValidationReport:
    status: str; campaign: Campaign; actions: tuple[str,...]; plan_identities: tuple[str,...]
    records: tuple[ShadowExecutionRecord,...]; reasons: tuple[str,...]; broker_submissions: int
    broker_dependency: bool; policy_reference: str; replay_identity: str
    def canonical_payload(self): return {k:getattr(self,k) for k in self.__dataclass_fields__ if k!="replay_identity"}
    def __post_init__(self):
        if self.status not in {"PASS","FAIL"} or self.broker_submissions!=0 or self.broker_dependency is not False: raise ValueError("SHADOW_REPORT_AUTHORITY_INVALID")
        if self.replay_identity!=certification_identity("V28_SHADOW_VALIDATION",self.canonical_payload()): raise ValueError("SHADOW_REPORT_REPLAY_INVALID")

def run_shadow_validation(campaign: Campaign,cases: Iterable[ShadowCase],*,recorded_at:str)->ShadowValidationReport:
    records=[]; reasons=[]; executor=ShadowExecutor()
    for case in tuple(cases):
        if type(case) is not ShadowCase or case.expected_action not in {"BUY","SELL","HOLD"}: reasons.append("SHADOW_CASE_INVALID"); continue
        try: first=executor.execute(case.plan,case.publication,recorded_at=recorded_at); second=executor.execute(case.plan,case.publication,recorded_at=recorded_at)
        except (TypeError,ValueError,AttributeError): reasons.append(f"{case.expected_action}_EVIDENCE_INVALID"); continue
        records.append(first)
        if first.action!=case.expected_action: reasons.append(f"EXPECTED_{case.expected_action}_NOT_OBSERVED")
        if first!=second or first.replay_identity!=identity("V28_SHADOW_EXECUTION_REPLAY",first.canonical_payload()): reasons.append("SHADOW_REPLAY_INVALID")
        if first.ordersend_permitted: reasons.append("ORDERSEND_PERMISSION_DETECTED")
    actions=tuple(x.action for x in records); plans=tuple(x.execution_plan_replay_identity for x in records)
    if len(records)!=3 or sorted(actions)!=["BUY","HOLD","SELL"]: reasons.append("BUY_SELL_HOLD_COVERAGE_INCOMPLETE")
    if len(set(plans))!=3: reasons.append("SHADOW_PLAN_IDENTITIES_NOT_DISTINCT")
    values=dict(status="FAIL" if reasons else "PASS",campaign=campaign,actions=actions,plan_identities=plans,records=tuple(records),reasons=tuple(dict.fromkeys(reasons)) or ("COMPLETE_BROKER_FREE_SHADOW_ONTOLOGY",),broker_submissions=0,broker_dependency=False,policy_reference=PR265_POLICY)
    return ShadowValidationReport(**values,replay_identity=certification_identity("V28_SHADOW_VALIDATION",values))
