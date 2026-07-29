"""Immutable PR277 Runtime Activation Authority contracts."""
from __future__ import annotations
from dataclasses import dataclass

from learning.deployment.contracts import _revalidate, _text, _utc
from learning.promotion.identity import identity_for
from learning.release import (AuthoritativeReleaseCertificate,
    AuthoritativeReleaseDecision, AuthoritativeReleaseManifest,
    AuthoritativeRuntimeActivationAuthorization, ReleaseRegistry,
    ReleaseRegistryEntry, TargetRuntimeInstance)

ACTIVATION_SCHEMA_VERSION = "PR277.RUNTIME_ACTIVATION.2.0"
ACTIVATION_CHECKS = ("authorization_identity_integrity", "certificate_identity",
    "release_registry_effectiveness", "runtime_instance_identity", "executor_identity",
    "executor_version", "activation_generation", "runtime_contract_identity",
    "target_environment_identity", "artifact_identity", "validity_window",
    "single_use_status", "revocation_status", "registry_identity")


def _id(kind, payload): return identity_for(kind, payload)


@dataclass(frozen=True)
class RuntimeActivationGovernanceBundle:
    release_decision: AuthoritativeReleaseDecision
    release_certificate: AuthoritativeReleaseCertificate
    release_manifest: AuthoritativeReleaseManifest
    authorization: AuthoritativeRuntimeActivationAuthorization
    release_registry: ReleaseRegistry
    release_registry_entry: ReleaseRegistryEntry
    target_runtime: TargetRuntimeInstance
    activation_registry: object
    expected_registry_identity: str
    activated_at: str
    bundle_identity: str = ""
    def __post_init__(self):
        for value in (self.release_decision,self.release_certificate,self.release_manifest,
                      self.authorization,self.release_registry,self.release_registry_entry,
                      self.target_runtime,self.activation_registry): _revalidate(value)
        _utc(self.activated_at)
        if not _text(self.expected_registry_identity): raise ValueError("EXPECTED_REGISTRY_IDENTITY_INVALID")
        payload={"decision":self.release_decision.decision_identity,"certificate":self.release_certificate.certificate_identity,
            "manifest":self.release_manifest.manifest_identity,"authorization":self.authorization.authorization_identity,
            "release_registry":self.release_registry.registry_identity,"release_entry":self.release_registry_entry.entry_identity,
            "runtime":self.target_runtime.instance_identity,"activation_registry":self.activation_registry.registry_identity,
            "expected_registry":self.expected_registry_identity,"activated_at":self.activated_at}
        expected=_id("RUNTIME_ACTIVATION_GOVERNANCE_BUNDLE",payload)
        if self.bundle_identity and self.bundle_identity!=expected: raise ValueError("ACTIVATION_BUNDLE_IDENTITY_INVALID")
        object.__setattr__(self,"bundle_identity",expected)


@dataclass(frozen=True)
class ActivationValidation:
    check:str; passed:bool; reason:str
    def __post_init__(self):
        if self.check not in ACTIVATION_CHECKS or type(self.passed)is not bool or not _text(self.reason): raise ValueError("ACTIVATION_VALIDATION_INVALID")


@dataclass(frozen=True)
class ActivationEvidence:
    bundle_identity:str; validations:tuple[ActivationValidation,...]; validated_at:str
    accepted:bool; evidence_identity:str=""
    def __post_init__(self):
        _utc(self.validated_at); values=tuple(self.validations); object.__setattr__(self,"validations",values)
        if not _text(self.bundle_identity) or tuple(x.check for x in values)!=ACTIVATION_CHECKS or self.accepted!=all(x.passed for x in values): raise ValueError("ACTIVATION_EVIDENCE_INVALID")
        expected=_id("RUNTIME_ACTIVATION_EVIDENCE",{"bundle":self.bundle_identity,"validations":tuple((x.check,x.passed,x.reason) for x in values),"validated_at":self.validated_at,"accepted":self.accepted})
        if self.evidence_identity and self.evidence_identity!=expected: raise ValueError("ACTIVATION_EVIDENCE_IDENTITY_INVALID")
        object.__setattr__(self,"evidence_identity",expected)


@dataclass(frozen=True)
class ActivationLifecycleTransition:
    authorization_identity:str; from_state:str; to_state:str; occurred_at:str
    sequence:int; previous_transition_identity:str|None; transition_identity:str=""
    def __post_init__(self):
        _utc(self.occurred_at)
        allowed={("AUTHORIZED","VALIDATED"),("VALIDATED","CONSUMED"),("CONSUMED","RECORDED"),("RECORDED","HANDOFF"),("HANDOFF","EXECUTOR")}
        if (self.from_state,self.to_state) not in allowed or self.sequence<1 or (self.sequence==1)!=(self.previous_transition_identity is None): raise ValueError("ACTIVATION_LIFECYCLE_INVALID")
        expected=_id("ACTIVATION_LIFECYCLE_TRANSITION",{k:v for k,v in self.__dict__.items() if k!="transition_identity"})
        if self.transition_identity and self.transition_identity!=expected: raise ValueError("ACTIVATION_LIFECYCLE_IDENTITY_INVALID")
        object.__setattr__(self,"transition_identity",expected)


