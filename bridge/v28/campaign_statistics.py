"""Deterministic aggregate statistics; no thresholds or promotion authority."""
from dataclasses import dataclass
from .pipeline_validator import certification_identity
from .qualification_campaign import ACTIONS, PR266_POLICY, QualificationCampaign

@dataclass(frozen=True)
class CampaignStatistics:
    campaign_count:int;run_count:int;action_counts:tuple[tuple[str,int],...]
    passed_runs:int;failed_runs:int;first_observed_at:str;last_observed_at:str
    policy_reference:str;replay_identity:str
    def canonical_payload(self):return {k:getattr(self,k) for k in self.__dataclass_fields__ if k!="replay_identity"}
    def __post_init__(self):
        if self.campaign_count<1 or self.run_count<1 or self.policy_reference!=PR266_POLICY:raise ValueError("CAMPAIGN_STATISTICS_INVALID")
        if self.replay_identity!=certification_identity("V28_CAMPAIGN_STATISTICS",self.canonical_payload()):raise ValueError("CAMPAIGN_STATISTICS_REPLAY_INVALID")

def aggregate_campaign_statistics(*campaigns:QualificationCampaign)->CampaignStatistics:
    if not campaigns or any(type(x) is not QualificationCampaign for x in campaigns):raise ValueError("CAMPAIGN_STATISTICS_INPUT_INVALID")
    runs=tuple(r for c in campaigns for r in c.runs);times=tuple(r.observed_at for r in runs)
    values=dict(campaign_count=len(campaigns),run_count=len(runs),action_counts=tuple((a,sum(r.action==a for r in runs)) for a in ACTIONS),passed_runs=sum(r.certification.status=="PASS" for r in runs),failed_runs=sum(r.certification.status!="PASS" for r in runs),first_observed_at=min(times),last_observed_at=max(times),policy_reference=PR266_POLICY)
    return CampaignStatistics(**values,replay_identity=certification_identity("V28_CAMPAIGN_STATISTICS",values))
