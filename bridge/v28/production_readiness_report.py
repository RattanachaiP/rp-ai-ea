"""Fail-closed immutable reports consuming authoritative PR266 semantics."""
from dataclasses import dataclass
import json
from typing import Any, Mapping

from .execution_plan import parse_utc
from .pipeline_validator import certification_identity
from .production_readiness_candidate import ProductionReadinessCandidate
from .production_readiness_registry import ProductionReadinessRegistry

STATUSES = {"NOT_READY", "READY_FOR_HUMAN_REVIEW", "UNDER_HUMAN_REVIEW",
            "APPROVED_FOR_DEPLOYMENT", "REJECTED", "SUPERSEDED"}
ROLES = {"REVIEWER", "APPROVER", "GOVERNANCE_OWNER"}
TRANSITIONS = {"READY_FOR_HUMAN_REVIEW": {"UNDER_HUMAN_REVIEW"},
               "UNDER_HUMAN_REVIEW": {"APPROVED_FOR_DEPLOYMENT", "REJECTED"},
               "APPROVED_FOR_DEPLOYMENT": {"SUPERSEDED"}, "REJECTED": {"SUPERSEDED"}}


def _plain(value: Any) -> Any:
    if hasattr(value, "__dataclass_fields__"):
        return {key: _plain(getattr(value, key)) for key in value.__dataclass_fields__}
    if isinstance(value, Mapping):
        return {str(key): _plain(item) for key, item in value.items()}
    if isinstance(value, (tuple, list)):
        return [_plain(item) for item in value]
    return value


@dataclass(frozen=True)
class GovernedHumanIdentity:
    subject_identity: str
    roles: tuple[str, ...]
    authority_reference: str
    identity: str

    def canonical_payload(self):
        return {key: getattr(self, key) for key in self.__dataclass_fields__ if key != "identity"}

    def __post_init__(self):
        if (not self.subject_identity or not self.authority_reference.startswith("HUMAN_IDENTITY_REGISTRY:") or
                not self.roles or tuple(sorted(set(self.roles))) != self.roles or any(r not in ROLES for r in self.roles)):
            raise ValueError("GOVERNED_HUMAN_IDENTITY_INVALID")
        if self.identity != certification_identity("V28_GOVERNED_HUMAN_IDENTITY", self.canonical_payload()):
            raise ValueError("GOVERNED_HUMAN_IDENTITY_DIGEST_INVALID")


def create_governed_human_identity(**values) -> GovernedHumanIdentity:
    normalized = dict(values)
    normalized["roles"] = tuple(sorted(set(normalized["roles"])))
    return GovernedHumanIdentity(
        **normalized, identity=certification_identity("V28_GOVERNED_HUMAN_IDENTITY", normalized))


@dataclass(frozen=True)
class ReadinessLifecycleEvent:
    sequence: int
    from_status: str
    to_status: str
    actor: GovernedHumanIdentity
    acting_role: str
    reason: str
    recorded_at: str
    previous_event_identity: str | None
    event_identity: str

    def canonical_payload(self):
        return {key: getattr(self, key) for key in self.__dataclass_fields__ if key != "event_identity"}

    def __post_init__(self):
        GovernedHumanIdentity(**self.actor.__dict__)
        parse_utc(self.recorded_at)
        if (self.sequence < 1 or self.from_status not in STATUSES or self.to_status not in STATUSES or
                self.acting_role not in self.actor.roles or not self.reason or
                (self.sequence == 1) != (self.previous_event_identity is None)):
            raise ValueError("READINESS_LIFECYCLE_EVENT_INVALID")
        if self.event_identity != certification_identity("V28_READINESS_LIFECYCLE_EVENT", self.canonical_payload()):
            raise ValueError("READINESS_LIFECYCLE_EVENT_IDENTITY_INVALID")


@dataclass(frozen=True)
class ProductionReadinessReport:
    status: str
    candidate_identity: str
    readiness_registry_identity: str
    qualification_registry_identity: str
    qualification_report_identity: str
    policy_identity: str
    architecture_version: str
    repository_evidence_identity: str
    repository_commit: str
    qualified_campaigns: int
    stable_campaigns: int
    runtime_duration_seconds: float
    failure_rate: float
    recovery_rate: float
    evidence_density_per_hour: float
    approval_history: tuple[ReadinessLifecycleEvent, ...]
    reasons: tuple[str, ...]
    production_authorized: bool
    deployment_performed: bool
    report_identity: str

    def canonical_payload(self):
        return {key: getattr(self, key) for key in self.__dataclass_fields__ if key != "report_identity"}

    def to_json(self):
        return json.dumps(_plain(self), sort_keys=True, separators=(",", ":"), allow_nan=False)

    def __post_init__(self):
        if (self.status not in STATUSES or self.production_authorized is not False or
                self.deployment_performed is not False or min(self.qualified_campaigns, self.stable_campaigns) < 0 or
                min(self.runtime_duration_seconds, self.failure_rate, self.recovery_rate,
                    self.evidence_density_per_hour) < 0):
            raise ValueError("PRODUCTION_READINESS_REPORT_INVALID")
        if not self.approval_history and self.status not in {"NOT_READY", "READY_FOR_HUMAN_REVIEW"}:
            raise ValueError("READINESS_APPROVAL_HISTORY_REQUIRED")
        previous, current, previous_time, reviewer = None, "READY_FOR_HUMAN_REVIEW", None, None
        for index, event in enumerate(self.approval_history, 1):
            ReadinessLifecycleEvent(**event.__dict__)
            event_time = parse_utc(event.recorded_at)
            required_role = "REVIEWER" if event.to_status == "UNDER_HUMAN_REVIEW" else (
                "APPROVER" if event.to_status in {"APPROVED_FOR_DEPLOYMENT", "REJECTED"} else "GOVERNANCE_OWNER")
            if (event.sequence != index or event.previous_event_identity != previous or
                    event.from_status != current or event.to_status not in TRANSITIONS.get(current, set()) or
                    event.acting_role != required_role or (previous_time is not None and event_time <= previous_time)):
                raise ValueError("READINESS_APPROVAL_LINEAGE_INVALID")
            if event.to_status == "UNDER_HUMAN_REVIEW":
                reviewer = event.actor.subject_identity
            elif event.to_status in {"APPROVED_FOR_DEPLOYMENT", "REJECTED"} and event.actor.subject_identity == reviewer:
                raise ValueError("READINESS_SELF_APPROVAL_PROHIBITED")
            previous, current, previous_time = event.event_identity, event.to_status, event_time
        if self.approval_history and current != self.status:
            raise ValueError("READINESS_APPROVAL_STATUS_MISMATCH")
        if self.report_identity != certification_identity("V28_PRODUCTION_READINESS_REPORT", self.canonical_payload()):
            raise ValueError("PRODUCTION_READINESS_REPORT_IDENTITY_INVALID")


