"""Policy-only operational recommendation; production is never authorized."""
from dataclasses import dataclass
import json
from typing import Any,Mapping
from .campaign_statistics import CampaignStatistics
from .delivery_reliability_validator import DeliveryReliabilityReport,validate_delivery_reliability
from .pipeline_validator import certification_identity
from .qualification_campaign import QualificationCampaign
from .qualification_registry import QualificationRegistry
from .runtime_stability_monitor import RuntimeStabilityReport,monitor_runtime_stability
from .shadow_campaign_runner import ShadowCampaignReport,run_shadow_campaign

def _plain(v:Any)->Any:
    if hasattr(v,"__dataclass_fields__"):return {k:_plain(getattr(v,k)) for k in v.__dataclass_fields__}
    if isinstance(v,Mapping):return {str(k):_plain(x) for k,x in v.items()}
    if isinstance(v,(tuple,list)):return [_plain(x) for x in v]
    return v
@dataclass(frozen=True)
class QualificationReport:
    status:str;campaign_identity:str;pr265_campaign_identities:tuple[str,...];symbol:str
    environment_identity:str;policy_identity:str;evaluation_window:tuple[str,str];run_count:int
    campaign_summary:CampaignStatistics;replay_stability:ShadowCampaignReport
    runtime_stability:RuntimeStabilityReport;delivery_reliability:DeliveryReliabilityReport
    certification_stability:bool;stable_campaign_count:int;operational_recommendation:str
    production_authorized:bool;reasons:tuple[str,...];replay_identity:str
    def canonical_payload(self):return {k:getattr(self,k) for k in self.__dataclass_fields__ if k!="replay_identity"}
    def to_json(self):return json.dumps(_plain(self),sort_keys=True,separators=(",",":"),allow_nan=False)
    def __post_init__(self):
        if self.status not in {"PASS","FAIL"} or self.operational_recommendation not in {"NOT READY","CONDITIONALLY READY","READY FOR HUMAN REVIEW"} or self.production_authorized is not False:raise ValueError("QUALIFICATION_REPORT_INVALID")
        if self.replay_identity!=certification_identity("V28_OPERATIONAL_QUALIFICATION_REPORT",self.canonical_payload()):raise ValueError("QUALIFICATION_REPORT_REPLAY_INVALID")
def _valid_identity(report,domain):return report.replay_identity==certification_identity(domain,report.canonical_payload())
def _stable(campaign):return monitor_runtime_stability(campaign).status==run_shadow_campaign(campaign).status==validate_delivery_reliability(campaign).status=="PASS"
def build_qualification_report(campaign:QualificationCampaign,registry:QualificationRegistry,statistics:CampaignStatistics,runtime:RuntimeStabilityReport,shadow:ShadowCampaignReport,delivery:DeliveryReliabilityReport,*,assessed_at:str)->QualificationReport:
    reports=((runtime,"V28_RUNTIME_STABILITY_REPORT"),(shadow,"V28_SHADOW_CAMPAIGN_REPORT"),(delivery,"V28_DELIVERY_RELIABILITY_REPORT"),(statistics,"V28_CAMPAIGN_STATISTICS"));reasons=[]
    if any(not _valid_identity(*x) for x in reports):reasons.append("NESTED_REPORT_INTEGRITY_INVALID")
    common=(campaign.campaign_identity,campaign.policy.policy_identity,campaign.symbol,campaign.environment_identity,(campaign.started_at,campaign.expires_at),len(campaign.runs))
    for report in (runtime,shadow,delivery):
        if (report.campaign_identity,report.policy_identity,report.symbol,report.environment_identity,report.evaluation_window,report.sample_count if hasattr(report,"sample_count") else report.run_count if hasattr(report,"run_count") else report.attempts)!=common:reasons.append("CROSS_REPORT_CAMPAIGN_MISMATCH")
    if registry.policy.policy_identity!=campaign.policy.policy_identity or campaign.campaign_identity not in tuple(c.campaign_identity for c in registry.campaigns):reasons.append("REGISTRY_CAMPAIGN_MISMATCH")
    if statistics.registry_identity!=registry.registry_identity or statistics.policy_identity!=campaign.policy.policy_identity or statistics.campaign_identities!=tuple(c.campaign_identity for c in registry.campaigns):reasons.append("STATISTICS_COVERAGE_MISMATCH")
    if not campaign.is_active(assessed_at):reasons.append("CAMPAIGN_NOT_ACTIVE")
    stable_count=0
    for item in reversed(registry.campaigns):
        if _stable(item):stable_count+=1
        else:break
    certification_stable=all(x.certification.status=="PASS" for x in campaign.runs)
    mandatory=not reasons and runtime.status==shadow.status==delivery.status=="PASS" and certification_stable
    if not mandatory:state="FAIL"
    elif stable_count<campaign.policy.required_consecutive_stable_campaigns:state="INCOMPLETE";reasons.append("CONSECUTIVE_STABLE_CAMPAIGNS_INSUFFICIENT")
    else:state="PASS"
    recommendation=campaign.policy.recommendation(state)
    values=dict(status="PASS" if state=="PASS" else "FAIL",campaign_identity=campaign.campaign_identity,pr265_campaign_identities=tuple(x.pr265_campaign_identity for x in campaign.runs),symbol=campaign.symbol,environment_identity=campaign.environment_identity,policy_identity=campaign.policy.policy_identity,evaluation_window=(campaign.started_at,campaign.expires_at),run_count=len(campaign.runs),campaign_summary=statistics,replay_stability=shadow,runtime_stability=runtime,delivery_reliability=delivery,certification_stability=certification_stable,stable_campaign_count=stable_count,operational_recommendation=recommendation,production_authorized=False,reasons=tuple(dict.fromkeys(reasons)) or ("QUALIFIED_FOR_HUMAN_REVIEW",))
    return QualificationReport(**values,replay_identity=certification_identity("V28_OPERATIONAL_QUALIFICATION_REPORT",values))
