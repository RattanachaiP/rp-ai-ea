"""Fail-closed, immutable production-readiness assessment reports."""
from dataclasses import dataclass
import json
from typing import Any, Mapping

from .execution_plan import parse_utc
from .pipeline_validator import certification_identity
from .production_readiness_candidate import ProductionReadinessCandidate
from .production_readiness_registry import ProductionReadinessRegistry

STATUSES = {"NOT_READY", "READY_FOR_HUMAN_REVIEW", "UNDER_HUMAN_REVIEW",
            "APPROVED_FOR_DEPLOYMENT", "REJECTED", "SUPERSEDED"}


def _plain(value: Any) -> Any:
    if hasattr(value, "__dataclass_fields__"):
        return {key: _plain(getattr(value, key)) for key in value.__dataclass_fields__}
    if isinstance(value, Mapping):
        return {str(key): _plain(item) for key, item in value.items()}
    if isinstance(value, (tuple, list)):
        return [_plain(item) for item in value]
    return value


@dataclass(frozen=True)
class ReadinessLifecycleEvent:
    sequence: int
    from_status: str
    to_status: str
    actor_identity: str
    reason: str
    recorded_at: str
    previous_event_identity: str | None
    event_identity: str

    def canonical_payload(self):
        return {key: getattr(self, key) for key in self.__dataclass_fields__ if key != "event_identity"}

    def __post_init__(self):
        parse_utc(self.recorded_at)
        if (self.sequence < 1 or self.from_status not in STATUSES or self.to_status not in STATUSES or
                not self.actor_identity or not self.reason or
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
        if self.status not in STATUSES or self.production_authorized is not False or self.deployment_performed is not False:
            raise ValueError("PRODUCTION_READINESS_REPORT_INVALID")
        if not self.approval_history and self.status not in {"NOT_READY", "READY_FOR_HUMAN_REVIEW"}:
            raise ValueError("READINESS_APPROVAL_HISTORY_REQUIRED")
        previous = None
        current = "READY_FOR_HUMAN_REVIEW"
        allowed = {"READY_FOR_HUMAN_REVIEW": {"UNDER_HUMAN_REVIEW"},
                   "UNDER_HUMAN_REVIEW": {"APPROVED_FOR_DEPLOYMENT", "REJECTED"},
                   "APPROVED_FOR_DEPLOYMENT": {"SUPERSEDED"}, "REJECTED": {"SUPERSEDED"}}
        for index, event in enumerate(self.approval_history, 1):
            ReadinessLifecycleEvent(**event.__dict__)
            if (event.sequence != index or event.previous_event_identity != previous or
                    event.from_status != current or event.to_status not in allowed.get(current, set()) or
                    not event.actor_identity.startswith("HUMAN:")):
                raise ValueError("READINESS_APPROVAL_LINEAGE_INVALID")
            previous = event.event_identity
            current = event.to_status
        if self.approval_history and current != self.status:
            raise ValueError("READINESS_APPROVAL_STATUS_MISMATCH")
        if self.report_identity != certification_identity("V28_PRODUCTION_READINESS_REPORT", self.canonical_payload()):
            raise ValueError("PRODUCTION_READINESS_REPORT_IDENTITY_INVALID")


def build_production_readiness_report(candidate: ProductionReadinessCandidate,
                                      registry: ProductionReadinessRegistry) -> ProductionReadinessReport:
    reasons = []
    try:
        ProductionReadinessCandidate(**candidate.__dict__)
        ProductionReadinessRegistry(**registry.__dict__)
    except ValueError:
        reasons.append("INTEGRITY_INVALID")
    if not registry.candidates or registry.candidates[-1].candidate_identity != candidate.candidate_identity:
        reasons.append("CANDIDATE_NOT_CURRENT")
    stats = candidate.campaign_statistics
    campaigns = candidate.qualification_registry.campaigns
    from .delivery_reliability_validator import validate_delivery_reliability
    from .runtime_stability_monitor import monitor_runtime_stability
    from .shadow_campaign_runner import run_shadow_campaign
    campaign_passes = tuple(
        monitor_runtime_stability(c).status == run_shadow_campaign(c).status ==
        validate_delivery_reliability(c).status == "PASS" and
        all(run.certification.status == "PASS" for run in c.runs) for c in campaigns)
    qualified = sum(campaign_passes)
    stable = 0
    for passed in reversed(campaign_passes):
        if not passed:
            break
        stable += 1
    first = parse_utc(stats.first_observed_at)
    last = parse_utc(stats.last_observed_at)
    duration = (last - first).total_seconds()
    failure_rate = stats.failed_runs / stats.run_count
    recoveries = sum(run.recovery.status != "NONE" for campaign in campaigns for run in campaign.runs)
    recovery_rate = recoveries / stats.run_count
    density = (stats.run_count - 1) / (duration / 3600) if duration > 0 else 0.0
    policy = candidate.policy
    checks = ((qualified >= policy.minimum_qualified_campaigns, "QUALIFIED_CAMPAIGNS_INSUFFICIENT"),
              (stable >= policy.minimum_stable_campaigns, "STABLE_CAMPAIGNS_INSUFFICIENT"),
              (duration >= policy.minimum_runtime_duration_seconds, "RUNTIME_DURATION_INSUFFICIENT"),
              (failure_rate <= policy.maximum_failure_rate, "FAILURE_RATE_EXCEEDED"),
              (recovery_rate <= policy.maximum_recovery_rate, "RECOVERY_RATE_EXCEEDED"),
              (density >= policy.minimum_evidence_density_per_hour, "EVIDENCE_DENSITY_INSUFFICIENT"),
              (candidate.qualification_report.status == "PASS", "QUALIFICATION_NOT_PASSED"))
    reasons.extend(reason for passed, reason in checks if not passed)
    values = dict(status="NOT_READY" if reasons else "READY_FOR_HUMAN_REVIEW",
                  candidate_identity=candidate.candidate_identity,
                  readiness_registry_identity=registry.registry_identity,
                  qualification_registry_identity=candidate.qualification_registry.registry_identity,
                  qualification_report_identity=candidate.qualification_report.replay_identity,
                  policy_identity=policy.policy_identity, architecture_version=candidate.architecture_version,
                  repository_commit=candidate.repository_commit, qualified_campaigns=qualified,
                  stable_campaigns=stable, runtime_duration_seconds=duration, failure_rate=failure_rate,
                  recovery_rate=recovery_rate, evidence_density_per_hour=density, approval_history=(),
                  reasons=tuple(dict.fromkeys(reasons)) or ("EVIDENCE_SUFFICIENT_FOR_HUMAN_REVIEW",),
                  production_authorized=False, deployment_performed=False)
    return ProductionReadinessReport(
        **values, report_identity=certification_identity("V28_PRODUCTION_READINESS_REPORT", values))
