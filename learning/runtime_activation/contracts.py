"""Immutable records at the Runtime Activation Authority boundary."""
from __future__ import annotations

from dataclasses import dataclass

from learning.deployment.contracts import _revalidate, _text, _utc
from learning.promotion.identity import identity_for
from learning.release import (AuthoritativeReleaseCertificate,
                              AuthoritativeRuntimeActivationAuthorization)

ACTIVATION_SCHEMA_VERSION = "PR277.RUNTIME_ACTIVATION.1.0"
ACTIVATION_CHECKS = ("authorization_signature", "certificate_identity",
                     "runtime_instance_identity", "executor_identity",
                     "activation_generation", "validity_window",
                     "single_use_status", "revocation_status")
ACTIVATION_LIFECYCLE = ("AUTHORIZED", "VALIDATED", "CONSUMED", "RECORDED",
                        "HANDOFF", "EXECUTOR")


def _identity(kind, payload):
    return identity_for(kind, payload)


@dataclass(frozen=True)
class ActivationValidation:
    check: str
    passed: bool
    reason: str

    def __post_init__(self):
        if (self.check not in ACTIVATION_CHECKS or type(self.passed) is not bool
                or not _text(self.reason)):
            raise ValueError("ACTIVATION_VALIDATION_INVALID")


@dataclass(frozen=True)
class ActivationEvidence:
    authorization_identity: str
    certificate_identity: str
    runtime_instance_identity: str
    executor_identity: str
    activation_generation: int
    validated_at: str
    validations: tuple[ActivationValidation, ...]
    lifecycle: tuple[str, ...] = ACTIVATION_LIFECYCLE
    evidence_identity: str = ""

    def __post_init__(self):
        _utc(self.validated_at)
        validations = tuple(self.validations)
        if (not all(_text(getattr(self, name)) for name in (
                "authorization_identity", "certificate_identity",
                "runtime_instance_identity", "executor_identity"))
                or type(self.activation_generation) is not int
                or tuple(item.check for item in validations) != ACTIVATION_CHECKS
                or not all(item.passed for item in validations)
                or tuple(self.lifecycle) != ACTIVATION_LIFECYCLE):
            raise ValueError("ACTIVATION_EVIDENCE_INVALID")
        object.__setattr__(self, "validations", validations)
        expected = _identity("RUNTIME_ACTIVATION_EVIDENCE", self.canonical_payload())
        if self.evidence_identity and self.evidence_identity != expected:
            raise ValueError("ACTIVATION_EVIDENCE_IDENTITY_INVALID")
        object.__setattr__(self, "evidence_identity", expected)

    def canonical_payload(self):
        return {"authorization_identity": self.authorization_identity,
                "certificate_identity": self.certificate_identity,
                "runtime_instance_identity": self.runtime_instance_identity,
                "executor_identity": self.executor_identity,
                "activation_generation": self.activation_generation,
                "validated_at": self.validated_at,
                "validations": tuple((v.check, v.passed, v.reason)
                                     for v in self.validations),
                "lifecycle": self.lifecycle}


@dataclass(frozen=True)
class ConsumedAuthorization:
    authorization: AuthoritativeRuntimeActivationAuthorization
    consumed_at: str
    evidence_identity: str
    consumption_identity: str = ""

    def __post_init__(self):
        _revalidate(self.authorization)
        _utc(self.consumed_at)
        if not _text(self.evidence_identity):
            raise ValueError("CONSUMED_AUTHORIZATION_INVALID")
        expected = _identity("CONSUMED_RUNTIME_ACTIVATION_AUTHORIZATION", {
            "authorization_identity": self.authorization.authorization_identity,
            "consumed_at": self.consumed_at,
            "evidence_identity": self.evidence_identity})
        if self.consumption_identity and self.consumption_identity != expected:
            raise ValueError("CONSUMED_AUTHORIZATION_IDENTITY_INVALID")
        object.__setattr__(self, "consumption_identity", expected)


@dataclass(frozen=True)
class RuntimeActivationEvent:
    consumption_identity: str
    runtime_instance_identity: str
    executor_identity: str
    occurred_at: str
    event_type: str = "RUNTIME_ACTIVATION_HANDOFF"
    event_identity: str = ""
    broker_access_authorized: bool = False
    trade_execution_authorized: bool = False

    def __post_init__(self):
        _utc(self.occurred_at)
        if (not all(_text(getattr(self, name)) for name in (
                "consumption_identity", "runtime_instance_identity", "executor_identity"))
                or self.event_type != "RUNTIME_ACTIVATION_HANDOFF"
                or self.broker_access_authorized or self.trade_execution_authorized):
            raise ValueError("RUNTIME_ACTIVATION_EVENT_INVALID")
        expected = _identity("RUNTIME_ACTIVATION_EVENT", {
            name: getattr(self, name) for name in self.__dataclass_fields__
            if name != "event_identity"})
        if self.event_identity and self.event_identity != expected:
            raise ValueError("RUNTIME_ACTIVATION_EVENT_IDENTITY_INVALID")
        object.__setattr__(self, "event_identity", expected)


@dataclass(frozen=True)
class ActivationRegistryEntry:
    consumed_authorization: ConsumedAuthorization
    evidence: ActivationEvidence
    event: RuntimeActivationEvent
    sequence: int
    previous_entry_identity: str | None
    entry_identity: str = ""

    def __post_init__(self):
        for value in (self.consumed_authorization, self.evidence, self.event):
            _revalidate(value)
        if (self.sequence < 1 or (self.sequence == 1) !=
                (self.previous_entry_identity is None)
                or self.consumed_authorization.evidence_identity != self.evidence.evidence_identity
                or self.event.consumption_identity != self.consumed_authorization.consumption_identity):
            raise ValueError("ACTIVATION_REGISTRY_ENTRY_INVALID")
        expected = _identity("ACTIVATION_REGISTRY_ENTRY", {
            "consumption_identity": self.consumed_authorization.consumption_identity,
            "evidence_identity": self.evidence.evidence_identity,
            "event_identity": self.event.event_identity, "sequence": self.sequence,
            "previous_entry_identity": self.previous_entry_identity})
        if self.entry_identity and self.entry_identity != expected:
            raise ValueError("ACTIVATION_REGISTRY_ENTRY_IDENTITY_INVALID")
        object.__setattr__(self, "entry_identity", expected)


@dataclass(frozen=True)
class ActivationResult:
    evidence: ActivationEvidence
    consumed_authorization: ConsumedAuthorization
    registry_entry: ActivationRegistryEntry
    event: RuntimeActivationEvent
    executor_handoff: RuntimeActivationEvent

    def __post_init__(self):
        for value in (self.evidence, self.consumed_authorization,
                      self.registry_entry, self.event):
            _revalidate(value)
        if self.executor_handoff is not self.event or self.registry_entry.event != self.event:
            raise ValueError("ACTIVATION_RESULT_HANDOFF_INVALID")


def validate_inputs(authorization, certificate):
    """Reconstruct identity-bearing inputs rather than trusting their fields."""
    if not isinstance(authorization, AuthoritativeRuntimeActivationAuthorization):
        raise ValueError("AUTHORIZATION_TYPE_INVALID")
    if not isinstance(certificate, AuthoritativeReleaseCertificate):
        raise ValueError("CERTIFICATE_TYPE_INVALID")
    _revalidate(authorization)
    _revalidate(certificate)
