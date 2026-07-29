"""PR278 admission-only authority; never invokes runtime or executor code."""
from threading import RLock

from learning.deployment.contracts import _revalidate, _utc
from learning.runtime_activation import ExecutorHandoff
from .contracts import (ADMISSION_CHECKS, AdmissionRegistryEntry, AdmissionValidation,
    ExecutorAuthorityTransfer, RuntimeAdmission, RuntimeAdmissionEvidence,
    RuntimeAdmissionRequest, RuntimeAdmissionResult, V27_EXECUTOR_IDENTITY,
    V27_EXECUTOR_VERSION)
from .registry import RuntimeAdmissionRegistry


class RuntimeAdmissionError(ValueError):
    def __init__(self, reason, evidence=None):
        super().__init__(reason); self.evidence = evidence


class RuntimeAdmissionAuthority:
    """Authenticates one PR277 handoff and records one admission atomically."""
    def __init__(self, registry=None):
        self.registry = RuntimeAdmissionRegistry() if registry is None else registry
        _revalidate(self.registry)
        self._lock = RLock()

    def admit(self, request: RuntimeAdmissionRequest):
        with self._lock:
            try: _revalidate(request)
            except (AttributeError, TypeError, ValueError) as exc:
                raise RuntimeAdmissionError("ADMISSION_INPUT_INVALID") from exc
            if (request.admission_registry.registry_identity != self.registry.registry_identity
                    or request.expected_admission_registry_identity != self.registry.registry_identity):
                raise RuntimeAdmissionError("ADMISSION_REGISTRY_CONFLICT")
            handoff, activation_registry, entry = (request.executor_handoff,
                request.activation_registry, request.activation_registry_entry)
            try:
                rebuilt = ExecutorHandoff(**{x: getattr(handoff, x)
                    for x in handoff.__dataclass_fields__ if x != "handoff_identity"})
                registry_copy = type(activation_registry)(**{x: getattr(activation_registry, x)
                    for x in activation_registry.__dataclass_fields__})
                entry_copy = type(entry)(**{x: getattr(entry, x)
                    for x in entry.__dataclass_fields__})
                index = activation_registry.entries.index(entry) if entry in activation_registry.entries else -1
            except (AttributeError, TypeError, ValueError):
                rebuilt, registry_copy, entry_copy, index = None, None, None, -1
            consumed = getattr(entry_copy, "consumed_authorization", None)
            authorization = getattr(consumed, "authorization", None)
            evidence = getattr(entry_copy, "evidence", None)
            event = getattr(entry_copy, "event", None)
            transitions = getattr(entry_copy, "transitions", ())
            checks = {
                "handoff_identity_integrity": rebuilt == handoff,
                "activation_registry_integrity": registry_copy == activation_registry,
                "activation_registry_membership": index >= 0 and
                    sum(x.entry_identity == entry.entry_identity for x in activation_registry.entries) == 1,
                "activation_evidence": bool(evidence and evidence.accepted and
                    evidence.evidence_identity == getattr(consumed, "evidence_identity", None)),
                "authorization_lineage": bool(authorization and handoff.authorization_identity ==
                    authorization.authorization_identity),
                "certificate_lineage": bool(authorization and handoff.certificate_identity ==
                    authorization.certificate_identity),
                "release_manifest_lineage": bool(entry_copy and entry_copy.handoff.release_manifest_identity ==
                    handoff.release_manifest_identity),
                "runtime_lineage": bool(authorization and handoff.runtime_instance_identity ==
                    authorization.runtime_instance_identity and handoff.activation_generation ==
                    authorization.activation_generation and
                    _utc(handoff.handed_off_at) <= _utc(request.admitted_at)),
                "executor_lineage": bool(authorization and handoff.executor_identity ==
                    authorization.executor_identity == V27_EXECUTOR_IDENTITY and
                    handoff.executor_version == authorization.executor_version == V27_EXECUTOR_VERSION),
                "lifecycle_lineage": tuple((x.from_state, x.to_state) for x in transitions) ==
                    (("AUTHORIZED","VALIDATED"),("VALIDATED","CONSUMED"),("CONSUMED","RECORDED"),
                     ("RECORDED","HANDOFF"),("HANDOFF","EXECUTOR")),
                "event_lineage": bool(event and event.handoff_identity == handoff.handoff_identity and
                    event.consumption_identity == getattr(consumed, "consumption_identity", None)),
                "single_admission": not self.registry.contains(handoff.handoff_identity,
                    handoff.runtime_instance_identity),
            }
            validations = tuple(AdmissionValidation(name, bool(checks[name]),
                "VALIDATED" if checks[name] else "REJECTED") for name in ADMISSION_CHECKS)
            admission_evidence = RuntimeAdmissionEvidence(request.request_identity,
                handoff.handoff_identity, activation_registry.registry_identity,
                entry.entry_identity, validations, request.admitted_at, all(checks.values()))
            if not admission_evidence.accepted:
                self.registry = self.registry.reject(admission_evidence,
                    request.expected_admission_registry_identity)
                failed = next(x.check for x in validations if not x.passed)
                raise RuntimeAdmissionError("ADMISSION_VALIDATION_FAILED:" + failed.upper(),
                                            admission_evidence)
            admission = RuntimeAdmission(handoff.handoff_identity,
                handoff.runtime_instance_identity, handoff.executor_identity,
                handoff.executor_version, handoff.activation_generation,
                admission_evidence.evidence_identity, request.admitted_at)
            transfer = ExecutorAuthorityTransfer(admission.admission_identity,
                handoff.handoff_identity, handoff.executor_identity, handoff.executor_version,
                handoff.runtime_instance_identity, request.admitted_at)
            registry_entry = AdmissionRegistryEntry(admission, admission_evidence, transfer,
                len(self.registry.entries) + 1,
                None if not self.registry.entries else self.registry.entries[-1].entry_identity)
            self.registry = self.registry.append(registry_entry,
                request.expected_admission_registry_identity)
            return RuntimeAdmissionResult(admission_evidence, admission, registry_entry, transfer)

    consume = admit
