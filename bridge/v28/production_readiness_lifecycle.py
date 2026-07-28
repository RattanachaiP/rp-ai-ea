"""Forward-only, human-governed readiness lifecycle; it never deploys."""
from .pipeline_validator import certification_identity
from .production_readiness_report import ProductionReadinessReport, ReadinessLifecycleEvent

TRANSITIONS = {
    "READY_FOR_HUMAN_REVIEW": {"UNDER_HUMAN_REVIEW"},
    "UNDER_HUMAN_REVIEW": {"APPROVED_FOR_DEPLOYMENT", "REJECTED"},
    "APPROVED_FOR_DEPLOYMENT": {"SUPERSEDED"},
    "REJECTED": {"SUPERSEDED"},
}


def transition_readiness(report: ProductionReadinessReport, to_status: str, *, actor_identity: str,
                         reason: str, recorded_at: str) -> ProductionReadinessReport:
    ProductionReadinessReport(**report.__dict__)
    if to_status not in TRANSITIONS.get(report.status, set()):
        raise ValueError("READINESS_LIFECYCLE_TRANSITION_INVALID")
    if not actor_identity.startswith("HUMAN:"):
        raise ValueError("READINESS_HUMAN_IDENTITY_REQUIRED")
    previous = report.approval_history[-1].event_identity if report.approval_history else None
    event_values = dict(sequence=len(report.approval_history) + 1, from_status=report.status,
                        to_status=to_status, actor_identity=actor_identity, reason=reason,
                        recorded_at=recorded_at, previous_event_identity=previous)
    event = ReadinessLifecycleEvent(
        **event_values, event_identity=certification_identity("V28_READINESS_LIFECYCLE_EVENT", event_values))
    values = report.canonical_payload()
    values.update(status=to_status, approval_history=report.approval_history + (event,),
                  reasons=report.reasons + (("HUMAN_APPROVAL_RECORDED",) if to_status == "APPROVED_FOR_DEPLOYMENT" else ()))
    return ProductionReadinessReport(
        **values, report_identity=certification_identity("V28_PRODUCTION_READINESS_REPORT", values))
