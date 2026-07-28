"""Read-only, fail-closed certification of the governed V28 pipeline."""
from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
import json
from typing import Any, Mapping

from .decision_contract import DecisionContext, decision_replay_identity
from .execution_plan import ExecutionPlan, identity
from .execution_replay_validator import validate_execution_replay
from .executor_contract import ExecutorContract
from .publisher_contract import BrokerSnapshot, PublishedExecutionPlan, RuntimeHealthSnapshot

PR265_POLICY = "V28_END_TO_END_VALIDATION_POLICY.1.0"


def _plain(value: Any) -> Any:
    if hasattr(value, "__dataclass_fields__"):
        return {name: _plain(getattr(value, name)) for name in value.__dataclass_fields__}
    if isinstance(value, Mapping):
        return {str(k): _plain(v) for k, v in sorted(value.items(), key=lambda item: str(item[0]))}
    if isinstance(value, (tuple, list)): return [_plain(v) for v in value]
    return value


def certification_identity(domain: str, payload: Any) -> str:
    encoded = json.dumps(_plain(payload), sort_keys=True, separators=(",", ":"), allow_nan=False)
    return sha256((domain + "|" + encoded).encode()).hexdigest()


@dataclass(frozen=True)
class BoundaryResult:
    boundary: str
    status: str
    checks: tuple[str, ...]
    failures: tuple[str, ...]
    policy_reference: str = PR265_POLICY

    def __post_init__(self) -> None:
        if self.status not in {"PASS", "WARNING", "FAIL"} or not self.boundary or not self.checks:
            raise ValueError("BOUNDARY_RESULT_INVALID")
        if (self.status == "FAIL") != bool(self.failures):
            raise ValueError("BOUNDARY_RESULT_STATUS_INVALID")
        object.__setattr__(self, "checks", tuple(self.checks))
        object.__setattr__(self, "failures", tuple(self.failures))


@dataclass(frozen=True)
class PipelineValidationReport:
    status: str
    runtime_sequence_id: int
    boundaries: tuple[BoundaryResult, ...]
    evaluated_at: str
    policy_reference: str
    production_authorized: bool
    replay_identity: str

    def canonical_payload(self) -> dict[str, Any]:
        return {name: getattr(self, name) for name in self.__dataclass_fields__ if name != "replay_identity"}

    def __post_init__(self) -> None:
        if self.status not in {"PASS", "FAIL"} or self.production_authorized is not False:
            raise ValueError("PIPELINE_CERTIFICATION_AUTHORITY_INVALID")
        if self.status == "PASS" and any(item.status != "PASS" for item in self.boundaries):
            raise ValueError("PIPELINE_CERTIFICATION_STATUS_INVALID")
        if self.replay_identity != certification_identity("V28_PIPELINE_VALIDATION", self.canonical_payload()):
            raise ValueError("PIPELINE_CERTIFICATION_REPLAY_INVALID")


def _result(name: str, checks: tuple[str, ...], failures: list[str]) -> BoundaryResult:
    return BoundaryResult(name, "FAIL" if failures else "PASS", checks, tuple(dict.fromkeys(failures)))


def validate_pipeline(decision: DecisionContext, plan: ExecutionPlan, contract: ExecutorContract,
                      health: RuntimeHealthSnapshot, broker: BrokerSnapshot,
                      publication: PublishedExecutionPlan, *, evaluation_time: str) -> PipelineValidationReport:
    """Verify every PR260--PR264 boundary without invoking or publishing anything."""
    boundaries: list[BoundaryResult] = []
    failures: list[str] = []
    if type(decision) is not DecisionContext:
        failures.append("DECISION_CONTEXT_REQUIRED")
    else:
        if decision.replay_identity != decision_replay_identity(decision.canonical_payload()): failures.append("DECISION_REPLAY_INVALID")
        if decision.decision not in {"BUY", "SELL", "HOLD"}: failures.append("DECISION_ONTOLOGY_INVALID")
    boundaries.append(_result("MARKET_TO_DECISION", ("IMMUTABLE_CONTEXTS", "POLICY_LINEAGE", "DECISION_REPLAY"), failures))

    failures = []
    if plan.replay_identity != identity("V28_EXECUTION_PLAN_REPLAY", plan.canonical_payload()): failures.append("EXECUTION_PLAN_REPLAY_INVALID")
    if plan.decision_replay_identity != decision.replay_identity: failures.append("DECISION_PLAN_LINEAGE_MISMATCH")
    if plan.symbol != decision.candidate.symbol: failures.append("DECISION_PLAN_SYMBOL_MISMATCH")
    if decision.decision in {"BUY", "SELL"} and plan.direction != decision.direction: failures.append("DECISION_PLAN_DIRECTION_MISMATCH")
    boundaries.append(_result("DECISION_TO_RISK", ("EXECUTION_PLAN_INTEGRITY", "DECISION_LINEAGE", "DATA_CONSISTENCY"), failures))

    replay = validate_execution_replay(plan, contract, health, broker, publication,
                                       evaluation_time=evaluation_time)
    boundaries.append(_result("RISK_TO_EXECUTION", ("EXECUTOR_CONTRACT_INTEGRITY", "RUNTIME_FRESHNESS", "BOUNDARY_FRESHNESS", "BROKER_CONSISTENCY"), [] if replay.valid else list(replay.reasons)))

    failures = []
    if publication.execution_plan_replay_identity != plan.replay_identity: failures.append("PUBLICATION_PLAN_LINEAGE_MISMATCH")
    if publication.decision_replay_identity != decision.replay_identity: failures.append("PUBLICATION_DECISION_LINEAGE_MISMATCH")
    if publication.runtime_sequence_id != plan.runtime_sequence_id: failures.append("PUBLICATION_SEQUENCE_MISMATCH")
    boundaries.append(_result("EXECUTION_TO_PUBLICATION", ("PUBLICATION_INTEGRITY", "PAYLOAD_IDENTITY", "SEQUENCE_INTEGRITY"), failures))
    status = "PASS" if all(item.status == "PASS" for item in boundaries) else "FAIL"
    values = dict(status=status, runtime_sequence_id=plan.runtime_sequence_id, boundaries=tuple(boundaries),
                  evaluated_at=evaluation_time, policy_reference=PR265_POLICY, production_authorized=False)
    return PipelineValidationReport(**values, replay_identity=certification_identity("V28_PIPELINE_VALIDATION", values))
