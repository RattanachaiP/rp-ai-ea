"""Immutable PR278 Runtime Admission Authority contracts."""
from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from learning.deployment.contracts import _revalidate, _text, _utc
from learning.promotion.identity import identity_for
from learning.release import ReleaseRegistry, ReleaseRegistryEntry
from learning.runtime_activation import ActivationRegistry, ActivationRegistryEntry, ExecutorHandoff

if TYPE_CHECKING:
    from .registry import RuntimeAdmissionRegistry

ADMISSION_SCHEMA_VERSION = "PR278.RUNTIME_ADMISSION.2.0"
ADMISSION_CHECKS = (
    "handoff_identity_integrity", "release_registry_integrity", "release_registry_membership",
    "release_effectiveness", "activation_registry_integrity", "activation_registry_membership",
    "activation_effectiveness", "activation_evidence", "authorization_lineage",
    "certificate_lineage", "release_manifest_lineage", "artifact_lineage",
    "runtime_contract_lineage", "environment_lineage", "runtime_lineage",
    "executor_policy", "lifecycle_lineage", "event_lineage", "handoff_freshness",
    "single_admission",
)
LIFECYCLE = (("REQUESTED", "VALIDATED"), ("VALIDATED", "ADMISSION_AUTHORIZED"),
             ("ADMISSION_AUTHORIZED", "RECORDED"))


def _id(kind, payload): return identity_for(kind, payload)


@dataclass(frozen=True)
class ExecutorDescriptor:
    executor_identity: str
    executor_version: str
    descriptor_identity: str = ""
    def __post_init__(self):
        if not _text(self.executor_identity) or not _text(self.executor_version):
            raise ValueError("EXECUTOR_DESCRIPTOR_INVALID")
        expected = _id("EXECUTOR_DESCRIPTOR", {"executor_identity": self.executor_identity,
            "executor_version": self.executor_version})
        if self.descriptor_identity and self.descriptor_identity != expected:
            raise ValueError("EXECUTOR_DESCRIPTOR_IDENTITY_INVALID")
        object.__setattr__(self, "descriptor_identity", expected)


@dataclass(frozen=True)
class ExecutorAdmissionPolicy:
    policy_reference: str
    admission_authority_identity: str
    allowed_executors: tuple[ExecutorDescriptor, ...]
    maximum_handoff_age_seconds: int
    admission_validity_seconds: int
    policy_identity: str = ""
    schema_version: str = ADMISSION_SCHEMA_VERSION
    def __post_init__(self):
        allowed = tuple(self.allowed_executors); object.__setattr__(self, "allowed_executors", allowed)
        for value in allowed: _revalidate(value)
        if (not _text(self.policy_reference) or not _text(self.admission_authority_identity)
                or not allowed or len({x.descriptor_identity for x in allowed}) != len(allowed)
                or type(self.maximum_handoff_age_seconds) is not int
                or self.maximum_handoff_age_seconds < 1
                or type(self.admission_validity_seconds) is not int
                or self.admission_validity_seconds < 1
                or self.schema_version != ADMISSION_SCHEMA_VERSION):
            raise ValueError("EXECUTOR_ADMISSION_POLICY_INVALID")
        expected = _id("EXECUTOR_ADMISSION_POLICY", {k: v for k, v in self.__dict__.items()
            if k != "policy_identity"} | {"allowed_executors": tuple(x.descriptor_identity for x in allowed)})
        if self.policy_identity and self.policy_identity != expected:
            raise ValueError("EXECUTOR_ADMISSION_POLICY_IDENTITY_INVALID")
        object.__setattr__(self, "policy_identity", expected)
    def permits(self, identity, version):
        return any(x.executor_identity == identity and x.executor_version == version
                   for x in self.allowed_executors)


