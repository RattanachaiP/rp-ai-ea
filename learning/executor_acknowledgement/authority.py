"""PR279 fail-closed executor acceptance; never starts or invokes runtime code."""
from threading import RLock

from learning.deployment.contracts import _revalidate, _utc
from learning.runtime_admission import RuntimeAdmissionAuthorization
from .contracts import (ACKNOWLEDGEMENT_CHECKS, LIFECYCLE, AcknowledgementValidation,
    ExecutionReadinessAuthorization, ExecutorAcknowledgement,
    ExecutorAcknowledgementGovernanceBundle, ExecutorAcknowledgementRegistryEntry,
    ExecutorAcknowledgementResult, ExecutorLifecycleRecord, ExecutorReadinessEvidence)
from .registry import ExecutorAcknowledgementRegistry


class ExecutorAcknowledgementError(ValueError):
    def __init__(self, reason, evidence=None): super().__init__(reason); self.evidence=evidence


class ExecutorAcknowledgementAuthority:
    """Verifies executor acceptance only and emits immutable readiness evidence."""
    def __init__(self, registry=None):
        self.registry=ExecutorAcknowledgementRegistry() if registry is None else registry
        _revalidate(self.registry); self._lock=RLock()

    def acknowledge(self,bundle:ExecutorAcknowledgementGovernanceBundle):
        with self._lock:
            try: _revalidate(bundle)
            except (AttributeError,TypeError,ValueError) as exc: raise ExecutorAcknowledgementError("ACKNOWLEDGEMENT_INPUT_INVALID") from exc
            if bundle.expected_admission_registry_identity!=bundle.admission_registry.registry_identity:
                raise ExecutorAcknowledgementError("ADMISSION_REGISTRY_CONFLICT")
            if (bundle.acknowledgement_registry.registry_identity!=self.registry.registry_identity or
                    bundle.expected_acknowledgement_registry_identity!=self.registry.registry_identity):
                raise ExecutorAcknowledgementError("ACKNOWLEDGEMENT_REGISTRY_CONFLICT")
            a,e,ar=bundle.admission_authorization,bundle.runtime_admission_evidence,bundle.admission_registry
            try: rebuilt=RuntimeAdmissionAuthorization(**{x:getattr(a,x) for x in a.__dataclass_fields__ if x!="authorization_identity"})
            except (AttributeError,TypeError,ValueError): rebuilt=None
            members=[x for x in ar.entries if x.admission_authorization.authorization_identity==a.authorization_identity and x.admission_authorization==a]
            member=members[0] if len(members)==1 else None
            evidence_bound=(member is not None and member.evidence==e and a.evidence_identity==e.evidence_identity and e.accepted)
            now=_utc(bundle.acknowledged_at)
            checks={
                "admission_authorization_integrity":rebuilt==a,
                "authorization_validity_window":_utc(a.authorized_at)<=now<_utc(a.valid_until),
                "executor_identity":bundle.executor_identity==a.executor_identity==e.executor_identity,
                "executor_version":bundle.executor_version==a.executor_version==e.executor_version,
                "runtime_instance_identity":bundle.runtime_instance_identity==a.runtime_instance_identity==e.runtime_instance_identity,
                "activation_generation":a.activation_generation==e.activation_generation,
                "runtime_contract":bool(e.runtime_contract_identity),
                "target_environment":bool(e.target_environment_identity),
                "admission_registry_membership":len(members)==1 and evidence_bound,
                "replay_protection":not self.registry.contains(a.authorization_identity,a.runtime_instance_identity,a.activation_generation),
                "revocation_status":not self.registry.is_revoked(a.authorization_identity,bundle.acknowledged_at),
                "lifecycle_consistency":member is not None and tuple((x.from_state,x.to_state) for x in member.transitions)==(("REQUESTED","VALIDATED"),("VALIDATED","ADMISSION_AUTHORIZED"),("ADMISSION_AUTHORIZED","RECORDED")),
            }
            validations=tuple(AcknowledgementValidation(x,bool(checks[x]),"VALIDATED" if checks[x] else "REJECTED") for x in ACKNOWLEDGEMENT_CHECKS)
            readiness=ExecutorReadinessEvidence(bundle.bundle_identity,a.authorization_identity,e.evidence_identity,
                a.runtime_instance_identity,a.executor_identity,a.executor_version,a.activation_generation,
                e.runtime_contract_identity,e.target_environment_identity,validations,bundle.acknowledged_at,all(checks.values()))
            if not readiness.accepted:
                self.registry=self.registry.reject(readiness,bundle.expected_acknowledgement_registry_identity)
                failed=next(x.check for x in validations if not x.passed)
                raise ExecutorAcknowledgementError("ACKNOWLEDGEMENT_VALIDATION_FAILED:"+failed.upper(),readiness)
            acknowledgement=ExecutorAcknowledgement(a.authorization_identity,readiness.evidence_identity,
                a.runtime_instance_identity,a.executor_identity,a.executor_version,a.activation_generation,bundle.acknowledged_at)
            authorization=ExecutionReadinessAuthorization(acknowledgement.acknowledgement_identity,
                readiness.evidence_identity,a.authorization_identity,a.runtime_instance_identity,
                a.executor_identity,a.executor_version,a.activation_generation,bundle.acknowledged_at)
            lifecycle=[]
            for i,(old,new) in enumerate(LIFECYCLE): lifecycle.append(ExecutorLifecycleRecord(
                acknowledgement.acknowledgement_identity,old,new,bundle.acknowledged_at,i+1,
                None if i==0 else lifecycle[-1].record_identity))
            entry=ExecutorAcknowledgementRegistryEntry(acknowledgement,readiness,authorization,
                tuple(lifecycle),len(self.registry.entries)+1,
                None if not self.registry.entries else self.registry.entries[-1].entry_identity)
            self.registry=self.registry.append(entry,bundle.expected_acknowledgement_registry_identity)
            return ExecutorAcknowledgementResult(acknowledgement,readiness,entry,authorization)

    accept=acknowledge
    verify=acknowledge
