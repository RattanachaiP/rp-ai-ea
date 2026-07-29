"""Immutable PR278 Runtime Admission contracts."""
from __future__ import annotations

from dataclasses import dataclass

from learning.deployment.contracts import _revalidate, _text, _utc
from learning.promotion.identity import identity_for
from learning.runtime_activation import ExecutorHandoff

ADMISSION_SCHEMA_VERSION = "PR278.RUNTIME_ADMISSION.1.0"
V27_EXECUTOR_IDENTITY = "V27_PRODUCTION_EXECUTOR"
V27_EXECUTOR_VERSION = "27.1"
ADMISSION_CHECKS = (
    "handoff_identity_integrity", "activation_registry_integrity",
    "activation_registry_membership", "activation_evidence", "authorization_lineage",
    "certificate_lineage", "release_manifest_lineage", "runtime_lineage",
    "executor_lineage", "lifecycle_lineage", "event_lineage", "single_admission",
)


def _id(kind, payload):
    return identity_for(kind, payload)


@dataclass(frozen=True)
class RuntimeAdmissionRequest:
    """The PR277 handoff plus read-only proofs needed to authenticate its origin."""
    executor_handoff: ExecutorHandoff
    activation_registry: object
    activation_registry_entry: object
    admission_registry: object
    expected_admission_registry_identity: str
    admitted_at: str
    request_identity: str = ""

    def __post_init__(self):
        for value in (self.executor_handoff, self.activation_registry,
                      self.activation_registry_entry, self.admission_registry):
            _revalidate(value)
        _utc(self.admitted_at)
        if not _text(self.expected_admission_registry_identity):
            raise ValueError("EXPECTED_ADMISSION_REGISTRY_IDENTITY_INVALID")
        payload = {
            "handoff": self.executor_handoff.handoff_identity,
            "activation_registry": self.activation_registry.registry_identity,
            "activation_entry": self.activation_registry_entry.entry_identity,
            "admission_registry": self.admission_registry.registry_identity,
            "expected_admission_registry": self.expected_admission_registry_identity,
            "admitted_at": self.admitted_at,
        }
        expected = _id("RUNTIME_ADMISSION_REQUEST", payload)
        if self.request_identity and self.request_identity != expected:
            raise ValueError("RUNTIME_ADMISSION_REQUEST_IDENTITY_INVALID")
        object.__setattr__(self, "request_identity", expected)


@dataclass(frozen=True)
class AdmissionValidation:
    check: str
    passed: bool
    reason: str
    def __post_init__(self):
        if self.check not in ADMISSION_CHECKS or type(self.passed) is not bool or not _text(self.reason):
            raise ValueError("ADMISSION_VALIDATION_INVALID")


@dataclass(frozen=True)
class RuntimeAdmissionEvidence:
    request_identity: str
    handoff_identity: str
    activation_registry_identity: str
    activation_registry_entry_identity: str
    validations: tuple[AdmissionValidation, ...]
    recorded_at: str
    accepted: bool
    evidence_identity: str = ""
    def __post_init__(self):
        _utc(self.recorded_at)
        values = tuple(self.validations)
        object.__setattr__(self, "validations", values)
        if (not all(_text(getattr(self, field)) for field in (
                "request_identity", "handoff_identity", "activation_registry_identity",
                "activation_registry_entry_identity"))
                or tuple(x.check for x in values) != ADMISSION_CHECKS
                or self.accepted != all(x.passed for x in values)):
            raise ValueError("RUNTIME_ADMISSION_EVIDENCE_INVALID")
        expected = _id("RUNTIME_ADMISSION_EVIDENCE", {
            "request": self.request_identity, "handoff": self.handoff_identity,
            "activation_registry": self.activation_registry_identity,
            "activation_entry": self.activation_registry_entry_identity,
            "validations": tuple((x.check, x.passed, x.reason) for x in values),
            "recorded_at": self.recorded_at, "accepted": self.accepted,
        })
        if self.evidence_identity and self.evidence_identity != expected:
            raise ValueError("RUNTIME_ADMISSION_EVIDENCE_IDENTITY_INVALID")
        object.__setattr__(self, "evidence_identity", expected)