@dataclass(frozen=True)
class RuntimeAdmissionGovernanceBundle:
    """The complete current governance state used to authenticate one PR277 handoff."""
    release_registry: ReleaseRegistry
    release_registry_entry: ReleaseRegistryEntry
    activation_registry: ActivationRegistry
    activation_registry_entry: ActivationRegistryEntry
    executor_handoff: ExecutorHandoff
    executor_admission_policy: ExecutorAdmissionPolicy
    admission_registry: RuntimeAdmissionRegistry
    expected_release_registry_identity: str
    expected_activation_registry_identity: str
    expected_admission_registry_identity: str
    admitted_at: str
    bundle_identity: str = ""
    def __post_init__(self):
        # Import here avoids a contracts/registry import cycle while retaining a concrete check.
        from .registry import RuntimeAdmissionRegistry
        if type(self.admission_registry) is not RuntimeAdmissionRegistry:
            raise ValueError("ADMISSION_REGISTRY_TYPE_INVALID")
        for value in (self.release_registry, self.release_registry_entry,
                self.activation_registry, self.activation_registry_entry,
                self.executor_handoff, self.executor_admission_policy, self.admission_registry):
            _revalidate(value)
        _utc(self.admitted_at)
        for name in ("expected_release_registry_identity", "expected_activation_registry_identity",
                     "expected_admission_registry_identity"):
            if not _text(getattr(self, name)): raise ValueError("EXPECTED_REGISTRY_IDENTITY_INVALID")
        payload = {"release_registry": self.release_registry.registry_identity,
            "release_entry": self.release_registry_entry.entry_identity,
            "activation_registry": self.activation_registry.registry_identity,
            "activation_entry": self.activation_registry_entry.entry_identity,
            "handoff": self.executor_handoff.handoff_identity,
            "policy": self.executor_admission_policy.policy_identity,
            "admission_registry": self.admission_registry.registry_identity,
            "expected_release_registry": self.expected_release_registry_identity,
            "expected_activation_registry": self.expected_activation_registry_identity,
            "expected_admission_registry": self.expected_admission_registry_identity,
            "admitted_at": self.admitted_at}
        expected = _id("RUNTIME_ADMISSION_GOVERNANCE_BUNDLE", payload)
        if self.bundle_identity and self.bundle_identity != expected:
            raise ValueError("RUNTIME_ADMISSION_BUNDLE_IDENTITY_INVALID")
        object.__setattr__(self, "bundle_identity", expected)


@dataclass(frozen=True)
class AdmissionValidation:
    check: str; passed: bool; reason: str
    def __post_init__(self):
        if self.check not in ADMISSION_CHECKS or type(self.passed) is not bool or not _text(self.reason):
            raise ValueError("ADMISSION_VALIDATION_INVALID")


@dataclass(frozen=True)
class RuntimeAdmissionEvidence:
    bundle_identity: str
    release_registry_identity: str
    release_registry_entry_identity: str
    activation_registry_identity: str
    activation_registry_entry_identity: str
    handoff_identity: str
    authorization_identity: str
    certificate_identity: str
    release_manifest_identity: str
    artifact_identity: str
    runtime_contract_identity: str
    target_environment_identity: str
    runtime_instance_identity: str
    executor_identity: str
    executor_version: str
    activation_generation: int
    executor_admission_policy_identity: str
    validations: tuple[AdmissionValidation, ...]
    recorded_at: str
    accepted: bool
    evidence_identity: str = ""
    def __post_init__(self):
        _utc(self.recorded_at); values = tuple(self.validations); object.__setattr__(self, "validations", values)
        texts = tuple(name for name in self.__dataclass_fields__ if name not in {
            "activation_generation", "validations", "accepted", "evidence_identity"})
        if (not all(_text(getattr(self, x)) for x in texts)
                or type(self.activation_generation) is not int
                or tuple(x.check for x in values) != ADMISSION_CHECKS
                or self.accepted != all(x.passed for x in values)):
            raise ValueError("RUNTIME_ADMISSION_EVIDENCE_INVALID")
        expected = _id("RUNTIME_ADMISSION_EVIDENCE", {k: (tuple((x.check,x.passed,x.reason)
            for x in values) if k == "validations" else v) for k,v in self.__dict__.items()
            if k != "evidence_identity"})
        if self.evidence_identity and self.evidence_identity != expected:
            raise ValueError("RUNTIME_ADMISSION_EVIDENCE_IDENTITY_INVALID")
        object.__setattr__(self, "evidence_identity", expected)


@dataclass(frozen=True)
class AdmissionLifecycleTransition:
    handoff_identity: str; from_state: str; to_state: str; occurred_at: str
    sequence: int; previous_transition_identity: str | None; transition_identity: str = ""
    def __post_init__(self):
        _utc(self.occurred_at)
        if ((self.from_state, self.to_state) not in LIFECYCLE or self.sequence < 1
                or (self.sequence == 1) != (self.previous_transition_identity is None)):
            raise ValueError("ADMISSION_LIFECYCLE_INVALID")
        expected = _id("ADMISSION_LIFECYCLE_TRANSITION", {k:v for k,v in self.__dict__.items()
            if k != "transition_identity"})
        if self.transition_identity and self.transition_identity != expected:
            raise ValueError("ADMISSION_LIFECYCLE_IDENTITY_INVALID")
        object.__setattr__(self, "transition_identity", expected)


