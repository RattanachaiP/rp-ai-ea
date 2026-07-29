"""Immutable PR279 executor-origin acknowledgement contracts."""
from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from learning.deployment.contracts import _revalidate, _text, _utc
from learning.promotion.identity import identity_for
from learning.runtime_admission import (AdmissionRegistryEntry, ExecutorAdmissionAuthorization,
    RuntimeAdmissionRegistry)

if TYPE_CHECKING:
    from .registry import ExecutorAcknowledgementRegistry

ACKNOWLEDGEMENT_SCHEMA_VERSION = "PR279.EXECUTOR_ACKNOWLEDGEMENT.2.0"
ACKNOWLEDGEMENT_CHECKS = (
    "attestation_integrity", "attestation_authenticity", "authorization_validity_window",
    "attestation_freshness", "executor_identity", "executor_version", "executor_instance_identity",
    "executor_session_identity", "runtime_instance_identity", "activation_generation",
    "artifact_lineage", "runtime_contract_lineage", "target_environment_lineage",
    "executor_policy_identity", "acknowledgement_authority_identity",
    "admission_registry_membership", "admission_effectiveness", "attestation_replay_protection",
    "nonce_session_replay_protection", "lifecycle_consistency")
LIFECYCLE = (("AUTHORIZED", "ACKNOWLEDGED"), ("ACKNOWLEDGED", "RECORDED"),
             ("RECORDED", "ACKNOWLEDGEMENT_COMPLETE"))


def _id(kind, payload): return identity_for(kind, payload)


@dataclass(frozen=True)
class ExecutorAcceptanceAttestation:
    """A signed acceptance statement created by the designated V27 executor."""
    admission_authorization_identity: str
    executor_admission_authorization_identity: str
    executor_identity: str
    executor_version: str
    executor_instance_identity: str
    executor_session_identity: str
    runtime_instance_identity: str
    activation_generation: int
    artifact_identity: str
    runtime_contract_identity: str
    target_environment_identity: str
    executor_policy_identity: str
    acknowledgement_authority_identity: str
    accepted_at: str
    nonce: str
    signature: str
    attestation_identity: str = ""
    def __post_init__(self):
        _utc(self.accepted_at)
        excluded={"activation_generation","attestation_identity"}
        if (not all(_text(getattr(self,x)) for x in self.__dataclass_fields__ if x not in excluded)
                or type(self.activation_generation) is not int or self.activation_generation < 1):
            raise ValueError("EXECUTOR_ACCEPTANCE_ATTESTATION_INVALID")
        expected=_id("EXECUTOR_ACCEPTANCE_ATTESTATION",{k:v for k,v in self.__dict__.items() if k!="attestation_identity"})
        if self.attestation_identity and self.attestation_identity!=expected:
            raise ValueError("EXECUTOR_ACCEPTANCE_ATTESTATION_IDENTITY_INVALID")
        object.__setattr__(self,"attestation_identity",expected)

    def signing_payload(self):
        return {k:v for k,v in self.__dict__.items() if k not in {"signature","attestation_identity"}}