@dataclass(frozen=True)
class RuntimeAdmission:
    """One runtime-instance admission; it is not an order or broker capability."""
    handoff_identity: str
    runtime_instance_identity: str
    executor_identity: str
    executor_version: str
    activation_generation: int
    evidence_identity: str
    admitted_at: str
    admission_identity: str = ""
    runtime_admitted: bool = True
    broker_access_authorized: bool = False
    trade_execution_authorized: bool = False
    runtime_modification_authorized: bool = False
    strategy_generation_authorized: bool = False
    ai_training_authorized: bool = False
    ai_evaluation_authorized: bool = False
    def __post_init__(self):
        _utc(self.admitted_at)
        flags = (self.runtime_admitted, self.broker_access_authorized,
                 self.trade_execution_authorized, self.runtime_modification_authorized,
                 self.strategy_generation_authorized, self.ai_training_authorized,
                 self.ai_evaluation_authorized)
        if (not all(_text(getattr(self, x)) for x in ("handoff_identity",
                "runtime_instance_identity", "executor_identity", "executor_version",
                "evidence_identity")) or type(self.activation_generation) is not int
                or flags != (True, False, False, False, False, False, False)):
            raise ValueError("RUNTIME_ADMISSION_INVALID")
        expected = _id("RUNTIME_ADMISSION", {k: v for k, v in self.__dict__.items()
                                               if k != "admission_identity"})
        if self.admission_identity and self.admission_identity != expected:
            raise ValueError("RUNTIME_ADMISSION_IDENTITY_INVALID")
        object.__setattr__(self, "admission_identity", expected)


@dataclass(frozen=True)
class ExecutorAuthorityTransfer:
    """Data-only transfer to the existing V27 executor; no callback is invoked."""
    admission_identity: str
    handoff_identity: str
    executor_identity: str
    executor_version: str
    runtime_instance_identity: str
    transferred_at: str
    transfer_identity: str = ""
    execution_domain_authority_transferred: bool = True
    broker_connection_performed: bool = False
    trade_execution_performed: bool = False
    def __post_init__(self):
        _utc(self.transferred_at)
        if (not all(_text(getattr(self, x)) for x in ("admission_identity",
                "handoff_identity", "executor_identity", "executor_version",
                "runtime_instance_identity"))
                or self.executor_identity != V27_EXECUTOR_IDENTITY
                or self.executor_version != V27_EXECUTOR_VERSION
                or self.execution_domain_authority_transferred is not True
                or self.broker_connection_performed or self.trade_execution_performed):
            raise ValueError("EXECUTOR_AUTHORITY_TRANSFER_INVALID")
        expected = _id("V27_EXECUTOR_AUTHORITY_TRANSFER", {k: v for k, v in self.__dict__.items()
                                                            if k != "transfer_identity"})
        if self.transfer_identity and self.transfer_identity != expected:
            raise ValueError("EXECUTOR_AUTHORITY_TRANSFER_IDENTITY_INVALID")
        object.__setattr__(self, "transfer_identity", expected)


@dataclass(frozen=True)
class AdmissionRegistryEntry:
    admission: RuntimeAdmission
    evidence: RuntimeAdmissionEvidence
    authority_transfer: ExecutorAuthorityTransfer
    sequence: int
    previous_entry_identity: str | None
    entry_identity: str = ""
    def __post_init__(self):
        for value in (self.admission, self.evidence, self.authority_transfer): _revalidate(value)
        if (self.admission.evidence_identity != self.evidence.evidence_identity
                or self.authority_transfer.admission_identity != self.admission.admission_identity
                or self.sequence < 1
                or (self.sequence == 1) != (self.previous_entry_identity is None)):
            raise ValueError("ADMISSION_REGISTRY_ENTRY_INVALID")
        expected = _id("RUNTIME_ADMISSION_REGISTRY_ENTRY", {
            "admission": self.admission.admission_identity,
            "evidence": self.evidence.evidence_identity,
            "transfer": self.authority_transfer.transfer_identity,
            "sequence": self.sequence, "previous": self.previous_entry_identity,
        })
        if self.entry_identity and self.entry_identity != expected:
            raise ValueError("ADMISSION_REGISTRY_ENTRY_IDENTITY_INVALID")
        object.__setattr__(self, "entry_identity", expected)


@dataclass(frozen=True)
class RuntimeAdmissionResult:
    evidence: RuntimeAdmissionEvidence
    admission: RuntimeAdmission
    registry_entry: AdmissionRegistryEntry
    authority_transfer: ExecutorAuthorityTransfer
    def __post_init__(self):
        if (self.registry_entry.admission != self.admission
                or self.registry_entry.evidence != self.evidence
                or self.registry_entry.authority_transfer != self.authority_transfer):
            raise ValueError("RUNTIME_ADMISSION_RESULT_BINDING_INVALID")
