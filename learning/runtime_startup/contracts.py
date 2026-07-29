"""Immutable, data-only PR280 Runtime Startup Authorization contracts."""
from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from learning.deployment.contracts import _revalidate, _text, _utc
from learning.promotion.identity import identity_for
from learning.executor_acknowledgement import (ExecutorAcknowledgementAuthorization,
    ExecutorAcknowledgementRegistry, ExecutorAcknowledgementRegistryEntry)

if TYPE_CHECKING:
    from .registry import RuntimeStartupRegistry

STARTUP_SCHEMA_VERSION = "PR280.RUNTIME_STARTUP_AUTHORIZATION.1.0"
STARTUP_AUTHORIZED = "STARTUP_AUTHORIZED"
STARTUP_REJECTED = "STARTUP_REJECTED"
STARTUP_GATES = (
    "acknowledgement_authorization_integrity", "acknowledgement_registry_integrity",
    "acknowledgement_registry_membership", "acknowledgement_effectiveness",
    "acknowledgement_validity_window", "acknowledgement_freshness", "executor_identity",
    "executor_version", "executor_instance_identity", "executor_session_identity",
    "runtime_instance_identity", "activation_generation", "artifact_identity",
    "runtime_contract_identity", "target_environment_identity", "startup_contract_integrity",
    "startup_policy_compliance", "revocation_status", "supersession_status",
    "registry_lineage", "startup_generation_replay_protection", "lifecycle_consistency")
SUCCESS_LIFECYCLE = (("REQUESTED","VALIDATED"),("VALIDATED","STARTUP_AUTHORIZED"),
    ("STARTUP_AUTHORIZED","REGISTERED"),("REGISTERED","STARTUP_PENDING"))
REJECTION_LIFECYCLE = (("REQUESTED","STARTUP_REJECTED"),)

def _id(kind,payload): return identity_for(kind,payload)

@dataclass(frozen=True)
class RuntimeStartupPolicy:
    version: str
    allowed_environment_classes: tuple[str,...]
    allowed_executor_identities: tuple[str,...]
    allowed_executor_versions: tuple[str,...]
    allowed_runtime_contracts: tuple[str,...]
    required_acknowledgement_authority_identity: str
    required_startup_contract_identity: str
    maximum_acknowledgement_age_seconds: int
    maximum_startup_authorization_lifetime_seconds: int
    future_timestamp_skew_tolerance_seconds: int
    allowed_activation_generations: tuple[int,...]
    revocation_behavior: str = "REJECT"
    supersession_behavior: str = "REJECT"
    replay_behavior: str = "REJECT"
    registry_conflict_behavior: str = "REJECT"
    policy_identity: str = ""
    def __post_init__(self):
        tuple_fields=("allowed_environment_classes","allowed_executor_identities",
            "allowed_executor_versions","allowed_runtime_contracts","allowed_activation_generations")
        for name in tuple_fields: object.__setattr__(self,name,tuple(getattr(self,name)))
        if (not all(_text(getattr(self,n)) for n in ("version","required_acknowledgement_authority_identity",
                "required_startup_contract_identity")) or
            any(not x for x in (self.allowed_environment_classes,self.allowed_executor_identities,
                self.allowed_executor_versions,self.allowed_runtime_contracts,self.allowed_activation_generations)) or
            any(not _text(x) for n in tuple_fields[:4] for x in getattr(self,n)) or
            any(type(x) is not int or x<1 for x in self.allowed_activation_generations) or
            type(self.maximum_acknowledgement_age_seconds) is not int or self.maximum_acknowledgement_age_seconds<1 or
            type(self.maximum_startup_authorization_lifetime_seconds) is not int or self.maximum_startup_authorization_lifetime_seconds<1 or
            type(self.future_timestamp_skew_tolerance_seconds) is not int or self.future_timestamp_skew_tolerance_seconds<0 or
            (self.revocation_behavior,self.supersession_behavior,self.replay_behavior,self.registry_conflict_behavior)!=("REJECT",)*4):
            raise ValueError("RUNTIME_STARTUP_POLICY_INVALID")
        expected=_id("RUNTIME_STARTUP_POLICY",{k:v for k,v in self.__dict__.items() if k!="policy_identity"})
        if self.policy_identity and self.policy_identity!=expected: raise ValueError("STARTUP_POLICY_IDENTITY_INVALID")
        object.__setattr__(self,"policy_identity",expected)