@dataclass(frozen=True)
class ExecutorAcknowledgementGovernanceBundle:
    executor_admission_authorization: ExecutorAdmissionAuthorization
    executor_acceptance_attestation: ExecutorAcceptanceAttestation
    admission_registry: RuntimeAdmissionRegistry
    admission_registry_entry: AdmissionRegistryEntry
    acknowledgement_registry: ExecutorAcknowledgementRegistry
    expected_admission_registry_identity: str
    expected_acknowledgement_registry_identity: str
    acknowledged_at: str
    bundle_identity: str = ""
    def __post_init__(self):
        from .registry import ExecutorAcknowledgementRegistry
        for value in (self.executor_admission_authorization,self.executor_acceptance_attestation,
                      self.admission_registry,self.admission_registry_entry,self.acknowledgement_registry):
            _revalidate(value)
        if type(self.acknowledgement_registry) is not ExecutorAcknowledgementRegistry:
            raise ValueError("ACKNOWLEDGEMENT_REGISTRY_TYPE_INVALID")
        _utc(self.acknowledged_at)
        if not _text(self.expected_admission_registry_identity) or not _text(self.expected_acknowledgement_registry_identity):
            raise ValueError("EXPECTED_REGISTRY_IDENTITY_INVALID")
        payload={"executor_authorization":self.executor_admission_authorization.authorization_identity,
            "attestation":self.executor_acceptance_attestation.attestation_identity,
            "admission_registry":self.admission_registry.registry_identity,
            "admission_entry":self.admission_registry_entry.entry_identity,
            "acknowledgement_registry":self.acknowledgement_registry.registry_identity,
            "expected_admission_registry":self.expected_admission_registry_identity,
            "expected_acknowledgement_registry":self.expected_acknowledgement_registry_identity,
            "acknowledged_at":self.acknowledged_at}
        expected=_id("EXECUTOR_ACKNOWLEDGEMENT_GOVERNANCE_BUNDLE",payload)
        if self.bundle_identity and self.bundle_identity!=expected: raise ValueError("ACKNOWLEDGEMENT_BUNDLE_IDENTITY_INVALID")
        object.__setattr__(self,"bundle_identity",expected)


@dataclass(frozen=True)
class AcknowledgementValidation:
    check: str; passed: bool; reason: str
    def __post_init__(self):
        if self.check not in ACKNOWLEDGEMENT_CHECKS or type(self.passed) is not bool or not _text(self.reason):
            raise ValueError("ACKNOWLEDGEMENT_VALIDATION_INVALID")


@dataclass(frozen=True)
class ExecutorReadinessEvidence:
    """Historical name retained; this proves acknowledgement, not operational readiness."""
    bundle_identity: str
    executor_admission_authorization_identity: str
    attestation_identity: str
    executor_identity: str
    executor_version: str
    executor_instance_identity: str
    executor_session_identity: str
    attestation_nonce: str
    runtime_instance_identity: str
    activation_generation: int
    artifact_identity: str
    runtime_contract_identity: str
    target_environment_identity: str
    executor_policy_identity: str
    acknowledgement_authority_identity: str
    validations: tuple[AcknowledgementValidation,...]
    recorded_at: str
    accepted: bool
    evidence_identity: str = ""
    def __post_init__(self):
        values=tuple(self.validations);object.__setattr__(self,"validations",values);_utc(self.recorded_at)
        excluded={"activation_generation","validations","accepted","evidence_identity"}
        if (not all(_text(getattr(self,x)) for x in self.__dataclass_fields__ if x not in excluded)
                or type(self.activation_generation) is not int
                or tuple(x.check for x in values)!=ACKNOWLEDGEMENT_CHECKS
                or self.accepted!=all(x.passed for x in values)):
            raise ValueError("EXECUTOR_ACKNOWLEDGEMENT_EVIDENCE_INVALID")
        expected=_id("EXECUTOR_ACKNOWLEDGEMENT_EVIDENCE",{k:(tuple((x.check,x.passed,x.reason) for x in values) if k=="validations" else v) for k,v in self.__dict__.items() if k!="evidence_identity"})
        if self.evidence_identity and self.evidence_identity!=expected: raise ValueError("ACKNOWLEDGEMENT_EVIDENCE_IDENTITY_INVALID")
        object.__setattr__(self,"evidence_identity",expected)


