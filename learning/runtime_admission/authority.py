"""PR278 fail-closed admission authorization; no runtime or executor invocation."""
from datetime import timedelta
from threading import RLock

from learning.deployment.contracts import _revalidate, _utc
from learning.runtime_activation import ExecutorHandoff
from .contracts import (ADMISSION_CHECKS, LIFECYCLE, AdmissionLifecycleTransition,
    AdmissionRegistryEntry, AdmissionValidation, ExecutorAdmissionAuthorization,
    RuntimeAdmissionAuthorization, RuntimeAdmissionEvidence,
    RuntimeAdmissionGovernanceBundle, RuntimeAdmissionResult)
from .registry import RuntimeAdmissionRegistry

class RuntimeAdmissionError(ValueError):
    def __init__(self,reason,evidence=None):super().__init__(reason);self.evidence=evidence

class RuntimeAdmissionAuthority:
    """Authenticates and authorizes admission only; never invokes the recipient."""
    def __init__(self,registry=None):
        self.registry=RuntimeAdmissionRegistry() if registry is None else registry
        _revalidate(self.registry);self._lock=RLock()

    def authorize(self,bundle:RuntimeAdmissionGovernanceBundle):
        with self._lock:
            try:_revalidate(bundle)
            except (AttributeError,TypeError,ValueError) as exc:raise RuntimeAdmissionError("ADMISSION_INPUT_INVALID") from exc
            if bundle.expected_release_registry_identity!=bundle.release_registry.registry_identity:
                raise RuntimeAdmissionError("RELEASE_REGISTRY_CONFLICT")
            if bundle.expected_activation_registry_identity!=bundle.activation_registry.registry_identity:
                raise RuntimeAdmissionError("ACTIVATION_REGISTRY_CONFLICT")
            if (bundle.admission_registry.registry_identity!=self.registry.registry_identity or
                bundle.expected_admission_registry_identity!=self.registry.registry_identity):
                raise RuntimeAdmissionError("ADMISSION_REGISTRY_CONFLICT")
            h,ar,ae,rr,re,p=(bundle.executor_handoff,bundle.activation_registry,
                bundle.activation_registry_entry,bundle.release_registry,bundle.release_registry_entry,
                bundle.executor_admission_policy)
            try:
                rebuilt=ExecutorHandoff(**{x:getattr(h,x) for x in h.__dataclass_fields__ if x!="handoff_identity"})
                rr_copy=type(rr)(**{x:getattr(rr,x) for x in rr.__dataclass_fields__})
                ar_copy=type(ar)(**{x:getattr(ar,x) for x in ar.__dataclass_fields__})
            except (AttributeError,TypeError,ValueError):rebuilt=rr_copy=ar_copy=None
            decision=re.decision;certificate=decision.certificate;manifest=decision.release_manifest
            authorization=ae.consumed_authorization.authorization
            release_members=[x for x in rr.entries if x.entry_identity==re.entry_identity and x==re]
            activation_members=[x for x in ar.entries if x.entry_identity==ae.entry_identity and x==ae]
            release_superseded=(re in rr.entries and any(
                x.decision.certificate.target_environment_identity==certificate.target_environment_identity and
                x.decision.certificate.runtime_contract_identity==certificate.runtime_contract_identity and
                x.decision.certificate.executor_identity==certificate.executor_identity and
                x.decision.certificate.activation_generation>certificate.activation_generation
                for x in rr.entries[rr.entries.index(re)+1:]))
            release_revoked=(any(x.certificate_identity==certificate.certificate_identity for x in rr.certificate_revocations)
                or any(x.authorization_identity==authorization.authorization_identity for x in rr.activation_revocations)
                or any(x.certificate_identity==certificate.certificate_identity for x in rr.rollback_authorizations))
            local_revoked=ar.is_revoked(authorization.authorization_identity,bundle.admitted_at)
            age=(_utc(bundle.admitted_at)-_utc(h.handed_off_at)).total_seconds()
            effective_binding=(decision.runtime_activation_authorization==authorization and decision.certificate==certificate
                and decision.release_manifest==manifest and ae.handoff==h and
                h.release_registry_entry_identity==re.entry_identity)
            checks={
              "handoff_identity_integrity":rebuilt==h,
              "release_registry_integrity":rr_copy==rr,
              "release_registry_membership":len(release_members)==1,
              "release_effectiveness":len(release_members)==1 and effective_binding and not release_revoked and not release_superseded,
              "activation_registry_integrity":ar_copy==ar,
              "activation_registry_membership":len(activation_members)==1,
              "activation_effectiveness":len(activation_members)==1 and effective_binding and not local_revoked,
              "activation_evidence":ae.evidence.accepted and ae.consumed_authorization.evidence_identity==ae.evidence.evidence_identity,
              "authorization_lineage":h.authorization_identity==authorization.authorization_identity,
              "certificate_lineage":h.certificate_identity==certificate.certificate_identity==authorization.certificate_identity,
              "release_manifest_lineage":h.release_manifest_identity==manifest.manifest_identity,
              "artifact_lineage":h.artifact_identity==authorization.artifact_identity==certificate.artifact_identity==manifest.artifact_identity,
              "runtime_contract_lineage":h.runtime_contract_identity==authorization.runtime_contract_identity==certificate.runtime_contract_identity==manifest.runtime_contract_identity,
              "environment_lineage":h.target_environment_identity==authorization.target_environment_identity==certificate.target_environment_identity==manifest.target_environment_identity,
              "runtime_lineage":h.runtime_instance_identity==authorization.runtime_instance_identity==certificate.runtime_instance_identity==manifest.runtime_instance_identity and h.activation_generation==authorization.activation_generation==certificate.activation_generation==manifest.activation_generation,
              "executor_policy":p.permits(h.executor_identity,h.executor_version) and h.executor_identity==authorization.executor_identity==certificate.executor_identity==manifest.executor_identity and h.executor_version==authorization.executor_version==certificate.executor_version==manifest.executor_version,
              "lifecycle_lineage":tuple((x.from_state,x.to_state) for x in ae.transitions)==(("AUTHORIZED","VALIDATED"),("VALIDATED","CONSUMED"),("CONSUMED","RECORDED"),("RECORDED","HANDOFF"),("HANDOFF","EXECUTOR")),
              "event_lineage":ae.event.handoff_identity==h.handoff_identity and ae.event.consumption_identity==ae.consumed_authorization.consumption_identity,
              "handoff_freshness":0<=age<=p.maximum_handoff_age_seconds,
              "single_admission":not self.registry.contains(h.handoff_identity,h.runtime_instance_identity,h.activation_generation)}
            validations=tuple(AdmissionValidation(x,bool(checks[x]),"VALIDATED" if checks[x] else "REJECTED") for x in ADMISSION_CHECKS)
            evidence=RuntimeAdmissionEvidence(bundle.bundle_identity,rr.registry_identity,re.entry_identity,
                ar.registry_identity,ae.entry_identity,h.handoff_identity,h.authorization_identity,
                h.certificate_identity,h.release_manifest_identity,h.artifact_identity,
                h.runtime_contract_identity,h.target_environment_identity,h.runtime_instance_identity,
                h.executor_identity,h.executor_version,h.activation_generation,p.policy_identity,
                validations,bundle.admitted_at,all(checks.values()))
            if not evidence.accepted:
                self.registry=self.registry.reject(evidence,bundle.expected_admission_registry_identity)
                failed=next(x.check for x in validations if not x.passed)
                raise RuntimeAdmissionError("ADMISSION_VALIDATION_FAILED:"+failed.upper(),evidence)
            valid_until=(_utc(bundle.admitted_at)+timedelta(seconds=p.admission_validity_seconds)).isoformat().replace("+00:00","Z")
            admission=RuntimeAdmissionAuthorization(h.handoff_identity,h.runtime_instance_identity,
                h.executor_identity,h.executor_version,h.activation_generation,evidence.evidence_identity,
                p.policy_identity,bundle.admitted_at,valid_until)
            executor_authorization=ExecutorAdmissionAuthorization(admission.authorization_identity,
                h.handoff_identity,h.executor_identity,h.executor_version,h.runtime_instance_identity,
                h.activation_generation,bundle.admitted_at,valid_until)
            transitions=[]
            for i,(old,new) in enumerate(LIFECYCLE):transitions.append(AdmissionLifecycleTransition(
                h.handoff_identity,old,new,bundle.admitted_at,i+1,None if i==0 else transitions[-1].transition_identity))
            entry=AdmissionRegistryEntry(admission,evidence,executor_authorization,tuple(transitions),
                len(self.registry.entries)+1,None if not self.registry.entries else self.registry.entries[-1].entry_identity)
            self.registry=self.registry.append(entry,bundle.expected_admission_registry_identity)
            return RuntimeAdmissionResult(evidence,admission,entry,executor_authorization)
    admit=authorize
    consume=authorize
