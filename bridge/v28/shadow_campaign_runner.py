"""Deterministic comparison of repeated BUY, SELL and HOLD qualification runs."""
from dataclasses import dataclass
from .pipeline_validator import certification_identity, report_identity_valid
from .certification_report import CertificationReport
from .qualification_campaign import ACTIONS, PR266_POLICY, QualificationCampaign

@dataclass(frozen=True)
class ShadowCampaignReport:
    status:str; campaign_identity:str; actions:tuple[str,...]; replay_equal:bool
    execution_equal:bool; certification_equal:bool; reasons:tuple[str,...]
    production_authorized:bool; policy_reference:str; replay_identity:str
    def canonical_payload(self):return {k:getattr(self,k) for k in self.__dataclass_fields__ if k!="replay_identity"}
    def __post_init__(self):
        if self.status not in {"PASS","FAIL"} or self.production_authorized is not False or self.policy_reference!=PR266_POLICY:raise ValueError("SHADOW_CAMPAIGN_REPORT_INVALID")
        if self.replay_identity!=certification_identity("V28_SHADOW_CAMPAIGN_REPORT",self.canonical_payload()):raise ValueError("SHADOW_CAMPAIGN_REPORT_REPLAY_INVALID")

def run_shadow_campaign(campaign:QualificationCampaign)->ShadowCampaignReport:
    cohorts={a:tuple(x for x in campaign.runs if x.action==a) for a in ACTIONS};reasons=[]
    coverage=all(len(v)>=2 for v in cohorts.values())
    replay=all(len({x.certification.replay_identity for x in v})==1 for v in cohorts.values())
    execution=all(len({(x.certification.shadow.actions,x.certification.shadow.plan_identities) for x in v})==1 for v in cohorts.values())
    certification=all(len({x.certification.replay_identity for x in v})==1 and all(report_identity_valid(x.certification, CertificationReport, "V28_END_TO_END_CERTIFICATION") and x.certification.status=="PASS" for x in v) for v in cohorts.values())
    if not coverage:reasons.append("REPEATED_BUY_SELL_HOLD_COVERAGE_INCOMPLETE")
    if not replay:reasons.append("REPLAY_INEQUALITY")
    if not execution:reasons.append("EXECUTION_INEQUALITY")
    if not certification:reasons.append("CERTIFICATION_INEQUALITY")
    values=dict(status="FAIL" if reasons else "PASS",campaign_identity=campaign.campaign_identity,actions=tuple(x.action for x in campaign.runs),replay_equal=replay,execution_equal=execution,certification_equal=certification,reasons=tuple(reasons) or ("SHADOW_CAMPAIGN_STABLE",),production_authorized=False,policy_reference=PR266_POLICY)
    return ShadowCampaignReport(**values,replay_identity=certification_identity("V28_SHADOW_CAMPAIGN_REPORT",values))
