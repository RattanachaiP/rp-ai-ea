"""Policy-bound continuity checks over authoritative runtime samples."""
from dataclasses import dataclass
from .execution_plan import parse_utc
from .pipeline_validator import certification_identity
from .qualification_campaign import QualificationCampaign

@dataclass(frozen=True)
class RuntimeStabilityReport:
    status:str;campaign_identity:str;policy_identity:str;symbol:str;environment_identity:str
    evaluation_window:tuple[str,str];sample_count:int;heartbeat_continuous:bool
    sequence_continuous:bool;health_stable:bool;reasons:tuple[str,...];replay_identity:str
    def canonical_payload(self):return {k:getattr(self,k) for k in self.__dataclass_fields__ if k!="replay_identity"}
    def __post_init__(self):
        if self.status not in {"PASS","FAIL"}:raise ValueError("RUNTIME_STABILITY_REPORT_INVALID")
        if self.replay_identity!=certification_identity("V28_RUNTIME_STABILITY_REPORT",self.canonical_payload()):raise ValueError("RUNTIME_STABILITY_REPORT_REPLAY_INVALID")

def monitor_runtime_stability(campaign:QualificationCampaign)->RuntimeStabilityReport:
    samples=tuple(x.runtime_sample for x in campaign.runs);policy=campaign.policy;reasons=[]
    heartbeats=tuple(parse_utc(x.heartbeat_at) for x in samples);observed=tuple(parse_utc(x.observed_at) for x in samples)
    heartbeat=heartbeats==tuple(sorted(heartbeats)) and all(0<=(b-a).total_seconds()<=policy.maximum_heartbeat_gap_seconds for a,b in zip(heartbeats,heartbeats[1:])) and all(h<=o for h,o in zip(heartbeats,observed))
    sequences=tuple(x.runtime_sequence for x in samples);sequence=not policy.require_strict_runtime_sequence or all(b==a+1 for a,b in zip(sequences,sequences[1:]))
    health=all(x.health_status=="HEALTHY" and x.health.healthy and x.environment_identity==campaign.environment_identity for x in samples)
    if not heartbeat:reasons.append("RUNTIME_HEARTBEAT_GAP_OR_CHRONOLOGY_INVALID")
    if not sequence:reasons.append("RUNTIME_SEQUENCE_GAP")
    if not health:reasons.append("RUNTIME_HEALTH_UNSTABLE")
    values=dict(status="FAIL" if reasons else "PASS",campaign_identity=campaign.campaign_identity,policy_identity=policy.policy_identity,symbol=campaign.symbol,environment_identity=campaign.environment_identity,evaluation_window=(campaign.started_at,campaign.expires_at),sample_count=len(samples),heartbeat_continuous=heartbeat,sequence_continuous=sequence,health_stable=health,reasons=tuple(reasons) or ("RUNTIME_STABLE",))
    return RuntimeStabilityReport(**values,replay_identity=certification_identity("V28_RUNTIME_STABILITY_REPORT",values))