@dataclass(frozen=True)
class RuntimeStartupContract:
    runtime_instance_identity: str; executor_identity: str; executor_version: str
    executor_instance_identity: str; executor_session_identity: str; activation_generation: int
    runtime_contract_identity: str; target_environment_identity: str; target_environment_class: str
    artifact_identity: str; expected_startup_mode: str; expected_configuration_identity: str
    expected_process_identity: str|None; startup_policy_identity: str; contract_identity: str=""
    def __post_init__(self):
        excluded={"activation_generation","expected_process_identity","contract_identity"}
        if (not all(_text(getattr(self,n)) for n in self.__dataclass_fields__ if n not in excluded)
                or type(self.activation_generation) is not int or self.activation_generation<1
                or (self.expected_process_identity is not None and not _text(self.expected_process_identity))):
            raise ValueError("RUNTIME_STARTUP_CONTRACT_INVALID")
        expected=_id("RUNTIME_STARTUP_CONTRACT",{k:v for k,v in self.__dict__.items() if k!="contract_identity"})
        if self.contract_identity and self.contract_identity!=expected: raise ValueError("STARTUP_CONTRACT_IDENTITY_INVALID")
        object.__setattr__(self,"contract_identity",expected)

@dataclass(frozen=True)
class StartupGovernanceStatus:
    kind: str; subject_identity: str; effective_at: str; authority_identity: str; reason: str
    status_identity: str=""
    def __post_init__(self):
        if self.kind not in {"REVOCATION","SUPERSESSION","EMERGENCY_ROLLBACK"}: raise ValueError("STARTUP_STATUS_KIND_INVALID")
        _utc(self.effective_at)
        if not all(_text(getattr(self,n)) for n in ("subject_identity","authority_identity","reason")): raise ValueError("STARTUP_STATUS_INVALID")
        expected=_id("STARTUP_GOVERNANCE_STATUS",{k:v for k,v in self.__dict__.items() if k!="status_identity"})
        if self.status_identity and self.status_identity!=expected: raise ValueError("STARTUP_STATUS_IDENTITY_INVALID")
        object.__setattr__(self,"status_identity",expected)

@dataclass(frozen=True)
class RuntimeStartupGovernanceBundle:
    acknowledgement_authorization: ExecutorAcknowledgementAuthorization
    acknowledgement_registry: ExecutorAcknowledgementRegistry
    acknowledgement_registry_entry: ExecutorAcknowledgementRegistryEntry
    startup_policy: RuntimeStartupPolicy; startup_contract: RuntimeStartupContract
    startup_registry: "RuntimeStartupRegistry"
    expected_acknowledgement_registry_identity: str; expected_startup_registry_identity: str
    expected_predecessor_registry_identity: str|None; canonical_evaluation_timestamp: str
    acknowledgement_authority_identity: str
    governance_statuses: tuple[StartupGovernanceStatus,...]=()
    bundle_identity: str=""
    def __post_init__(self):
        from .registry import RuntimeStartupRegistry
        for value in (self.acknowledgement_authorization,self.acknowledgement_registry,
                self.acknowledgement_registry_entry,self.startup_policy,self.startup_contract,self.startup_registry): _revalidate(value)
        if type(self.startup_registry) is not RuntimeStartupRegistry: raise ValueError("STARTUP_REGISTRY_TYPE_INVALID")
        statuses=tuple(self.governance_statuses); object.__setattr__(self,"governance_statuses",statuses)
        for value in statuses: _revalidate(value)
        _utc(self.canonical_evaluation_timestamp)
        if not all(_text(getattr(self,n)) for n in ("expected_acknowledgement_registry_identity",
                "expected_startup_registry_identity","acknowledgement_authority_identity")): raise ValueError("STARTUP_BUNDLE_INVALID")
        payload={"acknowledgement_authorization":self.acknowledgement_authorization.authorization_identity,
            "acknowledgement_registry":self.acknowledgement_registry.registry_identity,
            "acknowledgement_registry_entry":self.acknowledgement_registry_entry.entry_identity,
            "startup_policy":self.startup_policy.policy_identity,"startup_contract":self.startup_contract.contract_identity,
            "startup_registry":self.startup_registry.registry_identity,"expected_acknowledgement_registry":self.expected_acknowledgement_registry_identity,
            "expected_startup_registry":self.expected_startup_registry_identity,"expected_predecessor_registry":self.expected_predecessor_registry_identity,
            "evaluated_at":self.canonical_evaluation_timestamp,"acknowledgement_authority":self.acknowledgement_authority_identity,
            "statuses":tuple(x.status_identity for x in statuses)}
        expected=_id("RUNTIME_STARTUP_GOVERNANCE_BUNDLE",payload)
        if self.bundle_identity and self.bundle_identity!=expected: raise ValueError("STARTUP_BUNDLE_IDENTITY_INVALID")
        object.__setattr__(self,"bundle_identity",expected)

