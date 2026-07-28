"""Forward-only role-governed readiness lifecycle; it never deploys."""
from .execution_plan import parse_utc
from .pipeline_validator import certification_identity
from .production_readiness_report import (GovernedHumanIdentity, ProductionReadinessReport,
                                          ReadinessLifecycleEvent, TRANSITIONS)


def transition_readiness(report: ProductionReadinessReport, to_status: str, *,
                         actor: GovernedHumanIdentity, acting_role: str, reason: str,
                         recorded_at: str) -> ProductionReadinessReport:
    ProductionReadinessReport(**report.__dict__)
    GovernedHumanIdentity(**actor.__dict__)
    if to_status not in TRANSITIONS.get(report.status, set()):
        raise ValueError("READINESS_LIFECYCLE_TRANSITION_INVALID")
    required = "REVIEWER" if to_status == "UNDER_HUMAN_REVIEW" else (
        "APPROVER" if to_status in {"APPROVED_FOR_DEPLOYMENT", "REJECTED"} else "GOVERNANCE_OWNER")
    if acting_role != required or acting_role not in actor.roles:
        raise ValueError("READINESS_LIFECYCLE_ROLE_UNAUTHORIZED")
    if report.approval_history:
        if parse_utc(recorded_at) <= parse_utc(report.approval_history[-1].recorded_at):
            raise ValueError("READINESS_LIFECYCLE_TIMESTAMP_NOT_MONOTONIC")
        reviewer = report.approval_history[0].actor.subject_identity
        if to_status in {"APPROVED_FOR_DEPLOYMENT", "REJECTED"} and actor.subject_identity == reviewer:
            raise ValueError("READINESS_SELF_APPROVAL_PROHIBITED")
    previous = report.approval_history[-1].event_identity if report.approval_history else None
    event_values = dict(sequence=len(report.approval_history) + 1, from_status=report.status,
                        to_status=to_status, actor=actor, acting_role=acting_role, reason=reason,
                        recorded_at=recorded_at, previous_event_identity=previous)
    event = ReadinessLifecycleEvent(
        **event_values, event_identity=certification_identity("V28_READINESS_LIFECYCLE_EVENT", event_values))
    values = report.canonical_payload()
    values.update(status=to_status, approval_history=report.approval_history + (event,),
                  reasons=report.reasons + (("HUMAN_APPROVAL_RECORDED",) if to_status == "APPROVED_FOR_DEPLOYMENT" else ()))
    return ProductionReadinessReport(
        **values, report_identity=certification_identity("V28_PRODUCTION_READINESS_REPORT", values))