@dataclass(frozen=True)
class ExecutorAcknowledgement:
    executor_admission_authorization_identity: str
    attestation_identity: str
    acknowledgement_evidence_identity: str
    executor_identity: str
    executor_version: str
    executor_instance_identity: str
    executor_session_identity: str
    runtime_instance_identity: str
    activation_generation: int
    acknowledged_at: str
    acknowledgement_identity: str = ""
    executor_admission_acknowledged: bool = True
    runtime_started: bool = False
    broker_connected: bool = False
    orders_submitted: bool = False
    trades_executed: bool = False
    def __post_init__(self):
        _utc(self.acknowledged_at)
        excluded={"activation_generation","acknowledgement_identity","executor_admission_acknowledged","runtime_started","broker_connected","orders_submitted","trades_executed"}
        flags=(self.executor_admission_acknowledged,self.runtime_started,self.broker_connected,self.orders_submitted,self.trades_executed)
        if (not all(_text(getattr(self,x)) for x in self.__dataclass_fields__ if x not in excluded)
                or type(self.activation_generation) is not int or flags!=(True,False,False,False,False)):
            raise ValueError("EXECUTOR_ACKNOWLEDGEMENT_INVALID")
        expected=_id("EXECUTOR_ACKNOWLEDGEMENT",{k:v for k,v in self.__dict__.items() if k!="acknowledgement_identity"})
        if self.acknowledgement_identity and self.acknowledgement_identity!=expected: raise ValueError("EXECUTOR_ACKNOWLEDGEMENT_IDENTITY_INVALID")
        object.__setattr__(self,"acknowledgement_identity",expected)


@dataclass(frozen=True)
class ExecutorAcknowledgementAuthorization:
    acknowledgement_identity: str
    acknowledgement_evidence_identity: str
    executor_admission_authorization_identity: str
    executor_identity: str
    executor_version: str
    executor_instance_identity: str
    executor_session_identity: str
    runtime_instance_identity: str
    activation_generation: int
    recorded_at: str
    authorization_identity: str = ""
    executor_admission_acknowledged: bool = True
    operational_execution_ready: bool = False
    runtime_start_authorized: bool = False
    broker_connection_authorized: bool = False
    order_submission_authorized: bool = False
    trade_execution_authorized: bool = False
    runtime_modification_authorized: bool = False
    strategy_generation_authorized: bool = False
    ai_training_authorized: bool = False
    ai_evaluation_authorized: bool = False
    def __post_init__(self):
        _utc(self.recorded_at)
        excluded={"activation_generation","authorization_identity","executor_admission_acknowledged","operational_execution_ready","runtime_start_authorized","broker_connection_authorized","order_submission_authorized","trade_execution_authorized","runtime_modification_authorized","strategy_generation_authorized","ai_training_authorized","ai_evaluation_authorized"}
        flags=tuple(getattr(self,x) for x in ("executor_admission_acknowledged","operational_execution_ready","runtime_start_authorized","broker_connection_authorized","order_submission_authorized","trade_execution_authorized","runtime_modification_authorized","strategy_generation_authorized","ai_training_authorized","ai_evaluation_authorized"))
        if (not all(_text(getattr(self,x)) for x in self.__dataclass_fields__ if x not in excluded)
                or type(self.activation_generation) is not int or flags!=(True,False,False,False,False,False,False,False,False,False)):
            raise ValueError("EXECUTOR_ACKNOWLEDGEMENT_AUTHORIZATION_INVALID")
        expected=_id("EXECUTOR_ACKNOWLEDGEMENT_AUTHORIZATION",{k:v for k,v in self.__dict__.items() if k!="authorization_identity"})
        if self.authorization_identity and self.authorization_identity!=expected: raise ValueError("ACKNOWLEDGEMENT_AUTHORIZATION_IDENTITY_INVALID")
        object.__setattr__(self,"authorization_identity",expected)

# The PR279 output is acknowledgement-only. This compatibility name must not be
# interpreted as operational readiness.
ExecutionReadinessAuthorization = ExecutorAcknowledgementAuthorization


