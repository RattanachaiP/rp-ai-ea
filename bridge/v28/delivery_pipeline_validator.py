"""Read-only validation of the final adapter-to-delivery-receipt boundary."""
from dataclasses import dataclass
from .execution_bridge import DeliveryReceipt
from .execution_plan import ExecutionPlan, identity
from .executor_contract import ExecutorContract
from .pipeline_validator import PR265_POLICY, certification_identity
from .publisher_contract import PublishedExecutionPlan


@dataclass(frozen=True)
class DeliveryValidationReport:
    status: str; checks: tuple[str, ...]; failures: tuple[str, ...]
    production_authorized: bool; policy_reference: str; replay_identity: str
    def canonical_payload(self): return {k: getattr(self, k) for k in self.__dataclass_fields__ if k != "replay_identity"}
    def __post_init__(self):
        if self.status not in {"PASS", "FAIL"} or self.production_authorized is not False: raise ValueError("DELIVERY_VALIDATION_INVALID")
        if self.replay_identity != certification_identity("V28_DELIVERY_VALIDATION", self.canonical_payload()): raise ValueError("DELIVERY_VALIDATION_REPLAY_INVALID")


def validate_delivery(plan: ExecutionPlan, contract: ExecutorContract,
                      publication: PublishedExecutionPlan, receipt: DeliveryReceipt) -> DeliveryValidationReport:
    failures = []
    if receipt.replay_identity != identity("V28_DELIVERY_RECEIPT_REPLAY", receipt.canonical_payload()): failures.append("DELIVERY_RECEIPT_REPLAY_INVALID")
    if receipt.status != "DELIVERED": failures.append("DELIVERY_NOT_COMPLETED")
    if receipt.execution_plan_replay_identity != plan.replay_identity: failures.append("DELIVERY_PLAN_LINEAGE_MISMATCH")
    if receipt.executor_contract_replay_identity != contract.replay_identity: failures.append("DELIVERY_CONTRACT_LINEAGE_MISMATCH")
    if receipt.publication_replay_identity != publication.publication_replay_identity: failures.append("DELIVERY_PUBLICATION_LINEAGE_MISMATCH")
    if receipt.runtime_sequence_id != plan.runtime_sequence_id: failures.append("DELIVERY_SEQUENCE_MISMATCH")
    values = dict(status="FAIL" if failures else "PASS", checks=("DELIVERY_INTEGRITY", "EXECUTOR_ADAPTER_LINEAGE", "PUBLICATION_LINEAGE", "RUNTIME_SEQUENCE"), failures=tuple(failures), production_authorized=False, policy_reference=PR265_POLICY)
    return DeliveryValidationReport(**values, replay_identity=certification_identity("V28_DELIVERY_VALIDATION", values))
