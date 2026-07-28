"""Deterministic, fail-closed validation of PR264 lineage and integrity."""
from __future__ import annotations

from dataclasses import dataclass

from .execution_plan import ExecutionPlan, identity, parse_utc
from .executor_contract import ExecutorContract
from .publisher_contract import BrokerSnapshot, PublishedExecutionPlan, RuntimeHealthSnapshot


@dataclass(frozen=True)
class ReplayValidation:
    valid: bool
    reasons: tuple[str, ...]


def validate_execution_replay(plan: ExecutionPlan, contract: ExecutorContract | None,
                              health: RuntimeHealthSnapshot, broker: BrokerSnapshot,
                              publication: PublishedExecutionPlan | None = None,
                              *, maximum_boundary_age_seconds: float = 5.0) -> ReplayValidation:
    reasons: list[str] = []
    if plan.replay_identity != identity("V28_EXECUTION_PLAN_REPLAY", plan.canonical_payload()):
        reasons.append("EXECUTION_PLAN_INVALID")
    if not health.healthy: reasons.append("RUNTIME_UNHEALTHY")
    if health.boundary_age_seconds > maximum_boundary_age_seconds: reasons.append("BOUNDARY_STALE")
    if health.sequence_id != plan.runtime_sequence_id or broker.sequence_id != plan.runtime_sequence_id:
        reasons.append("RUNTIME_SEQUENCE_MISMATCH")
    if broker.symbol != plan.symbol or not broker.available: reasons.append("BROKER_SNAPSHOT_INVALID")
    try:
        if parse_utc(broker.observed_at) > parse_utc(health.observed_at): reasons.append("BROKER_SNAPSHOT_FUTURE")
    except ValueError: reasons.append("BOUNDARY_TIMESTAMP_INVALID")
    if plan.execution_ready:
        if contract is None: reasons.append("EXECUTOR_CONTRACT_MISSING")
        else:
            if contract.replay_identity != identity("V28_EXECUTOR_CONTRACT_REPLAY", contract.canonical_payload()): reasons.append("EXECUTOR_CONTRACT_INVALID")
            if contract.execution_plan_replay_identity != plan.replay_identity: reasons.append("EXECUTION_PLAN_LINEAGE_MISMATCH")
            if contract.decision_replay_identity != plan.decision_replay_identity: reasons.append("DECISION_REPLAY_MISMATCH")
            if contract.runtime_sequence_id != plan.runtime_sequence_id: reasons.append("EXECUTOR_RUNTIME_SEQUENCE_MISMATCH")
    if publication is not None:
        if publication.execution_plan_replay_identity != plan.replay_identity or dict(publication.payload) != plan.canonical_payload(): reasons.append("PUBLISHED_PAYLOAD_INTEGRITY_INVALID")
        if publication.decision_replay_identity != plan.decision_replay_identity: reasons.append("PUBLISHED_DECISION_REPLAY_MISMATCH")
        if publication.runtime_sequence_id != plan.runtime_sequence_id: reasons.append("PUBLISHED_RUNTIME_SEQUENCE_MISMATCH")
        if publication.execution_replay_identity != identity("V28_EXECUTION_PUBLICATION_REPLAY", publication.canonical_payload()): reasons.append("PUBLISHED_PAYLOAD_INTEGRITY_INVALID")
    return ReplayValidation(not reasons, tuple(dict.fromkeys(reasons)) or ("REPLAY_VALID",))

