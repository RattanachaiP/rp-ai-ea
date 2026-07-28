"""Read-only runtime continuity and corruption monitoring for PR266."""
from dataclasses import dataclass
from typing import Iterable
from .execution_plan import parse_utc
from .pipeline_validator import certification_identity, report_identity_valid
from .certification_report import CertificationReport
from .qualification_campaign import PR266_POLICY, QualificationCampaign

@dataclass(frozen=True)
class RuntimeStabilityReport:
    status: str
    campaign_identity: str
    sample_count: int
    heartbeat_continuous: bool
    sequence_continuous: bool
    replay_stable: bool
    state_uncorrupted: bool
    reasons: tuple[str, ...]
    policy_reference: str
    replay_identity: str
    def canonical_payload(self): return {k:getattr(self,k) for k in self.__dataclass_fields__ if k != "replay_identity"}
    def __post_init__(self):
        if self.status not in {"PASS","FAIL"} or self.policy_reference != PR266_POLICY:
            raise ValueError("RUNTIME_STABILITY_REPORT_INVALID")
        if self.replay_identity != certification_identity("V28_RUNTIME_STABILITY_REPORT", self.canonical_payload()):
            raise ValueError("RUNTIME_STABILITY_REPORT_REPLAY_INVALID")

def monitor_runtime_stability(campaign: QualificationCampaign, *, maximum_heartbeat_gap_seconds: float) -> RuntimeStabilityReport:
    if type(campaign) is not QualificationCampaign or type(maximum_heartbeat_gap_seconds) not in (int,float) or maximum_heartbeat_gap_seconds <= 0:
        raise ValueError("RUNTIME_STABILITY_INPUT_INVALID")
    runs=campaign.runs; reasons=[]
    times=tuple(parse_utc(x.observed_at) for x in runs)
    heartbeat=all(0 <= (b-a).total_seconds() <= maximum_heartbeat_gap_seconds for a,b in zip(times,times[1:]))
    sequence=tuple(x.ordinal for x in runs)==tuple(range(1,len(runs)+1))
    # Exact replay output must remain equal within each action cohort.
    replay=all(len({x.certification.replay_identity for x in runs if x.action==action}) == 1 for action in {x.action for x in runs})
    state=all(report_identity_valid(x.certification, CertificationReport, "V28_END_TO_END_CERTIFICATION") and x.certification.status=="PASS" and x.runtime_health_identity for x in runs)
    if not heartbeat: reasons.append("HEARTBEAT_DISCONTINUITY")
    if not sequence: reasons.append("SEQUENCE_DISCONTINUITY")
    if not replay: reasons.append("REPLAY_DRIFT")
    if not state: reasons.append("RUNTIME_STATE_CORRUPTION_OR_UNHEALTHY")
    values=dict(status="FAIL" if reasons else "PASS",campaign_identity=campaign.campaign_identity,sample_count=len(runs),heartbeat_continuous=heartbeat,sequence_continuous=sequence,replay_stable=replay,state_uncorrupted=state,reasons=tuple(reasons) or ("RUNTIME_STABLE",),policy_reference=PR266_POLICY)
    return RuntimeStabilityReport(**values,replay_identity=certification_identity("V28_RUNTIME_STABILITY_REPORT",values))
