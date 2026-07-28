"""Independent, read-only audit of evidence, metrics, chronology and approval."""
from dataclasses import dataclass

from .execution_plan import parse_utc
from .pipeline_validator import certification_identity
from .production_readiness_candidate import ProductionReadinessCandidate, RepositoryEvidence
from .production_readiness_registry import ProductionReadinessRegistry
from .production_readiness_report import (ProductionReadinessReport, ReadinessLifecycleEvent,
                                          TRANSITIONS)


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
        if (self.status not in {"PASS", "FAIL"} or
                self.audit_identity != certification_identity("V28_PRODUCTION_READINESS_AUDIT", self.canonical_payload())):
            raise ValueError("PRODUCTION_READINESS_AUDIT_INVALID")


def audit_production_readiness(candidate: ProductionReadinessCandidate,
                               registry: ProductionReadinessRegistry,
                               report: ProductionReadinessReport) -> ProductionReadinessAudit:
    integrity = True
    try:
        ProductionReadinessCandidate(**candidate.__dict__)
        ProductionReadinessRegistry(**registry.__dict__)
        ProductionReadinessReport(**report.__dict__)
        RepositoryEvidence(**candidate.repository_evidence.__dict__)
    except (TypeError, ValueError):
        integrity = False
    campaigns, stats = candidate.qualification_registry.campaigns, candidate.campaign_statistics
    coverage = sum((parse_utc(c.runs[-1].evaluation_time) - parse_utc(c.runs[0].evaluation_time)).total_seconds()
                   for c in campaigns)
    failure = stats.failed_runs / stats.run_count
    recovery = sum(r.recovery.status != "NONE" for c in campaigns for r in c.runs) / stats.run_count
    density = stats.run_count / (coverage / 3600) if coverage > 0 else 0.0
    authoritative_count = candidate.qualification_report.stable_campaign_count
    metrics = (report.qualified_campaigns, report.stable_campaigns, report.runtime_duration_seconds,
               report.failure_rate, report.recovery_rate, report.evidence_density_per_hour)
    expected_metrics = (authoritative_count, authoritative_count, coverage, failure, recovery, density)
    evidence_binding = (report.candidate_identity == candidate.candidate_identity and
                        report.readiness_registry_identity == registry.registry_identity and
                        report.qualification_registry_identity == candidate.qualification_registry.registry_identity and
                        report.qualification_report_identity == candidate.qualification_report.replay_identity and
                        report.repository_evidence_identity == candidate.repository_evidence.evidence_identity and
                        report.repository_commit == candidate.repository_evidence.commit_sha)
    chronology = roles = lineage = status = True
    current, previous, previous_time, reviewer = "READY_FOR_HUMAN_REVIEW", None, None, None
    for index, event in enumerate(report.approval_history, 1):
        try:
            ReadinessLifecycleEvent(**event.__dict__)
            timestamp = parse_utc(event.recorded_at)
        except (TypeError, ValueError):
            chronology = roles = lineage = status = False
            break
        required = "REVIEWER" if event.to_status == "UNDER_HUMAN_REVIEW" else (
            "APPROVER" if event.to_status in {"APPROVED_FOR_DEPLOYMENT", "REJECTED"} else "GOVERNANCE_OWNER")
        chronology &= previous_time is None or timestamp > previous_time
        lineage &= event.sequence == index and event.previous_event_identity == previous
        status &= event.from_status == current and event.to_status in TRANSITIONS.get(current, set())
        roles &= event.acting_role == required and required in event.actor.roles
        if event.to_status == "UNDER_HUMAN_REVIEW":
            reviewer = event.actor.subject_identity
        elif event.to_status in {"APPROVED_FOR_DEPLOYMENT", "REJECTED"}:
            roles &= event.actor.subject_identity != reviewer
        current, previous, previous_time = event.to_status, event.event_identity, timestamp
    status &= current == report.status if report.approval_history else report.status in {"NOT_READY", "READY_FOR_HUMAN_REVIEW"}
    policy = candidate.policy
    ready = (authoritative_count >= policy.minimum_qualified_campaigns and
             authoritative_count >= policy.minimum_stable_campaigns and
             coverage >= policy.minimum_runtime_duration_seconds and failure <= policy.maximum_failure_rate and
             recovery <= policy.maximum_recovery_rate and density >= policy.minimum_evidence_density_per_hour and
             candidate.qualification_report.status == "PASS" and
             candidate.qualification_report.operational_recommendation == "READY FOR HUMAN REVIEW")
    initial_status_valid = bool(report.approval_history) or report.status == (
        "READY_FOR_HUMAN_REVIEW" if ready else "NOT_READY")
    checks = (("integrity", integrity),
              ("candidate_is_current", bool(registry.candidates) and registry.candidates[-1] == candidate),
              ("policy_binding", candidate.policy.policy_identity == registry.policy.policy_identity == report.policy_identity),
              ("qualification_lineage", candidate.qualification_report.campaign_identity == campaigns[-1].campaign_identity),
              ("campaign_lineage", all(c.lineage_identity == (None if i == 0 else campaigns[i-1].campaign_identity)
                                       for i, c in enumerate(campaigns))),
              ("architecture_version", candidate.architecture_version == candidate.policy.required_architecture_version),
              ("repository_evidence", evidence_binding), ("metrics", metrics == expected_metrics),
              ("chronology", chronology), ("roles", roles), ("approval_lineage", lineage),
              ("lifecycle_status", status), ("readiness_status", initial_status_valid))
    findings = tuple(name.upper() + "_INVALID" for name, passed in checks if not passed)
    values = dict(status="FAIL" if findings else "PASS", candidate_identity=candidate.candidate_identity,
                  report_identity=report.report_identity, checks=checks, findings=findings or ("AUDIT_COMPLETE",))
    return ProductionReadinessAudit(
        **values, audit_identity=certification_identity("V28_PRODUCTION_READINESS_AUDIT", values))
