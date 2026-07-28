"""Broker-free BUY, SELL, and HOLD end-to-end shadow validation."""
from dataclasses import dataclass
from typing import Iterable
from .execution_plan import ExecutionPlan, identity
from .pipeline_validator import PR265_POLICY, certification_identity
from .publisher_contract import PublishedExecutionPlan
from .shadow_executor import ShadowExecutionRecord, ShadowExecutor


@dataclass(frozen=True)
class ShadowCase:
    expected_action: str
    plan: ExecutionPlan
    publication: PublishedExecutionPlan | None


@dataclass(frozen=True)
class ShadowValidationReport:
    status: str
    actions: tuple[str, ...]
    records: tuple[ShadowExecutionRecord, ...]
    reasons: tuple[str, ...]
    broker_submissions: int
    policy_reference: str
    replay_identity: str
    def canonical_payload(self): return {k: getattr(self, k) for k in self.__dataclass_fields__ if k != "replay_identity"}
    def __post_init__(self):
        if self.status not in {"PASS", "FAIL"} or self.broker_submissions != 0: raise ValueError("SHADOW_REPORT_AUTHORITY_INVALID")
        if self.replay_identity != certification_identity("V28_SHADOW_VALIDATION", self.canonical_payload()): raise ValueError("SHADOW_REPORT_REPLAY_INVALID")


def run_shadow_validation(cases: Iterable[ShadowCase], *, recorded_at: str) -> ShadowValidationReport:
    executor = ShadowExecutor(); records = []; reasons = []
    for case in tuple(cases):
        if case.expected_action not in {"BUY", "SELL", "HOLD"}:
            reasons.append("EXPECTED_ACTION_INVALID"); continue
        first = executor.execute(case.plan, case.publication, recorded_at=recorded_at)
        second = executor.execute(case.plan, case.publication, recorded_at=recorded_at)
        records.append(first)
        if first.action != case.expected_action: reasons.append(f"EXPECTED_{case.expected_action}_NOT_OBSERVED")
        if first != second or first.replay_identity != second.replay_identity: reasons.append(f"{case.expected_action}_NOT_REPRODUCIBLE")
        if first.ordersend_permitted: reasons.append("SHADOW_BROKER_AUTHORITY_DETECTED")
        if first.replay_identity != identity("V28_SHADOW_EXECUTION_REPLAY", first.canonical_payload()): reasons.append("SHADOW_RECORD_REPLAY_INVALID")
    actions = tuple(record.action for record in records)
    if set(actions) != {"BUY", "SELL", "HOLD"}: reasons.append("BUY_SELL_HOLD_COVERAGE_INCOMPLETE")
    values = dict(status="FAIL" if reasons else "PASS", actions=actions, records=tuple(records),
                  reasons=tuple(dict.fromkeys(reasons)) or ("SHADOW_REPRODUCIBLE_NO_BROKER_SUBMISSION",),
                  broker_submissions=0, policy_reference=PR265_POLICY)
    return ShadowValidationReport(**values, replay_identity=certification_identity("V28_SHADOW_VALIDATION", values))
