"""Immutable PR279 Executor Acknowledgement Authority contracts."""
from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from learning.deployment.contracts import _revalidate, _text, _utc
from learning.promotion.identity import identity_for
from learning.runtime_admission import (RuntimeAdmissionAuthorization,
    RuntimeAdmissionEvidence, RuntimeAdmissionRegistry)

if TYPE_CHECKING:
    from .registry import ExecutorAcknowledgementRegistry

ACKNOWLEDGEMENT_SCHEMA_VERSION = "PR279.EXECUTOR_ACKNOWLEDGEMENT.1.0"
ACKNOWLEDGEMENT_CHECKS = ("admission_authorization_integrity", "authorization_validity_window",
    "executor_identity", "executor_version", "runtime_instance_identity", "activation_generation",
    "runtime_contract", "target_environment", "admission_registry_membership", "replay_protection",
    "revocation_status", "lifecycle_consistency")
LIFECYCLE = (("AUTHORIZED", "ACKNOWLEDGED"), ("ACKNOWLEDGED", "RECORDED"),
             ("RECORDED", "READY"))


def _id(kind, payload): return identity_for(kind, payload)


@dataclass(frozen=True)
class AdmissionAuthorizationRevocation:
    admission_authorization_identity: str
    revoked_by: str
    reason: str
    revoked_at: str
    revocation_identity: str = ""
    def __post_init__(self):
        _utc(self.revoked_at)
        if not all(_text(getattr(self, x)) for x in ("admission_authorization_identity", "revoked_by", "reason")):
            raise ValueError("ADMISSION_AUTHORIZATION_REVOCATION_INVALID")
        expected = _id("ADMISSION_AUTHORIZATION_REVOCATION", {k:v for k,v in self.__dict__.items() if k != "revocation_identity"})
        if self.revocation_identity and self.revocation_identity != expected:
            raise ValueError("ADMISSION_AUTHORIZATION_REVOCATION_IDENTITY_INVALID")
        object.__setattr__(self, "revocation_identity", expected)


@dataclass(frozen=True)
class ExecutorAcknowledgementGovernanceBundle:
    admission_authorization: RuntimeAdmissionAuthorization
    runtime_admission_evidence: RuntimeAdmissionEvidence
    runtime_instance_identity: str
    executor_identity: str
    executor_version: str
    admission_registry: RuntimeAdmissionRegistry
    acknowledgement_registry: ExecutorAcknowledgementRegistry
    expected_admission_registry_identity: str
    expected_acknowledgement_registry_identity: str
    acknowledged_at: str
    bundle_identity: str = ""
    def __post_init__(self):
        from .registry import ExecutorAcknowledgementRegistry
        for value in (self.admission_authorization, self.runtime_admission_evidence,
                      self.admission_registry, self.acknowledgement_registry): _revalidate(value)
        if type(self.acknowledgement_registry) is not ExecutorAcknowledgementRegistry:
            raise ValueError("ACKNOWLEDGEMENT_REGISTRY_TYPE_INVALID")
        _utc(self.acknowledged_at)
        for name in ("runtime_instance_identity", "executor_identity", "executor_version",
                     "expected_admission_registry_identity", "expected_acknowledgement_registry_identity"):
            if not _text(getattr(self, name)): raise ValueError("ACKNOWLEDGEMENT_INPUT_INVALID")
        payload = {"authorization": self.admission_authorization.authorization_identity,
            "evidence": self.runtime_admission_evidence.evidence_identity,
            "runtime": self.runtime_instance_identity, "executor": self.executor_identity,
            "version": self.executor_version, "admission_registry": self.admission_registry.registry_identity,
            "acknowledgement_registry": self.acknowledgement_registry.registry_identity,
            "expected_admission_registry": self.expected_admission_registry_identity,
            "expected_acknowledgement_registry": self.expected_acknowledgement_registry_identity,
            "acknowledged_at": self.acknowledged_at}
        expected = _id("EXECUTOR_ACKNOWLEDGEMENT_GOVERNANCE_BUNDLE", payload)
        if self.bundle_identity and self.bundle_identity != expected: raise ValueError("ACKNOWLEDGEMENT_BUNDLE_IDENTITY_INVALID")
        object.__setattr__(self, "bundle_identity", expected)


