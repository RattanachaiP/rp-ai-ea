"""Compare scenario-equivalent semantic projections, never whole run artifacts."""
from dataclasses import dataclass
from .pipeline_validator import certification_identity,report_identity_valid
from .certification_report import CertificationReport
from .qualification_campaign import ACTIONS,QualificationCampaign,semantic_output_identity
@dataclass(frozen=True)
class ShadowCampaignReport:
    status:str;campaign_identity:str;policy_identity:str;symbol:str;environment_identity:str
    evaluation_window:tuple[str,str];run_count:int;scenario_inputs_equal:bool
    semantic_outputs_equal:bool;certifications_valid:bool;reasons:tuple[str,...];production_authorized:bool;replay_identity:str
    def canonical_payload(self):return {k:getattr(self,k) for k in self.__dataclass_fields__ if k!="replay_identity"}
    def __post_init__(self):
        if self.status not in {"PASS","FAIL"} or self.production_authorized is not False:raise ValueError("SHADOW_CAMPAIGN_REPORT_INVALID")
        if self.replay_identity!=certification_identity("V28_SHADOW_CAMPAIGN_REPORT",self.canonical_payload()):raise ValueError("SHADOW_CAMPAIGN_REPORT_REPLAY_INVALID")
def run_shadow_campaign(campaign:QualificationCampaign)->ShadowCampaignReport:
    cohorts={a:tuple(x for x in campaign.runs if x.scenario.action==a) for a in ACTIONS};reasons=[]
    inputs=all(len({(x.scenario.scenario_identity,x.scenario.normalized_input_identity) for x in cohort})==1 for cohort in cohorts.values())
    outputs=all(len({semantic_output_identity(x.certification,a) for x in cohort})==1 and all(semantic_output_identity(x.certification,a)==x.scenario.expected_semantic_output_identity for x in cohort) for a,cohort in cohorts.items())
    certifications=all(report_identity_valid(x.certification,CertificationReport,"V28_END_TO_END_CERTIFICATION") and x.certification.status=="PASS" for x in campaign.runs)
    if not inputs:reasons.append("SCENARIO_INPUT_PROJECTION_DRIFT")
    if not outputs:reasons.append("SEMANTIC_OUTPUT_PROJECTION_DRIFT")
    if not certifications:reasons.append("CERTIFICATION_INSTABILITY")
    values=dict(status="FAIL" if reasons else "PASS",campaign_identity=campaign.campaign_identity,policy_identity=campaign.policy.policy_identity,symbol=campaign.symbol,environment_identity=campaign.environment_identity,evaluation_window=(campaign.started_at,campaign.expires_at),run_count=len(campaign.runs),scenario_inputs_equal=inputs,semantic_outputs_equal=outputs,certifications_valid=certifications,reasons=tuple(reasons) or ("SCENARIO_REPLAY_STABLE",),production_authorized=False)
    return ShadowCampaignReport(**values,replay_identity=certification_identity("V28_SHADOW_CAMPAIGN_REPORT",values))
