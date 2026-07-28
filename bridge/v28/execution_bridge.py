"""Governed demo delivery boundary; V27 Executor remains the only OrderSend owner."""
from __future__ import annotations
from dataclasses import dataclass
from bridge.decision_writer import WriterReadResult
from runtime.executor import Executor
from .execution_plan import identity
from .execution_replay_validator import validate_execution_replay
from .executor_adapter import V27ExecutorCompatibilityContract,adapt_executor_contract
from .publisher_contract import ExecutionEnvironmentContract


class DemoExecutor:
    """Nominal DEMO-only capability that constructs, but never replaces, V27 Executor."""
    def __init__(self, environment: ExecutionEnvironmentContract, broker, **executor_options):
        if type(environment) is not ExecutionEnvironmentContract or environment.environment!="DEMO": raise ValueError("VERIFIED_DEMO_ENVIRONMENT_REQUIRED")
        self.environment=environment; self.instance_identity=environment.executor_instance_identity
        self.__executor=Executor(broker,**executor_options)
    def deliver(self,snapshot: WriterReadResult): return self.__executor.execute(snapshot)


@dataclass(frozen=True)
class DeliveryReceipt:
    status: str; reason: str; execution_plan_replay_identity: str
    executor_contract_replay_identity: str; publication_replay_identity: str
    environment_identity: str; executor_instance_identity: str; runtime_sequence_id: int
    delivered_at: str; downstream_result_identity: str; replay_identity: str
    def canonical_payload(self): return {k:getattr(self,k) for k in self.__dataclass_fields__ if k!="replay_identity"}
    def __post_init__(self):
        if self.status not in {"DELIVERED","REJECTED"}: raise ValueError("DELIVERY_STATUS_INVALID")
        if self.replay_identity!=identity("V28_DELIVERY_RECEIPT_REPLAY",self.canonical_payload()): raise ValueError("DELIVERY_RECEIPT_REPLAY_INVALID")


class ExecutionBridge:
    def __init__(self,executor: DemoExecutor):
        if type(executor) is not DemoExecutor: raise TypeError("DEMO_EXECUTOR_CAPABILITY_REQUIRED")
        self._executor=executor
    def deliver(self,plan,contract,compatibility: V27ExecutorCompatibilityContract,health,broker,publication,environment,approval,*,delivered_at):
        validation=validate_execution_replay(plan,contract,health,broker,publication,environment,approval,
            evaluation_time=delivered_at,require_delivery_authority=True)
        reason=validation.reasons[0] if not validation.valid else None
        if reason is None and (compatibility.execution_plan_replay_identity!=plan.replay_identity or compatibility.executor_contract_replay_identity!=contract.replay_identity): reason="COMPATIBILITY_LINEAGE_MISMATCH"
        adapted=adapt_executor_contract(compatibility) if reason is None else None
        if reason is None and (adapted is None or not adapted.valid or adapted.snapshot is None): reason=adapted.reason if adapted else "ADAPTER_INVALID"
        if reason is None and (environment.replay_identity!=self._executor.environment.replay_identity or environment.executor_instance_identity!=self._executor.instance_identity): reason="EXECUTOR_ENVIRONMENT_MISMATCH"
        downstream=None
        if reason is None: downstream=self._executor.deliver(adapted.snapshot)
        values=dict(status="DELIVERED" if reason is None else "REJECTED",reason=reason or "DELIVERED_TO_V27_EXECUTOR",
            execution_plan_replay_identity=plan.replay_identity,executor_contract_replay_identity=contract.replay_identity,
            publication_replay_identity=publication.publication_replay_identity if publication else "NONE",
            environment_identity=environment.replay_identity if environment else "NONE",
            executor_instance_identity=self._executor.instance_identity,runtime_sequence_id=plan.runtime_sequence_id,
            delivered_at=delivered_at,downstream_result_identity=identity("V27_EXECUTOR_RESULT",downstream) if downstream else "NONE")
        return DeliveryReceipt(**values,replay_identity=identity("V28_DELIVERY_RECEIPT_REPLAY",values))
