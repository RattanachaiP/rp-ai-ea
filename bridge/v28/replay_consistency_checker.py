"""Independent repeated-run and artifact replay consistency evidence."""
from dataclasses import dataclass
from typing import Any, Callable
from .pipeline_validator import PR265_POLICY, certification_identity


@dataclass(frozen=True)
class ReplayConsistencyReport:
    status: str
    run_count: int
    replay_identities: tuple[str, ...]
    reasons: tuple[str, ...]
    policy_reference: str
    replay_identity: str
    def canonical_payload(self): return {k: getattr(self, k) for k in self.__dataclass_fields__ if k != "replay_identity"}
    def __post_init__(self):
        if self.status not in {"PASS", "FAIL"} or self.run_count < 2: raise ValueError("REPLAY_REPORT_INVALID")
        if self.replay_identity != certification_identity("V28_REPLAY_CONSISTENCY", self.canonical_payload()): raise ValueError("REPLAY_REPORT_IDENTITY_INVALID")


def check_replay(factory: Callable[[], Any], *, run_count: int = 2) -> ReplayConsistencyReport:
    if run_count < 2: raise ValueError("REPLAY_REQUIRES_MULTIPLE_RUNS")
    artifacts = tuple(factory() for _ in range(run_count))
    identities = tuple(getattr(item, "replay_identity", "") for item in artifacts)
    reasons = []
    if any(not value for value in identities): reasons.append("REPLAY_IDENTITY_MISSING")
    if len(set(identities)) != 1: reasons.append("NON_DETERMINISTIC_REPLAY")
    if any(item != artifacts[0] for item in artifacts[1:]): reasons.append("NON_DETERMINISTIC_OUTPUT")
    values = dict(status="FAIL" if reasons else "PASS", run_count=run_count, replay_identities=identities,
                  reasons=tuple(reasons) or ("REPLAY_REPRODUCIBLE",), policy_reference=PR265_POLICY)
    return ReplayConsistencyReport(**values, replay_identity=certification_identity("V28_REPLAY_CONSISTENCY", values))
