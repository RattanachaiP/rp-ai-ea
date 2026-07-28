"""Read-only audit of readiness evidence and human approval lineage."""
from dataclasses import dataclass

from .pipeline_validator import certification_identity
from .production_readiness_candidate import ProductionReadinessCandidate
from .production_readiness_registry import ProductionReadinessRegistry
from .production_readiness_report import ProductionReadinessReport


@dataclass(frozen=True)
class ProductionReadinessAudit:
    status: str
    candidate_identity: str
    report_identity: str
    checks: tuple[tuple[str, bool], ...]
    findings: tuple[str, ...]
    audit_identity: str

    def canonical_payload(self):
        return {key: getattr(self, key) for key in self.__dataclass_fields__ if key != "audit_identity"}

    def __post_init__(self):
        if self.status not in {"PASS", "FAIL"} or self.audit_identity != certification_identity("V28_PRODUCTION_READINESS_AUDIT", self.canonical_payload()):
            raise ValueError("PRODUCTION_READINESS_AUDIT_INVALID")


def audit_production_readiness(candidate: ProductionReadinessCandidate,
                               registry: ProductionReadinessRegistry,
                               report: ProductionReadinessReport) -> ProductionReadinessAudit:
    integrity = True
    try:
        ProductionReadinessCandidate(**candidate.__dict__)
        ProductionReadinessRegistry(**registry.__dict__)
        ProductionReadinessReport(**report.__dict__)
    except ValueError:
        integrity = False
    events = report.approval_history
    checks = (("integrity", integrity),
              ("qualification_lineage", candidate.qualification_report.campaign_identity in
               tuple(c.campaign_identity for c in candidate.qualification_registry.campaigns)),
              ("campaign_lineage", all(c.lineage_identity == (None if i == 0 else candidate.qualification_registry.campaigns[i-1].campaign_identity)
                                       for i, c in enumerate(candidate.qualification_registry.campaigns))),
              ("policy_version", candidate.policy.policy_identity == registry.policy.policy_identity),
              ("architecture_version", candidate.architecture_version == candidate.policy.required_architecture_version),
              ("repository_commit", report.repository_commit == candidate.repository_commit),
              ("approval_history", all(e.actor_identity.startswith("HUMAN:") for e in events)))
    findings = tuple(name.upper() + "_INVALID" for name, passed in checks if not passed)
    values = dict(status="FAIL" if findings else "PASS", candidate_identity=candidate.candidate_identity,
                  report_identity=report.report_identity, checks=checks, findings=findings or ("AUDIT_COMPLETE",))
    return ProductionReadinessAudit(
        **values, audit_identity=certification_identity("V28_PRODUCTION_READINESS_AUDIT", values))