@dataclass(frozen=True)
class ExecutorLifecycleRecord:
    acknowledgement_identity: str; from_state: str; to_state: str; occurred_at: str
    sequence: int; previous_record_identity: str|None; record_identity: str = ""
    def __post_init__(self):
        _utc(self.occurred_at)
        if ((self.from_state,self.to_state) not in LIFECYCLE or self.sequence<1 or
                (self.sequence==1)!=(self.previous_record_identity is None)):
            raise ValueError("EXECUTOR_LIFECYCLE_INVALID")
        expected=_id("EXECUTOR_LIFECYCLE_RECORD",{k:v for k,v in self.__dict__.items() if k!="record_identity"})
        if self.record_identity and self.record_identity!=expected: raise ValueError("EXECUTOR_LIFECYCLE_IDENTITY_INVALID")
        object.__setattr__(self,"record_identity",expected)


@dataclass(frozen=True)
class ExecutorAcknowledgementRegistryEntry:
    acknowledgement: ExecutorAcknowledgement
    acknowledgement_evidence: ExecutorReadinessEvidence
    acknowledgement_authorization: ExecutorAcknowledgementAuthorization
    lifecycle: tuple[ExecutorLifecycleRecord,...]
    sequence: int
    previous_entry_identity: str|None
    entry_identity: str = ""
    def __post_init__(self):
        for value in (self.acknowledgement,self.acknowledgement_evidence,self.acknowledgement_authorization): _revalidate(value)
        lifecycle=tuple(self.lifecycle);object.__setattr__(self,"lifecycle",lifecycle)
        if (tuple((x.from_state,x.to_state) for x in lifecycle)!=LIFECYCLE or tuple(x.sequence for x in lifecycle)!=(1,2,3)
                or any(x.acknowledgement_identity!=self.acknowledgement.acknowledgement_identity for x in lifecycle)
                or any(x.previous_record_identity!=(None if i==0 else lifecycle[i-1].record_identity) for i,x in enumerate(lifecycle))
                or self.acknowledgement.acknowledgement_evidence_identity!=self.acknowledgement_evidence.evidence_identity
                or self.acknowledgement_authorization.acknowledgement_identity!=self.acknowledgement.acknowledgement_identity
                or self.sequence<1 or (self.sequence==1)!=(self.previous_entry_identity is None)):
            raise ValueError("ACKNOWLEDGEMENT_REGISTRY_ENTRY_INVALID")
        expected=_id("EXECUTOR_ACKNOWLEDGEMENT_REGISTRY_ENTRY",{"acknowledgement":self.acknowledgement.acknowledgement_identity,"evidence":self.acknowledgement_evidence.evidence_identity,"authorization":self.acknowledgement_authorization.authorization_identity,"lifecycle":tuple(x.record_identity for x in lifecycle),"sequence":self.sequence,"previous":self.previous_entry_identity})
        if self.entry_identity and self.entry_identity!=expected: raise ValueError("ACKNOWLEDGEMENT_REGISTRY_ENTRY_IDENTITY_INVALID")
        object.__setattr__(self,"entry_identity",expected)

    @property
    def readiness_evidence(self): return self.acknowledgement_evidence
    @property
    def readiness_authorization(self): return self.acknowledgement_authorization


@dataclass(frozen=True)
class ExecutorAcknowledgementResult:
    acknowledgement: ExecutorAcknowledgement
    acknowledgement_evidence: ExecutorReadinessEvidence
    registry_entry: ExecutorAcknowledgementRegistryEntry
    acknowledgement_authorization: ExecutorAcknowledgementAuthorization
    def __post_init__(self):
        if (self.registry_entry.acknowledgement!=self.acknowledgement or
                self.registry_entry.acknowledgement_evidence!=self.acknowledgement_evidence or
                self.registry_entry.acknowledgement_authorization!=self.acknowledgement_authorization):
            raise ValueError("EXECUTOR_ACKNOWLEDGEMENT_RESULT_BINDING_INVALID")
    @property
    def readiness_evidence(self): return self.acknowledgement_evidence
    @property
    def readiness_authorization(self): return self.acknowledgement_authorization
