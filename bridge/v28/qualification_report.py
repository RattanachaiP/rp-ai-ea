"""Top-level operational qualification report; production is never authorized."""
from dataclasses import dataclass
import json
from typing import Any,Mapping
from .campaign_statistics import CampaignStatistics
from .delivery_reliability_validator import DeliveryReliabilityReport
from .pipeline_validator import certification_identity
from .qualification_campaign import PR266_POLICY,QualificationCampaign
from .runtime_stability_monitor import RuntimeStabilityReport
from .shadow_campaign_runner import ShadowCampaignReport

RECOMMENDATIONS=("NOT READY","CONDITIONALLY READY","READY FOR HUMAN REVIEW")
def _plain(v:Any)->Any:
    if hasattr(v,"__dataclass_fields__"):return {k:_plain(getattr(v,k)) for k in v.__dataclass_fields__}
    if isinstance(v,Mapping):return {str(k):_plain(x) for k,x in v.items()}
    if isinstance(v,(tuple,list)):return [_plain(x) for x in v]
    return v
@dataclass(frozen=True)
class QualificationReport:
    status:str;campaign_summary:CampaignStatistics;replay_stability:ShadowCampaignReport
    runtime_stability:RuntimeStabilityReport;delivery_reliability:DeliveryReliabilityReport
    certification_stability:bool;operational_recommendation:str;production_authorized:bool
    policy_reference:str;reasons:tuple[str,...];replay_identity:str
    def canonical_payload(self):return {k:getattr(self,k) for k in self.__dataclass_fields__ if k!="replay_identity"}
    def to_json(self):return json.dumps(_plain(self),sort_keys=True,separators=(",",":"),allow_nan=False)
    def __post_init__(self):
        if self.status not in {"PASS","FAIL"} or self.operational_recommendation not in RECOMMENDATIONS or self.production_authorized is not False or self.policy_reference!=PR266_POLICY:raise ValueError("QUALIFICATION_REPORT_INVALID")
        if self.replay_identity!=certification_identity("V28_OPERATIONAL_QUALIFICATION_REPORT",self.canonical_payload()):raise ValueError("QUALIFICATION_REPORT_REPLAY_INVALID")

def build_qualification_report(campaign:QualificationCampaign,statistics:CampaignStatistics,runtime:RuntimeStabilityReport,shadow:ShadowCampaignReport,delivery:DeliveryReliabilityReport,*,assessed_at:str)->QualificationReport:
    identities=(runtime.campaign_identity,shadow.campaign_identity,delivery.campaign_identity)
    report_integrity=(
        runtime.replay_identity==certification_identity("V28_RUNTIME_STABILITY_REPORT",runtime.canonical_payload())
        and shadow.replay_identity==certification_identity("V28_SHADOW_CAMPAIGN_REPORT",shadow.canonical_payload())
        and delivery.replay_identity==certification_identity("V28_DELIVERY_RELIABILITY_REPORT",delivery.canonical_payload())
        and statistics.replay_identity==certification_identity("V28_CAMPAIGN_STATISTICS",statistics.canonical_payload())
    )
    statistics_match=statistics.campaign_count==1 and statistics.run_count==len(campaign.runs)
    integrity=all(x==campaign.campaign_identity for x in identities) and report_integrity and statistics_match
    expired=campaign.is_expired(assessed_at)
    stable=all(x.certification.status=="PASS" for x in campaign.runs) and all(len({x.certification.replay_identity for x in campaign.runs if x.action==a})==1 for a in set(x.action for x in campaign.runs))
    passed=integrity and expired and stable and runtime.status==shadow.status==delivery.status=="PASS"
    reasons=[]
    if not integrity:reasons.append("CROSS_REPORT_CAMPAIGN_MISMATCH")
    if not expired:reasons.append("CAMPAIGN_NOT_COMPLETE")
    if not stable:reasons.append("CERTIFICATION_INSTABILITY")
    if any(x.status=="FAIL" for x in (runtime,shadow,delivery)):reasons.append("QUALIFICATION_COMPONENT_FAILURE")
    recommendation="READY FOR HUMAN REVIEW" if passed else ("CONDITIONALLY READY" if integrity and stable else "NOT READY")
    values=dict(status="PASS" if passed else "FAIL",campaign_summary=statistics,replay_stability=shadow,runtime_stability=runtime,delivery_reliability=delivery,certification_stability=stable,operational_recommendation=recommendation,production_authorized=False,policy_reference=PR266_POLICY,reasons=tuple(reasons) or ("QUALIFIED_FOR_HUMAN_REVIEW",))
    return QualificationReport(**values,replay_identity=certification_identity("V28_OPERATIONAL_QUALIFICATION_REPORT",values))