def authoritative_metrics(candidate: ProductionReadinessCandidate):
    """Recompute metrics without interpreting a campaign's qualification outcome.

    PR266's consecutive stable count is the authoritative qualified/stable campaign semantic.
    Coverage is the sum of each integrity-validated campaign's first-to-last run interval, so
    inter-campaign gaps never count. Density is observations per validated coverage hour.
    """
    campaigns, stats = candidate.qualification_registry.campaigns, candidate.campaign_statistics
    coverage = sum((parse_utc(c.runs[-1].evaluation_time) - parse_utc(c.runs[0].evaluation_time)).total_seconds()
                   for c in campaigns)
    failure_rate = stats.failed_runs / stats.run_count
    recoveries = sum(run.recovery.status != "NONE" for campaign in campaigns for run in campaign.runs)
    recovery_rate = recoveries / stats.run_count
    density = stats.run_count / (coverage / 3600) if coverage > 0 else 0.0
    qualified = candidate.qualification_report.stable_campaign_count
    return qualified, qualified, coverage, failure_rate, recovery_rate, density


def build_production_readiness_report(candidate: ProductionReadinessCandidate,
                                      registry: ProductionReadinessRegistry) -> ProductionReadinessReport:
    # Integrity failures are contract failures, never NOT_READY assessments.
    ProductionReadinessCandidate(**candidate.__dict__)
    ProductionReadinessRegistry(**registry.__dict__)
    if candidate.policy.policy_identity != registry.policy.policy_identity:
        raise ValueError("READINESS_REPORT_POLICY_MISMATCH")
    if not registry.candidates or registry.candidates[-1].candidate_identity != candidate.candidate_identity:
        raise ValueError("READINESS_REPORT_CANDIDATE_NOT_CURRENT")
    qualified, stable, duration, failure_rate, recovery_rate, density = authoritative_metrics(candidate)
    policy, qualification = candidate.policy, candidate.qualification_report
    checks = ((qualified >= policy.minimum_qualified_campaigns, "QUALIFIED_CAMPAIGNS_INSUFFICIENT"),
              (stable >= policy.minimum_stable_campaigns, "STABLE_CAMPAIGNS_INSUFFICIENT"),
              (duration >= policy.minimum_runtime_duration_seconds, "RUNTIME_DURATION_INSUFFICIENT"),
              (failure_rate <= policy.maximum_failure_rate, "FAILURE_RATE_EXCEEDED"),
              (recovery_rate <= policy.maximum_recovery_rate, "RECOVERY_RATE_EXCEEDED"),
              (density >= policy.minimum_evidence_density_per_hour, "EVIDENCE_DENSITY_INSUFFICIENT"),
              (qualification.status == "PASS" and qualification.operational_recommendation == "READY FOR HUMAN REVIEW",
               "QUALIFICATION_NOT_READY_FOR_HUMAN_REVIEW"))
    reasons = tuple(reason for passed, reason in checks if not passed)
    repository = candidate.repository_evidence
    values = dict(status="NOT_READY" if reasons else "READY_FOR_HUMAN_REVIEW",
                  candidate_identity=candidate.candidate_identity, readiness_registry_identity=registry.registry_identity,
                  qualification_registry_identity=candidate.qualification_registry.registry_identity,
                  qualification_report_identity=qualification.replay_identity, policy_identity=policy.policy_identity,
                  architecture_version=candidate.architecture_version,
                  repository_evidence_identity=repository.evidence_identity, repository_commit=repository.commit_sha,
                  qualified_campaigns=qualified, stable_campaigns=stable, runtime_duration_seconds=duration,
                  failure_rate=failure_rate, recovery_rate=recovery_rate, evidence_density_per_hour=density,
                  approval_history=(), reasons=reasons or ("EVIDENCE_SUFFICIENT_FOR_HUMAN_REVIEW",),
                  production_authorized=False, deployment_performed=False)
    return ProductionReadinessReport(
        **values, report_identity=certification_identity("V28_PRODUCTION_READINESS_REPORT", values))
