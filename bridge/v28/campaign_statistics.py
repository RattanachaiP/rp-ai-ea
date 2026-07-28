"""Canonical statistics over one integrity-verified qualification registry."""
from dataclasses import dataclass
from datetime import timezone
from .execution_plan import parse_utc
from .pipeline_validator import certification_identity
from .qualification_campaign import ACTIONS
from .qualification_registry import QualificationRegistry

def utc(value:str)->str:return parse_utc(value).astimezone(timezone.utc).isoformat().replace("+00:00","Z")
@dataclass(frozen=True)
class CampaignStatistics:
    registry_identity:str;policy_identity:str;campaign_identities:tuple[str,...]
    campaign_count:int;run_count:int;action_counts:tuple[tuple[str,int],...]
    passed_runs:int;failed_runs:int;first_observed_at:str;last_observed_at:str;replay_identity:str
    def canonical_payload(self):return {k:getattr(self,k) for k in self.__dataclass_fields__ if k!="replay_identity"}
    def __post_init__(self):
        if self.campaign_count<1 or self.run_count<1:raise ValueError("CAMPAIGN_STATISTICS_INVALID")
        if self.replay_identity!=certification_identity("V28_CAMPAIGN_STATISTICS",self.canonical_payload()):raise ValueError("CAMPAIGN_STATISTICS_REPLAY_INVALID")
def aggregate_campaign_statistics(registry:QualificationRegistry)->CampaignStatistics:
    # Reconstruction revalidates generation, predecessor metadata, campaign uniqueness and lineage.
    QualificationRegistry(**registry.__dict__)
    if not registry.campaigns:raise ValueError("CAMPAIGN_STATISTICS_EMPTY")
    runs=tuple(r for c in registry.campaigns for r in c.runs);times=tuple(parse_utc(r.evaluation_time) for r in runs)
    run_pass=lambda r:r.pipeline.status==r.delivery.status==r.certification.status=="PASS" and r.certification.replay.status=="PASS" and r.receipt.status=="DELIVERED" and r.recovery.status=="NONE"
    values=dict(registry_identity=registry.registry_identity,policy_identity=registry.policy.policy_identity,campaign_identities=tuple(c.campaign_identity for c in registry.campaigns),campaign_count=len(registry.campaigns),run_count=len(runs),action_counts=tuple((a,sum(r.scenario.action==a for r in runs)) for a in ACTIONS),passed_runs=sum(run_pass(r) for r in runs),failed_runs=sum(not run_pass(r) for r in runs),first_observed_at=utc(min(times).isoformat()),last_observed_at=utc(max(times).isoformat()))
    return CampaignStatistics(**values,replay_identity=certification_identity("V28_CAMPAIGN_STATISTICS",values))
