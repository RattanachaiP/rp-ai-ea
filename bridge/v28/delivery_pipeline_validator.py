"""Complete read-only validation of environment, approval and delivery receipt."""
from dataclasses import dataclass
from datetime import datetime,timezone
from typing import Any
from .execution_bridge import DeliveryReceipt
from .execution_plan import ExecutionPlan,identity,parse_utc
from .executor_contract import ExecutorContract
from .pipeline_validator import Campaign,PR265_POLICY,certification_identity
from .publisher_contract import ExecutionEnvironmentContract,HumanApprovalRecord,PublishedExecutionPlan

@dataclass(frozen=True)
class DeliveryValidationReport:
    status: str; campaign: Campaign; checks: tuple[str,...]; failures: tuple[str,...]
    production_authorized: bool; policy_reference: str; replay_identity: str
    def canonical_payload(self): return {k:getattr(self,k) for k in self.__dataclass_fields__ if k!="replay_identity"}
    def __post_init__(self):
        if self.status not in {"PASS","FAIL"} or self.production_authorized is not False or self.policy_reference!=PR265_POLICY: raise ValueError("DELIVERY_REPORT_INVALID")
        if self.replay_identity!=certification_identity("V28_DELIVERY_VALIDATION",self.canonical_payload()): raise ValueError("DELIVERY_REPORT_REPLAY_INVALID")

def validate_delivery(*,campaign:Campaign,plan:Any,contract:Any,publication:Any,environment:Any,
                      approval:Any,receipt:Any)->DeliveryValidationReport:
    f=[]
    valid=(type(plan) is ExecutionPlan,type(contract) is ExecutorContract,type(publication) is PublishedExecutionPlan,
           type(environment) is ExecutionEnvironmentContract,type(approval) is HumanApprovalRecord,type(receipt) is DeliveryReceipt)
    if not all(valid): f.append("DELIVERY_ARTIFACT_MISSING_OR_INVALID")
    else:
        if receipt.replay_identity!=identity("V28_DELIVERY_RECEIPT_REPLAY",receipt.canonical_payload()): f.append("DELIVERY_RECEIPT_REPLAY_INVALID")
        if environment.replay_identity!=identity("V28_EXECUTION_ENVIRONMENT_REPLAY",environment.canonical_payload()): f.append("ENVIRONMENT_REPLAY_INVALID")
        if approval.replay_identity!=identity("V28_HUMAN_APPROVAL_REPLAY",approval.canonical_payload()): f.append("APPROVAL_REPLAY_INVALID")
        comparisons=((receipt.execution_plan_replay_identity,plan.replay_identity,"DELIVERY_PLAN_MISMATCH"),(receipt.executor_contract_replay_identity,contract.replay_identity,"DELIVERY_CONTRACT_MISMATCH"),(receipt.publication_replay_identity,publication.publication_replay_identity,"DELIVERY_PUBLICATION_MISMATCH"),(receipt.environment_identity,environment.replay_identity,"DELIVERY_ENVIRONMENT_MISMATCH"),(receipt.executor_instance_identity,environment.executor_instance_identity,"DELIVERY_EXECUTOR_MISMATCH"))
        for actual,expected,reason in comparisons:
            if actual!=expected:f.append(reason)
        if receipt.runtime_sequence_id!=campaign.runtime_sequence_id:f.append("DELIVERY_SEQUENCE_MISMATCH")
        if environment.replay_identity!=campaign.environment_identity:f.append("DELIVERY_CAMPAIGN_ENVIRONMENT_MISMATCH")
        if publication.policy_reference!=environment.policy_reference or approval.policy_reference!=environment.policy_reference:f.append("DELIVERY_POLICY_LINEAGE_MISMATCH")
        try:
            delivered=parse_utc(receipt.delivered_at); now=parse_utc(campaign.evaluation_time)
            if delivered>now:f.append("DELIVERY_FUTURE_DATED")
            if parse_utc(publication.publication_timestamp)>delivered:f.append("PUBLICATION_AFTER_DELIVERY")
            if parse_utc(approval.approval_timestamp)>delivered:f.append("APPROVAL_AFTER_DELIVERY")
            if delivered>parse_utc(environment.expires_at):f.append("ENVIRONMENT_EXPIRED_AT_DELIVERY")
            if delivered<parse_utc(environment.verification_timestamp):f.append("DELIVERY_BEFORE_ENVIRONMENT_VERIFICATION")
        except ValueError:f.append("DELIVERY_TIMESTAMP_INVALID")
        if receipt.status=="DELIVERED" and receipt.downstream_result_identity in {"","NONE"}:f.append("DOWNSTREAM_RESULT_IDENTITY_MISSING")
        if receipt.status=="REJECTED" and receipt.downstream_result_identity!="NONE":f.append("REJECTED_DELIVERY_HAS_DOWNSTREAM_IDENTITY")
    values=dict(status="FAIL" if f else "PASS",campaign=campaign,checks=("RECEIPT_REPLAY","ENVIRONMENT_REPLAY","EXECUTOR_IDENTITY","PUBLICATION_CHRONOLOGY","APPROVAL_CHRONOLOGY","ENVIRONMENT_VALIDITY","FUTURE_TIMESTAMP","DOWNSTREAM_IDENTITY","POLICY_LINEAGE","RUNTIME_SEQUENCE"),failures=tuple(dict.fromkeys(f)),production_authorized=False,policy_reference=PR265_POLICY)
    return DeliveryValidationReport(**values,replay_identity=certification_identity("V28_DELIVERY_VALIDATION",values))