@dataclass(frozen=True)
class RuntimeAdmissionAuthorization:
    handoff_identity: str; runtime_instance_identity: str; executor_identity: str
    executor_version: str; activation_generation: int; evidence_identity: str
    policy_identity: str; authorized_at: str; valid_until: str
    authorization_identity: str = ""; runtime_admission_authorized: bool = True
    broker_access_authorized: bool = False; trade_execution_authorized: bool = False
    runtime_modification_authorized: bool = False; strategy_generation_authorized: bool = False
    ai_training_authorized: bool = False; ai_evaluation_authorized: bool = False
    def __post_init__(self):
        start,end = _utc(self.authorized_at),_utc(self.valid_until)
        flags=(self.runtime_admission_authorized,self.broker_access_authorized,
            self.trade_execution_authorized,self.runtime_modification_authorized,
            self.strategy_generation_authorized,self.ai_training_authorized,self.ai_evaluation_authorized)
        if (not all(_text(getattr(self,x)) for x in ("handoff_identity","runtime_instance_identity",
                "executor_identity","executor_version","evidence_identity","policy_identity"))
                or type(self.activation_generation) is not int or start >= end
                or flags != (True,False,False,False,False,False,False)):
            raise ValueError("RUNTIME_ADMISSION_AUTHORIZATION_INVALID")
        expected=_id("RUNTIME_ADMISSION_AUTHORIZATION",{k:v for k,v in self.__dict__.items()
            if k != "authorization_identity"})
        if self.authorization_identity and self.authorization_identity != expected:
            raise ValueError("RUNTIME_ADMISSION_AUTHORIZATION_IDENTITY_INVALID")
        object.__setattr__(self,"authorization_identity",expected)


@dataclass(frozen=True)
class ExecutorAdmissionAuthorization:
    admission_authorization_identity: str; handoff_identity: str; executor_identity: str
    executor_version: str; runtime_instance_identity: str; activation_generation: int
    authorized_at: str; valid_until: str; authorization_identity: str = ""
    executor_admission_authorized: bool = True; executor_acknowledged: bool = False
    broker_connection_performed: bool = False; trade_execution_performed: bool = False
    def __post_init__(self):
        if (not all(_text(getattr(self,x)) for x in ("admission_authorization_identity",
                "handoff_identity","executor_identity","executor_version","runtime_instance_identity"))
                or type(self.activation_generation) is not int or _utc(self.authorized_at)>=_utc(self.valid_until)
                or self.executor_admission_authorized is not True or self.executor_acknowledged
                or self.broker_connection_performed or self.trade_execution_performed):
            raise ValueError("EXECUTOR_ADMISSION_AUTHORIZATION_INVALID")
        expected=_id("EXECUTOR_ADMISSION_AUTHORIZATION",{k:v for k,v in self.__dict__.items()
            if k != "authorization_identity"})
        if self.authorization_identity and self.authorization_identity != expected:
            raise ValueError("EXECUTOR_ADMISSION_AUTHORIZATION_IDENTITY_INVALID")
        object.__setattr__(self,"authorization_identity",expected)


@dataclass(frozen=True)
class AdmissionRegistryEntry:
    admission_authorization: RuntimeAdmissionAuthorization
    evidence: RuntimeAdmissionEvidence
    executor_admission_authorization: ExecutorAdmissionAuthorization
    transitions: tuple[AdmissionLifecycleTransition, ...]
    sequence: int; previous_entry_identity: str | None; entry_identity: str = ""
    def __post_init__(self):
        for value in (self.admission_authorization,self.evidence,self.executor_admission_authorization): _revalidate(value)
        transitions=tuple(self.transitions); object.__setattr__(self,"transitions",transitions)
        if (tuple((x.from_state,x.to_state) for x in transitions) != LIFECYCLE
                or tuple(x.sequence for x in transitions) != (1,2,3)
                or any(x.handoff_identity != self.admission_authorization.handoff_identity for x in transitions)
                or any(x.previous_transition_identity != (None if i == 0 else transitions[i-1].transition_identity)
                       for i,x in enumerate(transitions))
                or self.admission_authorization.evidence_identity != self.evidence.evidence_identity
                or self.executor_admission_authorization.admission_authorization_identity != self.admission_authorization.authorization_identity
                or self.sequence < 1 or (self.sequence == 1) != (self.previous_entry_identity is None)):
            raise ValueError("ADMISSION_REGISTRY_ENTRY_INVALID")
        expected=_id("RUNTIME_ADMISSION_REGISTRY_ENTRY",{"admission":self.admission_authorization.authorization_identity,
            "evidence":self.evidence.evidence_identity,"executor_authorization":self.executor_admission_authorization.authorization_identity,
            "transitions":tuple(x.transition_identity for x in transitions),"sequence":self.sequence,"previous":self.previous_entry_identity})
        if self.entry_identity and self.entry_identity != expected: raise ValueError("ADMISSION_REGISTRY_ENTRY_IDENTITY_INVALID")
        object.__setattr__(self,"entry_identity",expected)


@dataclass(frozen=True)
class RuntimeAdmissionResult:
    evidence: RuntimeAdmissionEvidence; admission_authorization: RuntimeAdmissionAuthorization
    registry_entry: AdmissionRegistryEntry; executor_admission_authorization: ExecutorAdmissionAuthorization
    def __post_init__(self):
        if (self.registry_entry.evidence != self.evidence or
            self.registry_entry.admission_authorization != self.admission_authorization or
            self.registry_entry.executor_admission_authorization != self.executor_admission_authorization):
            raise ValueError("RUNTIME_ADMISSION_RESULT_BINDING_INVALID")