@dataclass(frozen=True)
class RuntimeStartupGateResult:
    gate: str; passed: bool; reason: str
    def __post_init__(self):
        if self.gate not in STARTUP_GATES or type(self.passed) is not bool or not _text(self.reason): raise ValueError("STARTUP_GATE_RESULT_INVALID")

@dataclass(frozen=True)
class RuntimeStartupEvidence:
    bundle_identity: str; decision: str; gate_results: tuple[RuntimeStartupGateResult,...]
    evaluated_at: str; evidence_identity: str=""
    def __post_init__(self):
        results=tuple(self.gate_results); object.__setattr__(self,"gate_results",results); _utc(self.evaluated_at)
        if (self.decision not in {STARTUP_AUTHORIZED,STARTUP_REJECTED} or
            tuple(x.gate for x in results)!=STARTUP_GATES or (self.decision==STARTUP_AUTHORIZED)!=all(x.passed for x in results)):
            raise ValueError("RUNTIME_STARTUP_EVIDENCE_INVALID")
        expected=_id("RUNTIME_STARTUP_EVIDENCE",{"bundle":self.bundle_identity,"decision":self.decision,
            "gates":tuple((x.gate,x.passed,x.reason) for x in results),"evaluated_at":self.evaluated_at})
        if self.evidence_identity and self.evidence_identity!=expected: raise ValueError("STARTUP_EVIDENCE_IDENTITY_INVALID")
        object.__setattr__(self,"evidence_identity",expected)

RuntimeStartupRejectionEvidence = RuntimeStartupEvidence

@dataclass(frozen=True)
class RuntimeStartupAuthorization:
    startup_result_identity: str; startup_evidence_identity: str; startup_policy_identity: str
    startup_contract_identity: str; executor_acknowledgement_authorization_identity: str
    acknowledgement_registry_entry_identity: str; runtime_instance_identity: str
    executor_identity: str; executor_version: str; executor_instance_identity: str
    executor_session_identity: str; activation_generation: int; artifact_identity: str
    runtime_contract_identity: str; target_environment_identity: str; issued_at: str
    valid_from: str; expires_at: str; authorization_identity: str=""; single_use: bool=True
    revoked: bool=False; superseded: bool=False; runtime_startup_authorized: bool=True
    runtime_started: bool=False; executor_invoked: bool=False; broker_access_authorized: bool=False
    broker_connected: bool=False; order_submission_authorized: bool=False; trade_execution_authorized: bool=False
    def __post_init__(self):
        for value in (self.issued_at,self.valid_from,self.expires_at): _utc(value)
        excluded={"activation_generation","authorization_identity","single_use","revoked","superseded",
            "runtime_startup_authorized","runtime_started","executor_invoked","broker_access_authorized",
            "broker_connected","order_submission_authorized","trade_execution_authorized"}
        flags=(self.single_use,self.revoked,self.superseded,self.runtime_startup_authorized,self.runtime_started,
            self.executor_invoked,self.broker_access_authorized,self.broker_connected,self.order_submission_authorized,self.trade_execution_authorized)
        if (not all(_text(getattr(self,n)) for n in self.__dataclass_fields__ if n not in excluded)
                or type(self.activation_generation) is not int or flags!=(True,False,False,True,False,False,False,False,False,False)
                or not (_utc(self.issued_at)==_utc(self.valid_from)<_utc(self.expires_at))): raise ValueError("RUNTIME_STARTUP_AUTHORIZATION_INVALID")
        expected=_id("RUNTIME_STARTUP_AUTHORIZATION",{k:v for k,v in self.__dict__.items() if k!="authorization_identity"})
        if self.authorization_identity and self.authorization_identity!=expected: raise ValueError("STARTUP_AUTHORIZATION_IDENTITY_INVALID")
        object.__setattr__(self,"authorization_identity",expected)

