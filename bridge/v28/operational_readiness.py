"""Fail-closed V28 operational-readiness decision (never production authority)."""
from dataclasses import dataclass
from typing import Any
from .pipeline_validator import PR265_POLICY, certification_identity

@dataclass(frozen=True)
class OperationalReadinessReport:
    status: str; readiness: str; evidence_identities: tuple[str, ...]; failures: tuple[str, ...]
    production_authorized: bool; authority_statement: str; policy_reference: str; replay_identity: str
    def canonical_payload(self): return {k: getattr(self, k) for k in self.__dataclass_fields__ if k != "replay_identity"}
    def __post_init__(self):
        if self.status not in {"PASS", "FAIL"} or self.readiness not in {"VALIDATION_READY", "READINESS_DENIED"}: raise ValueError("OPERATIONAL_READINESS_INVALID")
        if self.production_authorized is not False or self.authority_statement != "V27_REMAINS_SOLE_PRODUCTION_AUTHORITY": raise ValueError("PRODUCTION_AUTHORITY_INVALID")
        if self.replay_identity != certification_identity("V28_OPERATIONAL_READINESS", self.canonical_payload()): raise ValueError("OPERATIONAL_READINESS_REPLAY_INVALID")

def assess_operational_readiness(*reports: Any) -> OperationalReadinessReport:
    failures = []; identities = []
    if not reports: failures.append("CERTIFICATION_EVIDENCE_MISSING")
    for report in reports:
        replay = getattr(report, "replay_identity", "")
        if not replay: failures.append(f"{type(report).__name__.upper()}_IDENTITY_MISSING")
        else: identities.append(replay)
        if getattr(report, "status", None) != "PASS": failures.append(f"{type(report).__name__.upper()}_NOT_PASS")
    values = dict(status="FAIL" if failures else "PASS", readiness="READINESS_DENIED" if failures else "VALIDATION_READY",
                  evidence_identities=tuple(identities), failures=tuple(failures), production_authorized=False,
                  authority_statement="V27_REMAINS_SOLE_PRODUCTION_AUTHORITY", policy_reference=PR265_POLICY)
    return OperationalReadinessReport(**values, replay_identity=certification_identity("V28_OPERATIONAL_READINESS", values))
