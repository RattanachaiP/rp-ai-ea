"""Fail-closed reliability measurements over immutable campaign evidence."""
from dataclasses import dataclass
from .pipeline_validator import certification_identity
from .qualification_campaign import PR266_POLICY, QualificationCampaign

@dataclass(frozen=True)
class DeliveryReliabilityReport:
    status:str;campaign_identity:str;attempts:int;publication_successes:int
    validation_successes:int;delivery_successes:int;replay_successes:int
    certification_successes:int;failure_rate:float;recovery_attempts:int
    recovery_behavior:str;reasons:tuple[str,...];policy_reference:str;replay_identity:str
    def canonical_payload(self):return {k:getattr(self,k) for k in self.__dataclass_fields__ if k!="replay_identity"}
    def __post_init__(self):
        if self.status not in {"PASS","FAIL"} or self.policy_reference!=PR266_POLICY or not 0<=self.failure_rate<=1:raise ValueError("DELIVERY_RELIABILITY_REPORT_INVALID")
        if self.replay_identity!=certification_identity("V28_DELIVERY_RELIABILITY_REPORT",self.canonical_payload()):raise ValueError("DELIVERY_RELIABILITY_REPORT_REPLAY_INVALID")

def validate_delivery_reliability(campaign:QualificationCampaign)->DeliveryReliabilityReport:
    runs=campaign.runs;n=len(runs);publication=sum(x.publication_succeeded for x in runs);validation=sum(x.validation_succeeded for x in runs);delivery=sum(x.delivery_succeeded for x in runs)
    replay=sum(x.certification.replay.status=="PASS" for x in runs);certification=sum(x.certification.status=="PASS" for x in runs);recovery=sum(x.recovery_attempted for x in runs)
    failed=n-min(publication,validation,delivery,replay,certification);reasons=[]
    if failed:reasons.append("PIPELINE_DELIVERY_FAILURE")
    if recovery:reasons.append("AUTOMATIC_RECOVERY_FORBIDDEN")
    values=dict(status="FAIL" if reasons else "PASS",campaign_identity=campaign.campaign_identity,attempts=n,publication_successes=publication,validation_successes=validation,delivery_successes=delivery,replay_successes=replay,certification_successes=certification,failure_rate=failed/n,recovery_attempts=recovery,recovery_behavior="NONE_OBSERVED" if not recovery else "FORBIDDEN_RECOVERY_OBSERVED",reasons=tuple(reasons) or ("DELIVERY_RELIABLE",),policy_reference=PR266_POLICY)
    return DeliveryReliabilityReport(**values,replay_identity=certification_identity("V28_DELIVERY_RELIABILITY_REPORT",values))