@dataclass(frozen=True)
class AcknowledgementValidation:
    check: str; passed: bool; reason: str
    def __post_init__(self):
        if self.check not in ACKNOWLEDGEMENT_CHECKS or type(self.passed) is not bool or not _text(self.reason):
            raise ValueError("ACKNOWLEDGEMENT_VALIDATION_INVALID")


@dataclass(frozen=True)
class ExecutorReadinessEvidence:
    bundle_identity: str; admission_authorization_identity: str; admission_evidence_identity: str
    runtime_instance_identity: str; executor_identity: str; executor_version: str
    activation_generation: int; runtime_contract_identity: str; target_environment_identity: str
    validations: tuple[AcknowledgementValidation, ...]; recorded_at: str; accepted: bool
    evidence_identity: str = ""
    def __post_init__(self):
        values=tuple(self.validations); object.__setattr__(self,"validations",values); _utc(self.recorded_at)
        texts=("bundle_identity","admission_authorization_identity","admission_evidence_identity",
            "runtime_instance_identity","executor_identity","executor_version","runtime_contract_identity",
            "target_environment_identity")
        if (not all(_text(getattr(self,x)) for x in texts) or type(self.activation_generation) is not int
                or tuple(x.check for x in values) != ACKNOWLEDGEMENT_CHECKS
                or self.accepted != all(x.passed for x in values)):
            raise ValueError("EXECUTOR_READINESS_EVIDENCE_INVALID")
        expected=_id("EXECUTOR_READINESS_EVIDENCE",{k:(tuple((x.check,x.passed,x.reason) for x in values) if k=="validations" else v) for k,v in self.__dict__.items() if k!="evidence_identity"})
        if self.evidence_identity and self.evidence_identity != expected: raise ValueError("READINESS_EVIDENCE_IDENTITY_INVALID")
        object.__setattr__(self,"evidence_identity",expected)


@dataclass(frozen=True)
class ExecutorAcknowledgement:
    admission_authorization_identity: str; readiness_evidence_identity: str
    runtime_instance_identity: str; executor_identity: str; executor_version: str
    activation_generation: int; acknowledged_at: str; acknowledgement_identity: str = ""
    executor_acknowledged: bool = True; runtime_started: bool = False
    broker_connected: bool = False; orders_submitted: bool = False; trades_executed: bool = False
    def __post_init__(self):
        _utc(self.acknowledged_at)
        texts=("admission_authorization_identity","readiness_evidence_identity","runtime_instance_identity","executor_identity","executor_version")
        flags=(self.executor_acknowledged,self.runtime_started,self.broker_connected,self.orders_submitted,self.trades_executed)
        if not all(_text(getattr(self,x)) for x in texts) or type(self.activation_generation) is not int or flags!=(True,False,False,False,False):
            raise ValueError("EXECUTOR_ACKNOWLEDGEMENT_INVALID")
        expected=_id("EXECUTOR_ACKNOWLEDGEMENT",{k:v for k,v in self.__dict__.items() if k!="acknowledgement_identity"})
        if self.acknowledgement_identity and self.acknowledgement_identity != expected: raise ValueError("EXECUTOR_ACKNOWLEDGEMENT_IDENTITY_INVALID")
        object.__setattr__(self,"acknowledgement_identity",expected)


@dataclass(frozen=True)
class ExecutionReadinessAuthorization:
    acknowledgement_identity: str; readiness_evidence_identity: str; admission_authorization_identity: str
    runtime_instance_identity: str; executor_identity: str; executor_version: str; activation_generation: int
    authorized_at: str; authorization_identity: str = ""; execution_ready: bool = True
    runtime_started: bool = False; broker_connection_performed: bool = False
    order_submission_performed: bool = False; trade_execution_performed: bool = False
    runtime_modification_authorized: bool = False; strategy_generation_authorized: bool = False
    ai_training_authorized: bool = False; ai_evaluation_authorized: bool = False
    def __post_init__(self):
        _utc(self.authorized_at)
        texts=("acknowledgement_identity","readiness_evidence_identity","admission_authorization_identity","runtime_instance_identity","executor_identity","executor_version")
        flags=tuple(getattr(self,x) for x in ("execution_ready","runtime_started","broker_connection_performed","order_submission_performed","trade_execution_performed","runtime_modification_authorized","strategy_generation_authorized","ai_training_authorized","ai_evaluation_authorized"))
        if not all(_text(getattr(self,x)) for x in texts) or type(self.activation_generation) is not int or flags!=(True,False,False,False,False,False,False,False,False):
            raise ValueError("EXECUTION_READINESS_AUTHORIZATION_INVALID")
        expected=_id("EXECUTION_READINESS_AUTHORIZATION",{k:v for k,v in self.__dict__.items() if k!="authorization_identity"})
        if self.authorization_identity and self.authorization_identity != expected: raise ValueError("READINESS_AUTHORIZATION_IDENTITY_INVALID")
        object.__setattr__(self,"authorization_identity",expected)


