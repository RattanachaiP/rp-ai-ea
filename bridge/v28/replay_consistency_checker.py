"""Side-effect-free comparison of immutable replay artifacts."""
from dataclasses import dataclass
from typing import Any, Iterable
from .pipeline_validator import Campaign, PR265_POLICY, certification_identity

@dataclass(frozen=True)
class ReplayPair:
    original: Any; replayed: Any
    def __post_init__(self):
        if callable(self.original) or callable(self.replayed): raise ValueError("REPLAY_CAPABILITY_FORBIDDEN")

@dataclass(frozen=True)
class ReplayConsistencyReport:
    status: str; campaign: Campaign; replay_identities: tuple[str,...]; reasons: tuple[str,...]
    policy_reference: str; replay_identity: str
    def canonical_payload(self): return {k:getattr(self,k) for k in self.__dataclass_fields__ if k!="replay_identity"}
    def __post_init__(self):
        if self.status not in {"PASS","FAIL"} or self.policy_reference!=PR265_POLICY: raise ValueError("REPLAY_REPORT_INVALID")
        if self.replay_identity!=certification_identity("V28_REPLAY_CONSISTENCY",self.canonical_payload()): raise ValueError("REPLAY_REPORT_IDENTITY_INVALID")

def check_replay(campaign: Campaign, pairs: Iterable[ReplayPair]) -> ReplayConsistencyReport:
    pairs=tuple(pairs); reasons=[]; identities=[]
    if not pairs: reasons.append("REPLAY_EVIDENCE_MISSING")
    for pair in pairs:
        left=getattr(pair.original,"replay_identity",None); right=getattr(pair.replayed,"replay_identity",None)
        if not left or left!=right: reasons.append("REPLAY_IDENTITY_MISMATCH")
        if pair.original!=pair.replayed: reasons.append("NON_DETERMINISTIC_OUTPUT")
        identities.extend((left or "MISSING",right or "MISSING"))
    values=dict(status="FAIL" if reasons else "PASS",campaign=campaign,replay_identities=tuple(identities),reasons=tuple(dict.fromkeys(reasons)) or ("REPLAY_REPRODUCIBLE",),policy_reference=PR265_POLICY)
    return ReplayConsistencyReport(**values,replay_identity=certification_identity("V28_REPLAY_CONSISTENCY",values))
