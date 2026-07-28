"""Per-run conjunction of authoritative publication and delivery evidence."""
from dataclasses import dataclass
from .execution_plan import identity
from .pipeline_validator import certification_identity,report_identity_valid,PipelineValidationReport
from .delivery_pipeline_validator import DeliveryValidationReport
from .certification_report import CertificationReport
from .qualification_campaign import QualificationCampaign
@dataclass(frozen=True)
class DeliveryReliabilityReport:
    status:str;campaign_identity:str;policy_identity:str;symbol:str;environment_identity:str
    evaluation_window:tuple[str,str];attempts:int;successful_runs:int;failed_runs:int
    failure_rate:float;run_results:tuple[tuple[str,bool,tuple[str,...]],...]
    reasons:tuple[str,...];replay_identity:str
    def canonical_payload(self):return {k:getattr(self,k) for k in self.__dataclass_fields__ if k!="replay_identity"}
    def __post_init__(self):
        if self.status not in {"PASS","FAIL"} or not 0<=self.failure_rate<=1:raise ValueError("DELIVERY_RELIABILITY_REPORT_INVALID")
        if self.replay_identity!=certification_identity("V28_DELIVERY_RELIABILITY_REPORT",self.canonical_payload()):raise ValueError("DELIVERY_RELIABILITY_REPORT_REPLAY_INVALID")
def validate_delivery_reliability(campaign:QualificationCampaign)->DeliveryReliabilityReport:
    results=[]
    for run in campaign.runs:
        failures=[]
        if run.publication.publication_replay_identity!=identity("V28_EXECUTION_PUBLICATION_REPLAY",run.publication.canonical_payload()):failures.append("PUBLICATION_INTEGRITY_INVALID")
        if not report_identity_valid(run.pipeline,PipelineValidationReport,"V28_PIPELINE_VALIDATION") or run.pipeline.status!="PASS":failures.append("PIPELINE_VALIDATION_FAILED")
        if not report_identity_valid(run.delivery,DeliveryValidationReport,"V28_DELIVERY_VALIDATION") or run.delivery.status!="PASS":failures.append("DELIVERY_VALIDATION_FAILED")
        if run.certification.replay.status!="PASS":failures.append("REPLAY_VALIDATION_FAILED")
        if not report_identity_valid(run.certification,CertificationReport,"V28_END_TO_END_CERTIFICATION") or run.certification.status!="PASS":failures.append("CERTIFICATION_FAILED")
        if run.receipt.replay_identity!=identity("V28_DELIVERY_RECEIPT_REPLAY",run.receipt.canonical_payload()) or run.receipt.status!="DELIVERED":failures.append("DELIVERY_RECEIPT_FAILED")
        if run.recovery.status!="NONE":failures.append("FORBIDDEN_RECOVERY_OBSERVED")
        results.append((run.run_identity,not failures,tuple(failures)))
    failed=sum(not x[1] for x in results);rate=failed/len(results);reasons=[]
    if rate>campaign.policy.maximum_delivery_failure_rate:reasons.append("DELIVERY_FAILURE_RATE_EXCEEDED")
    if any("FORBIDDEN_RECOVERY_OBSERVED" in x[2] for x in results):reasons.append("AUTOMATIC_RECOVERY_FORBIDDEN")
    values=dict(status="FAIL" if reasons else "PASS",campaign_identity=campaign.campaign_identity,policy_identity=campaign.policy.policy_identity,symbol=campaign.symbol,environment_identity=campaign.environment_identity,evaluation_window=(campaign.started_at,campaign.expires_at),attempts=len(results),successful_runs=len(results)-failed,failed_runs=failed,failure_rate=rate,run_results=tuple(results),reasons=tuple(reasons) or ("DELIVERY_RELIABLE",))
    return DeliveryReliabilityReport(**values,replay_identity=certification_identity("V28_DELIVERY_RELIABILITY_REPORT",values))