@dataclass(frozen=True)
class ExecutorLifecycleRecord:
    acknowledgement_identity: str; from_state: str; to_state: str; occurred_at: str
    sequence: int; previous_record_identity: str|None; record_identity: str = ""
    def __post_init__(self):
        _utc(self.occurred_at)
        if ((self.from_state,self.to_state) not in LIFECYCLE or self.sequence<1
                or (self.sequence==1)!=(self.previous_record_identity is None)):
            raise ValueError("EXECUTOR_LIFECYCLE_INVALID")
        expected=_id("EXECUTOR_LIFECYCLE_RECORD",{k:v for k,v in self.__dict__.items() if k!="record_identity"})
        if self.record_identity and self.record_identity != expected: raise ValueError("EXECUTOR_LIFECYCLE_IDENTITY_INVALID")
        object.__setattr__(self,"record_identity",expected)


@dataclass(frozen=True)
class ExecutorAcknowledgementRegistryEntry:
    acknowledgement: ExecutorAcknowledgement; readiness_evidence: ExecutorReadinessEvidence
    readiness_authorization: ExecutionReadinessAuthorization; lifecycle: tuple[ExecutorLifecycleRecord,...]
    sequence: int; previous_entry_identity: str|None; entry_identity: str = ""
    def __post_init__(self):
        for value in (self.acknowledgement,self.readiness_evidence,self.readiness_authorization): _revalidate(value)
        lifecycle=tuple(self.lifecycle); object.__setattr__(self,"lifecycle",lifecycle)
        if (tuple((x.from_state,x.to_state) for x in lifecycle)!=LIFECYCLE
                or tuple(x.sequence for x in lifecycle)!=(1,2,3)
                or any(x.acknowledgement_identity!=self.acknowledgement.acknowledgement_identity for x in lifecycle)
                or any(x.previous_record_identity!=(None if i==0 else lifecycle[i-1].record_identity) for i,x in enumerate(lifecycle))
                or self.acknowledgement.readiness_evidence_identity!=self.readiness_evidence.evidence_identity
                or self.readiness_authorization.acknowledgement_identity!=self.acknowledgement.acknowledgement_identity
                or self.sequence<1 or (self.sequence==1)!=(self.previous_entry_identity is None)):
            raise ValueError("ACKNOWLEDGEMENT_REGISTRY_ENTRY_INVALID")
        expected=_id("EXECUTOR_ACKNOWLEDGEMENT_REGISTRY_ENTRY",{"acknowledgement":self.acknowledgement.acknowledgement_identity,"evidence":self.readiness_evidence.evidence_identity,"authorization":self.readiness_authorization.authorization_identity,"lifecycle":tuple(x.record_identity for x in lifecycle),"sequence":self.sequence,"previous":self.previous_entry_identity})
        if self.entry_identity and self.entry_identity!=expected: raise ValueError("ACKNOWLEDGEMENT_REGISTRY_ENTRY_IDENTITY_INVALID")
        object.__setattr__(self,"entry_identity",expected)


@dataclass(frozen=True)
class ExecutorAcknowledgementResult:
    acknowledgement: ExecutorAcknowledgement; readiness_evidence: ExecutorReadinessEvidence
    registry_entry: ExecutorAcknowledgementRegistryEntry
    readiness_authorization: ExecutionReadinessAuthorization
    def __post_init__(self):
        if (self.registry_entry.acknowledgement!=self.acknowledgement or self.registry_entry.readiness_evidence!=self.readiness_evidence
                or self.registry_entry.readiness_authorization!=self.readiness_authorization):
            raise ValueError("EXECUTOR_ACKNOWLEDGEMENT_RESULT_BINDING_INVALID")
