"""Fail-closed, non-executing Runtime Activation Authority."""
from threading import RLock
from learning.deployment.contracts import _revalidate,_utc
from .contracts import (ACTIVATION_CHECKS,ActivationEvidence,ActivationLifecycleTransition,
    ActivationRegistryEntry,ActivationResult,ActivationValidation,ConsumedAuthorization,
    ExecutorHandoff,RuntimeActivationEvent,RuntimeActivationGovernanceBundle)
from .registry import ActivationRegistry

class RuntimeActivationError(ValueError):
    def __init__(self,reason,evidence=None): super().__init__(reason); self.evidence=evidence

class RuntimeActivationAuthority:
    """Validates and records data; never invokes a runtime, broker, or executor."""
    def __init__(self,registry=None):
        self.registry=ActivationRegistry() if registry is None else registry
        _revalidate(self.registry); self._lock=RLock()

    def activate(self,bundle:RuntimeActivationGovernanceBundle):
        with self._lock:
            try:_revalidate(bundle)
            except (AttributeError,TypeError,ValueError) as exc: raise RuntimeActivationError("ACTIVATION_INPUT_INVALID") from exc
            # Authority state, bundle snapshot, and caller expectation form one CAS boundary.
            if bundle.activation_registry.registry_identity!=self.registry.registry_identity or bundle.expected_registry_identity!=self.registry.registry_identity:
                raise RuntimeActivationError("ACTIVATION_REGISTRY_CONFLICT")
            a,c,m,d,e,r,t=(bundle.authorization,bundle.release_certificate,bundle.release_manifest,
                bundle.release_decision,bundle.release_registry_entry,bundle.release_registry,bundle.target_runtime)
            registered=[x for x in r.entries if x.entry_identity==e.entry_identity and x==e and x.decision==d]
            effective=(len(registered)==1 and d.certificate==c and d.release_manifest==m and
                d.runtime_activation_authorization==a and e.decision.certificate==c)
            certificate_revoked=any(x.certificate_identity==c.certificate_identity for x in r.certificate_revocations)
            activation_revoked=any(x.authorization_identity==a.authorization_identity for x in r.activation_revocations)
            rolled_back=any(x.certificate_identity==c.certificate_identity for x in r.rollback_authorizations)
            index=r.entries.index(e) if e in r.entries else -1
            superseded=index>=0 and any(x.decision.certificate.runtime_instance_identity==c.runtime_instance_identity and
                x.decision.certificate.executor_identity==c.executor_identity for x in r.entries[index+1:])
            rebuilt=type(a)(**{x:getattr(a,x) for x in a.__dataclass_fields__ if x!="authorization_identity"})
            checks={
              "authorization_identity_integrity":rebuilt.authorization_identity==a.authorization_identity,
              "certificate_identity":a.certificate_identity==c.certificate_identity==m.certificate_identity,
              "release_registry_effectiveness":effective and not superseded,
              "runtime_instance_identity":a.runtime_instance_identity==c.runtime_instance_identity==m.runtime_instance_identity==t.instance_identity,
              "executor_identity":a.executor_identity==c.executor_identity==m.executor_identity==t.executor_identity,
              "executor_version":a.executor_version==c.executor_version==m.executor_version==t.executor_version,
              "activation_generation":a.activation_generation==c.activation_generation==m.activation_generation==t.activation_generation,
              "runtime_contract_identity":a.runtime_contract_identity==c.runtime_contract_identity==m.runtime_contract_identity==t.runtime_contract_identity,
              "target_environment_identity":a.target_environment_identity==c.target_environment_identity==m.target_environment_identity==t.target_environment_identity,
              "artifact_identity":a.artifact_identity==c.artifact_identity==m.artifact_identity,
              "validity_window":_utc(a.valid_from)<=_utc(bundle.activated_at)<_utc(a.valid_until),
              "single_use_status":not self.registry.is_consumed(a.authorization_identity),
              "revocation_status":not(certificate_revoked or activation_revoked or rolled_back or self.registry.is_revoked(a.authorization_identity,bundle.activated_at)),
              "registry_identity":True}
            validations=tuple(ActivationValidation(x,bool(checks[x]),"VALIDATED" if checks[x] else "REJECTED") for x in ACTIVATION_CHECKS)
            evidence=ActivationEvidence(bundle.bundle_identity,validations,bundle.activated_at,all(checks.values()))
            if not evidence.accepted:
                self.registry=self.registry.reject(evidence,bundle.expected_registry_identity)
                failed=next(x.check for x in validations if not x.passed)
                raise RuntimeActivationError("ACTIVATION_VALIDATION_FAILED:"+failed.upper(),evidence)
            consumed=ConsumedAuthorization(a,bundle.activated_at,evidence.evidence_identity)
            handoff=ExecutorHandoff(a.authorization_identity,c.certificate_identity,m.manifest_identity,
                a.artifact_identity,a.runtime_contract_identity,a.target_environment_identity,a.executor_identity,
                a.executor_version,a.runtime_instance_identity,a.activation_generation,e.entry_identity,bundle.activated_at)
            event=RuntimeActivationEvent(consumed.consumption_identity,handoff.handoff_identity,bundle.activated_at)
            pairs=(("AUTHORIZED","VALIDATED"),("VALIDATED","CONSUMED"),("CONSUMED","RECORDED"),("RECORDED","HANDOFF"),("HANDOFF","EXECUTOR"))
            transitions=[]
            for i,(old,new) in enumerate(pairs): transitions.append(ActivationLifecycleTransition(a.authorization_identity,old,new,bundle.activated_at,i+1,None if i==0 else transitions[-1].transition_identity))
            entry=ActivationRegistryEntry(consumed,evidence,handoff,event,tuple(transitions),len(self.registry.entries)+1,None if not self.registry.entries else self.registry.entries[-1].entry_identity)
            self.registry=self.registry.append(entry,bundle.expected_registry_identity)
            return ActivationResult(evidence,consumed,entry,event,handoff)
    consume=activate