@dataclass(frozen=True)
class ConsumedAuthorization:
    authorization:AuthoritativeRuntimeActivationAuthorization; consumed_at:str; evidence_identity:str; consumption_identity:str=""
    def __post_init__(self):
        _revalidate(self.authorization); _utc(self.consumed_at)
        expected=_id("CONSUMED_RUNTIME_ACTIVATION_AUTHORIZATION",{"authorization":self.authorization.authorization_identity,"at":self.consumed_at,"evidence":self.evidence_identity})
        if self.consumption_identity and self.consumption_identity!=expected: raise ValueError("CONSUMPTION_IDENTITY_INVALID")
        object.__setattr__(self,"consumption_identity",expected)


@dataclass(frozen=True)
class ExecutorHandoff:
    authorization_identity:str; certificate_identity:str; release_manifest_identity:str
    artifact_identity:str; runtime_contract_identity:str; target_environment_identity:str
    executor_identity:str; executor_version:str; runtime_instance_identity:str
    activation_generation:int; release_registry_entry_identity:str; handed_off_at:str
    handoff_identity:str=""; broker_access_authorized:bool=False; trade_execution_authorized:bool=False
    def __post_init__(self):
        _utc(self.handed_off_at)
        excluded={"handoff_identity","broker_access_authorized","trade_execution_authorized"}
        if not all(_text(getattr(self,x)) for x in self.__dataclass_fields__ if x not in excluded|{"activation_generation"}) or type(self.activation_generation)is not int or self.broker_access_authorized or self.trade_execution_authorized: raise ValueError("EXECUTOR_HANDOFF_INVALID")
        expected=_id("EXECUTOR_HANDOFF",{k:v for k,v in self.__dict__.items() if k!="handoff_identity"})
        if self.handoff_identity and self.handoff_identity!=expected: raise ValueError("EXECUTOR_HANDOFF_IDENTITY_INVALID")
        object.__setattr__(self,"handoff_identity",expected)


@dataclass(frozen=True)
class RuntimeActivationEvent:
    consumption_identity:str; handoff_identity:str; occurred_at:str; event_identity:str=""
    def __post_init__(self):
        _utc(self.occurred_at)
        expected=_id("RUNTIME_ACTIVATION_EVENT",{"consumption":self.consumption_identity,"handoff":self.handoff_identity,"at":self.occurred_at})
        if self.event_identity and self.event_identity!=expected: raise ValueError("ACTIVATION_EVENT_IDENTITY_INVALID")
        object.__setattr__(self,"event_identity",expected)


@dataclass(frozen=True)
class ActivationRegistryEntry:
    consumed_authorization:ConsumedAuthorization; evidence:ActivationEvidence
    handoff:ExecutorHandoff; event:RuntimeActivationEvent
    transitions:tuple[ActivationLifecycleTransition,...]; sequence:int
    previous_entry_identity:str|None; entry_identity:str=""
    def __post_init__(self):
        for x in (self.consumed_authorization,self.evidence,self.handoff,self.event): _revalidate(x)
        transitions=tuple(self.transitions); object.__setattr__(self,"transitions",transitions)
        if tuple((x.from_state,x.to_state) for x in transitions)!=(('AUTHORIZED','VALIDATED'),('VALIDATED','CONSUMED'),('CONSUMED','RECORDED'),('RECORDED','HANDOFF'),('HANDOFF','EXECUTOR')) or self.event.handoff_identity!=self.handoff.handoff_identity or self.sequence<1 or (self.sequence==1)!=(self.previous_entry_identity is None): raise ValueError("ACTIVATION_REGISTRY_ENTRY_INVALID")
        expected=_id("ACTIVATION_REGISTRY_ENTRY",{"consumption":self.consumed_authorization.consumption_identity,"evidence":self.evidence.evidence_identity,"handoff":self.handoff.handoff_identity,"event":self.event.event_identity,"transitions":tuple(x.transition_identity for x in transitions),"sequence":self.sequence,"previous":self.previous_entry_identity})
        if self.entry_identity and self.entry_identity!=expected: raise ValueError("ACTIVATION_REGISTRY_ENTRY_IDENTITY_INVALID")
        object.__setattr__(self,"entry_identity",expected)


@dataclass(frozen=True)
class ActivationResult:
    evidence:ActivationEvidence; consumed_authorization:ConsumedAuthorization
    registry_entry:ActivationRegistryEntry; event:RuntimeActivationEvent; executor_handoff:ExecutorHandoff
    def __post_init__(self):
        if self.registry_entry.event.event_identity!=self.event.event_identity or self.event.handoff_identity!=self.executor_handoff.handoff_identity: raise ValueError("ACTIVATION_RESULT_BINDING_INVALID")
