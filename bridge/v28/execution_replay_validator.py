"""Complete deterministic PR264 lineage, field, authority, and time validation."""
from __future__ import annotations
from dataclasses import dataclass
from .execution_plan import ExecutionPlan, identity, parse_utc
from .executor_contract import ExecutorContract
from .publisher_contract import BrokerSnapshot,ExecutionEnvironmentContract,HumanApprovalRecord,PublishedExecutionPlan,RuntimeHealthSnapshot,canonical_json


@dataclass(frozen=True)
class ReplayValidation:
    valid: bool; reasons: tuple[str,...]


def validate_execution_replay(plan: ExecutionPlan, contract: ExecutorContract | None,
        health: RuntimeHealthSnapshot, broker: BrokerSnapshot, publication: PublishedExecutionPlan | None=None,
        environment: ExecutionEnvironmentContract | None=None, approval: HumanApprovalRecord | None=None,
        *, evaluation_time: str, require_delivery_authority: bool=False, maximum_clock_skew_seconds: float=1.0) -> ReplayValidation:
    reasons=[]
    def reject(condition,reason):
        if condition: reasons.append(reason)
    now=parse_utc(evaluation_time); skew=maximum_clock_skew_seconds
    reject(plan.replay_identity!=identity("V28_EXECUTION_PLAN_REPLAY",plan.canonical_payload()),"EXECUTION_PLAN_INVALID")
    reject(health.replay_identity!=identity("V28_RUNTIME_HEALTH_SNAPSHOT_REPLAY",health.canonical_payload()),"RUNTIME_HEALTH_REPLAY_INVALID")
    reject(broker.replay_identity!=identity("V28_BROKER_SNAPSHOT_REPLAY",broker.canonical_payload()),"BROKER_SNAPSHOT_REPLAY_INVALID")
    reject(not health.healthy,"RUNTIME_UNHEALTHY")
    reject(health.runtime_sequence_id!=plan.runtime_sequence_id or broker.runtime_sequence_id!=plan.runtime_sequence_id,"RUNTIME_SEQUENCE_MISMATCH")
    reject(broker.symbol!=plan.symbol,"BROKER_SYMBOL_MISMATCH")
    reject(not broker.trading_enabled or broker.session_state!="OPEN" or broker.symbol_trade_mode!="ENABLED" or broker.connection_state!="CONNECTED","BROKER_SNAPSHOT_NOT_TRADABLE")
    if contract is None: reject(plan.execution_ready,"EXECUTOR_CONTRACT_MISSING")
    else:
        reject(contract.replay_identity!=identity("V28_EXECUTOR_CONTRACT_REPLAY",contract.canonical_payload()),"EXECUTOR_CONTRACT_INVALID")
        comparisons=(("execution_plan_replay_identity",plan.replay_identity),("decision_replay_identity",plan.decision_replay_identity),
            ("runtime_sequence_id",plan.runtime_sequence_id),("symbol",plan.symbol),("direction",plan.direction),
            ("approved_volume",plan.approved_volume),("executable_entry_price",plan.executable_entry_price),
            ("protective_stop",plan.protective_stop),("target",plan.target),("tick_size",plan.tick_size),
            ("volume_step",plan.volume_step),("execution_model_id",plan.execution_model_id))
        for field,expected in comparisons: reject(getattr(contract,field)!=expected,f"EXECUTOR_PLAN_{field.upper()}_MISMATCH")
        reject(contract.policy_reference not in plan.policy_references,"EXECUTOR_PLAN_POLICY_REFERENCE_MISMATCH")
    if publication is None: reject(require_delivery_authority,"PUBLICATION_REQUIRED")
    else:
        reject(publication.publication_replay_identity!=identity("V28_EXECUTION_PUBLICATION_REPLAY",publication.canonical_payload()),"PUBLICATION_REPLAY_INVALID")
        reject(publication.canonical_plan_json!=canonical_json(plan.canonical_payload()),"PUBLISHED_PAYLOAD_INTEGRITY_INVALID")
        reject(publication.execution_plan_replay_identity!=plan.replay_identity,"PUBLISHED_PLAN_REPLAY_MISMATCH")
        reject(publication.decision_replay_identity!=plan.decision_replay_identity,"PUBLISHED_DECISION_REPLAY_MISMATCH")
        reject(publication.runtime_sequence_id!=plan.runtime_sequence_id,"PUBLISHED_RUNTIME_SEQUENCE_MISMATCH")
    if environment is not None:
        reject(environment.replay_identity!=identity("V28_EXECUTION_ENVIRONMENT_REPLAY",environment.canonical_payload()),"ENVIRONMENT_REPLAY_INVALID")
        reject(broker.account_environment!=environment.environment or broker.account_identifier!=environment.account_identifier or broker.broker_server!=environment.broker_server or broker.terminal_instance_identity!=environment.terminal_instance_identity,"BROKER_ENVIRONMENT_MISMATCH")
    if require_delivery_authority:
        reject(environment is None,"DEMO_ENVIRONMENT_REQUIRED"); reject(approval is None,"HUMAN_APPROVAL_REQUIRED")
        if environment is not None and approval is not None and contract is not None:
            reject(approval.replay_identity!=identity("V28_HUMAN_APPROVAL_REPLAY",approval.canonical_payload()),"HUMAN_APPROVAL_REPLAY_INVALID")
            reject(approval.execution_plan_replay_identity!=plan.replay_identity,"APPROVAL_PLAN_MISMATCH")
            reject(approval.executor_contract_replay_identity!=contract.replay_identity,"APPROVAL_CONTRACT_MISMATCH")
            reject(approval.approved_environment_identity!=environment.replay_identity,"APPROVAL_ENVIRONMENT_MISMATCH")
    time_sources=[("PLAN",parse_utc(plan.evaluation_time),None,None),
        ("HEALTH",parse_utc(health.observed_at),parse_utc(health.expires_at),health.maximum_age_seconds),
        ("BROKER",parse_utc(broker.observed_at),parse_utc(broker.expires_at),broker.maximum_age_seconds)]
    if publication is not None: time_sources.append(("PUBLICATION",parse_utc(publication.publication_timestamp),None,None))
    if environment is not None: time_sources.append(("ENVIRONMENT",parse_utc(environment.verification_timestamp),parse_utc(environment.expires_at),None))
    if approval is not None: time_sources.append(("APPROVAL",parse_utc(approval.approval_timestamp),parse_utc(approval.expires_at),None))
    for name,observed,expires,max_age in time_sources:
        age=(now-observed).total_seconds(); reject(age < -skew,f"{name}_TIMESTAMP_FUTURE")
        if max_age is not None: reject(age>max_age,f"{name}_STALE")
        if expires is not None: reject(now>expires,f"{name}_EXPIRED")
    if publication is not None: reject(parse_utc(publication.publication_timestamp)<parse_utc(plan.evaluation_time),"PUBLICATION_BEFORE_PLAN")
    if publication is not None and approval is not None: reject(parse_utc(approval.approval_timestamp)<parse_utc(publication.publication_timestamp),"APPROVAL_BEFORE_PUBLICATION")
    if environment is not None and approval is not None: reject(parse_utc(approval.approval_timestamp)<parse_utc(environment.verification_timestamp),"APPROVAL_BEFORE_ENVIRONMENT_VERIFICATION")
    reject(parse_utc(health.evaluation_time)!=now or parse_utc(broker.evaluation_time)!=now,"EVALUATION_WINDOW_MISMATCH")
    return ReplayValidation(not reasons,tuple(dict.fromkeys(reasons)) or ("REPLAY_VALID",))