@dataclass(frozen=True)
class RuntimeStartupLifecycleRecord:
    startup_result_identity: str; from_state: str; to_state: str; occurred_at: str
    sequence: int; previous_record_identity: str|None; record_identity: str=""
    def __post_init__(self):
        _utc(self.occurred_at)
        if ((self.from_state,self.to_state) not in SUCCESS_LIFECYCLE+REJECTION_LIFECYCLE or self.sequence<1 or
            (self.sequence==1)!=(self.previous_record_identity is None)): raise ValueError("STARTUP_LIFECYCLE_INVALID")
        expected=_id("RUNTIME_STARTUP_LIFECYCLE_RECORD",{k:v for k,v in self.__dict__.items() if k!="record_identity"})
        if self.record_identity and self.record_identity!=expected: raise ValueError("STARTUP_LIFECYCLE_IDENTITY_INVALID")
        object.__setattr__(self,"record_identity",expected)

@dataclass(frozen=True)
class RuntimeStartupRegistryEntry:
    composite_key: str; decision: str; evidence: RuntimeStartupEvidence
    authorization: RuntimeStartupAuthorization|None; lifecycle: tuple[RuntimeStartupLifecycleRecord,...]
    sequence: int; previous_entry_identity: str|None; entry_identity: str=""
    def __post_init__(self):
        _revalidate(self.evidence)
        if self.authorization is not None: _revalidate(self.authorization)
        lifecycle=tuple(self.lifecycle); object.__setattr__(self,"lifecycle",lifecycle)
        expected_flow=SUCCESS_LIFECYCLE if self.decision==STARTUP_AUTHORIZED else REJECTION_LIFECYCLE
        if (not _text(self.composite_key) or self.decision!=self.evidence.decision or
            (self.authorization is not None)!=(self.decision==STARTUP_AUTHORIZED) or
            tuple((x.from_state,x.to_state) for x in lifecycle)!=expected_flow or
            any(x.previous_record_identity!=(None if i==0 else lifecycle[i-1].record_identity) for i,x in enumerate(lifecycle)) or
            self.sequence<1 or (self.sequence==1)!=(self.previous_entry_identity is None)): raise ValueError("STARTUP_REGISTRY_ENTRY_INVALID")
        expected=_id("RUNTIME_STARTUP_REGISTRY_ENTRY",{"key":self.composite_key,"decision":self.decision,
            "evidence":self.evidence.evidence_identity,"authorization":None if self.authorization is None else self.authorization.authorization_identity,
            "lifecycle":tuple(x.record_identity for x in lifecycle),"sequence":self.sequence,"previous":self.previous_entry_identity})
        if self.entry_identity and self.entry_identity!=expected: raise ValueError("STARTUP_REGISTRY_ENTRY_IDENTITY_INVALID")
        object.__setattr__(self,"entry_identity",expected)

@dataclass(frozen=True)
class RuntimeStartupResult:
    decision: str; result_identity: str; evidence: RuntimeStartupEvidence
    authorization: RuntimeStartupAuthorization|None; registry_entry: RuntimeStartupRegistryEntry

