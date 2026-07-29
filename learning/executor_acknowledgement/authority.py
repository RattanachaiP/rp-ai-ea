"""PR279 authenticates executor-origin acceptance; it never invokes Runtime."""
import hashlib
import hmac
import json
from threading import RLock

from learning.deployment.contracts import _revalidate, _utc
from .contracts import (ACKNOWLEDGEMENT_CHECKS,LIFECYCLE,AcknowledgementValidation,
    ExecutorAcknowledgement,ExecutorAcknowledgementAuthorization,
    ExecutorAcknowledgementGovernanceBundle,ExecutorAcknowledgementRegistryEntry,
    ExecutorAcknowledgementResult,ExecutorAcceptanceAttestation,ExecutorLifecycleRecord,
    ExecutorReadinessEvidence)
from .registry import ExecutorAcknowledgementRegistry


class ExecutorAcknowledgementError(ValueError):
    def __init__(self,reason,evidence=None):super().__init__(reason);self.evidence=evidence


def _signature(attestation,key):
    canonical=json.dumps(attestation.signing_payload(),sort_keys=True,separators=(",",":"),ensure_ascii=True).encode()
    return hmac.new(key,canonical,hashlib.sha256).hexdigest()


class ExecutorAcknowledgementAuthority:
    """Authenticates a signed V27 attestation and records acknowledgement only."""
    def __init__(self,*,registry=None,acknowledgement_authority_identity,
            trusted_executor_keys,expected_executor_instances,
            maximum_attestation_age_seconds=30,maximum_future_skew_seconds=0):
        self.registry=ExecutorAcknowledgementRegistry() if registry is None else registry
        _revalidate(self.registry)
        if (not isinstance(acknowledgement_authority_identity,str) or not acknowledgement_authority_identity
                or not trusted_executor_keys or not expected_executor_instances
                or type(maximum_attestation_age_seconds)is not int or maximum_attestation_age_seconds<1
                or type(maximum_future_skew_seconds)is not int or maximum_future_skew_seconds<0):
            raise ValueError("ACKNOWLEDGEMENT_AUTHORITY_CONFIGURATION_INVALID")
        self.authority_identity=acknowledgement_authority_identity
        self.trusted_executor_keys=dict(trusted_executor_keys)
        self.expected_executor_instances=dict(expected_executor_instances)
        self.maximum_attestation_age_seconds=maximum_attestation_age_seconds
        self.maximum_future_skew_seconds=maximum_future_skew_seconds
        self._lock=RLock()

    def acknowledge(self,bundle:ExecutorAcknowledgementGovernanceBundle):
        with self._lock:
            try:_revalidate(bundle)
            except (AttributeError,TypeError,ValueError) as exc:raise ExecutorAcknowledgementError("ACKNOWLEDGEMENT_INPUT_INVALID") from exc
            if bundle.expected_admission_registry_identity!=bundle.admission_registry.registry_identity:
                raise ExecutorAcknowledgementError("ADMISSION_REGISTRY_CONFLICT")
            if (bundle.acknowledgement_registry.registry_identity!=self.registry.registry_identity or
                    bundle.expected_acknowledgement_registry_identity!=self.registry.registry_identity):
                raise ExecutorAcknowledgementError("ACKNOWLEDGEMENT_REGISTRY_CONFLICT")
            x,t,ar,entry=(bundle.executor_admission_authorization,bundle.executor_acceptance_attestation,
                bundle.admission_registry,bundle.admission_registry_entry)
            a,e=entry.admission_authorization,entry.evidence
            try:rebuilt=ExecutorAcceptanceAttestation(**{k:getattr(t,k) for k in t.__dataclass_fields__ if k!="attestation_identity"})
            except (AttributeError,TypeError,ValueError):rebuilt=None
            members=[item for item in ar.entries if item.entry_identity==entry.entry_identity and item==entry]
            key_id=(t.executor_identity,t.executor_version,t.executor_instance_identity)
            key=self.trusted_executor_keys.get(key_id)
            expected_session=self.expected_executor_instances.get(key_id)
            accepted,recorded=_utc(t.accepted_at),_utc(bundle.acknowledged_at)
            age=(recorded-accepted).total_seconds()
            authorization_binding=(t.executor_admission_authorization_identity==x.authorization_identity and
                t.admission_authorization_identity==a.authorization_identity and
                entry.executor_admission_authorization==x and
                x.admission_authorization_identity==a.authorization_identity and
                a.evidence_identity==e.evidence_identity and e.accepted)
            checks={
                "attestation_integrity":rebuilt==t,
                "attestation_authenticity":key is not None and hmac.compare_digest(t.signature,_signature(t,key)),
                "authorization_validity_window":_utc(x.authorized_at)<=accepted<=recorded<_utc(x.valid_until),
                "attestation_freshness":-self.maximum_future_skew_seconds<=age<=self.maximum_attestation_age_seconds,
                "executor_identity":t.executor_identity==x.executor_identity==a.executor_identity==e.executor_identity,
                "executor_version":t.executor_version==x.executor_version==a.executor_version==e.executor_version,
                "executor_instance_identity":key is not None,
                "executor_session_identity":expected_session==t.executor_session_identity,
                "runtime_instance_identity":t.runtime_instance_identity==x.runtime_instance_identity==a.runtime_instance_identity==e.runtime_instance_identity,
                "activation_generation":t.activation_generation==x.activation_generation==a.activation_generation==e.activation_generation,
                "artifact_lineage":t.artifact_identity==e.artifact_identity,
                "runtime_contract_lineage":t.runtime_contract_identity==e.runtime_contract_identity,
                "target_environment_lineage":t.target_environment_identity==e.target_environment_identity,
                "executor_policy_identity":t.executor_policy_identity==a.policy_identity,
                "acknowledgement_authority_identity":t.acknowledgement_authority_identity==self.authority_identity,
                "admission_registry_membership":len(members)==1 and authorization_binding,
                "admission_effectiveness":len(members)==1 and authorization_binding and not ar.is_revoked(a.authorization_identity,bundle.acknowledged_at),
                "attestation_replay_protection":not self.registry.contains_attestation(t.attestation_identity) and not self.registry.contains_authorization(x.authorization_identity),
                "nonce_session_replay_protection":not self.registry.contains_nonce_session(t.nonce,t.executor_instance_identity,t.executor_session_identity),
                "lifecycle_consistency":tuple((v.from_state,v.to_state) for v in entry.transitions)==(("REQUESTED","VALIDATED"),("VALIDATED","ADMISSION_AUTHORIZED"),("ADMISSION_AUTHORIZED","RECORDED")),
            }
            validations=tuple(AcknowledgementValidation(name,bool(checks[name]),"VALIDATED" if checks[name] else "REJECTED") for name in ACKNOWLEDGEMENT_CHECKS)
            evidence=ExecutorReadinessEvidence(bundle.bundle_identity,x.authorization_identity,
                t.attestation_identity,t.executor_identity,t.executor_version,t.executor_instance_identity,
                t.executor_session_identity,t.nonce,t.runtime_instance_identity,t.activation_generation,
                t.artifact_identity,t.runtime_contract_identity,t.target_environment_identity,
                t.executor_policy_identity,t.acknowledgement_authority_identity,validations,
                bundle.acknowledged_at,all(checks.values()))
            if not evidence.accepted:
                self.registry=self.registry.reject(evidence,bundle.expected_acknowledgement_registry_identity)
                failed=next(v.check for v in validations if not v.passed)
                raise ExecutorAcknowledgementError("ACKNOWLEDGEMENT_VALIDATION_FAILED:"+failed.upper(),evidence)
            acknowledgement=ExecutorAcknowledgement(x.authorization_identity,t.attestation_identity,
                evidence.evidence_identity,t.executor_identity,t.executor_version,t.executor_instance_identity,
                t.executor_session_identity,t.runtime_instance_identity,t.activation_generation,bundle.acknowledged_at)
            authorization=ExecutorAcknowledgementAuthorization(acknowledgement.acknowledgement_identity,
                evidence.evidence_identity,x.authorization_identity,t.executor_identity,t.executor_version,
                t.executor_instance_identity,t.executor_session_identity,t.runtime_instance_identity,
                t.activation_generation,bundle.acknowledged_at)
            lifecycle=[]
            for i,(old,new) in enumerate(LIFECYCLE):lifecycle.append(ExecutorLifecycleRecord(
                acknowledgement.acknowledgement_identity,old,new,bundle.acknowledged_at,i+1,
                None if i==0 else lifecycle[-1].record_identity))
            registry_entry=ExecutorAcknowledgementRegistryEntry(acknowledgement,evidence,
                authorization,tuple(lifecycle),len(self.registry.entries)+1,
                None if not self.registry.entries else self.registry.entries[-1].entry_identity)
            self.registry=self.registry.append(registry_entry,bundle.expected_acknowledgement_registry_identity)
            return ExecutorAcknowledgementResult(acknowledgement,evidence,registry_entry,authorization)

    accept=acknowledge
    verify=acknowledge
