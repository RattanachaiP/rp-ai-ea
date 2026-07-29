"""PR280 fail-closed startup authorization; this module performs no startup."""
from datetime import timedelta
from threading import RLock

from learning.deployment.contracts import _revalidate, _utc
from learning.promotion.identity import identity_for
from .contracts import *
from .registry import RuntimeStartupRegistry

class RuntimeStartupError(ValueError):
    def __init__(self,reason,result=None): super().__init__(reason); self.result=result

class RuntimeStartupAuthority:
    def __init__(self,registry=None):
        self.registry=RuntimeStartupRegistry() if registry is None else registry; _revalidate(self.registry); self._lock=RLock()

    @staticmethod
    def _key(contract,policy):
        return identity_for("RUNTIME_STARTUP_COMPOSITE_KEY",(contract.runtime_instance_identity,contract.executor_identity,
            contract.executor_version,contract.executor_instance_identity,contract.executor_session_identity,
            contract.activation_generation,contract.artifact_identity,policy.policy_identity,contract.contract_identity))

    def authorize(self,bundle:RuntimeStartupGovernanceBundle):
        with self._lock:
            try: _revalidate(bundle)
            except (AttributeError,TypeError,ValueError) as exc: raise RuntimeStartupError("STARTUP_INPUT_INVALID") from exc
            a,r,e,p,c=bundle.acknowledgement_authorization,bundle.acknowledgement_registry,bundle.acknowledgement_registry_entry,bundle.startup_policy,bundle.startup_contract
            now=_utc(bundle.canonical_evaluation_timestamp); recorded=_utc(a.recorded_at); age=(now-recorded).total_seconds()
            members=[x for x in r.entries if x.entry_identity==e.entry_identity and x==e]
            authorization_bound=(e.acknowledgement_authorization==a and e.acknowledgement_evidence.accepted and
                e.acknowledgement.acknowledgement_evidence_identity==e.acknowledgement_evidence.evidence_identity)
            subjects={a.authorization_identity,e.entry_identity,c.artifact_identity,c.runtime_contract_identity,
                c.runtime_instance_identity,str(c.activation_generation)}
            effective=[x for x in bundle.governance_statuses if _utc(x.effective_at)<=now]
            revoked=any(x.kind in {"REVOCATION","EMERGENCY_ROLLBACK"} and (x.subject_identity in subjects or x.subject_identity=="GLOBAL") for x in effective)
            superseded=any(x.kind=="SUPERSESSION" and x.subject_identity in subjects for x in effective)
            key=self._key(c,p)
            duplicate=any(x.decision==STARTUP_AUTHORIZED and x.composite_key==key for x in self.registry.entries)
            higher_generation=any(x.decision==STARTUP_AUTHORIZED and x.authorization and
                x.authorization.runtime_instance_identity==c.runtime_instance_identity and
                x.authorization.artifact_identity==c.artifact_identity and x.authorization.activation_generation>c.activation_generation for x in self.registry.entries)
            ack_integrity=False
            try:
                rebuilt=type(a)(**{k:getattr(a,k) for k in a.__dataclass_fields__ if k!="authorization_identity"}); ack_integrity=rebuilt==a
            except (TypeError,ValueError,AttributeError): pass
            contract_integrity=False; policy_integrity=False
            try: contract_integrity=type(c)(**{k:getattr(c,k) for k in c.__dataclass_fields__ if k!="contract_identity"})==c
            except (TypeError,ValueError,AttributeError): pass
            try: policy_integrity=type(p)(**{k:getattr(p,k) for k in p.__dataclass_fields__ if k!="policy_identity"})==p
            except (TypeError,ValueError,AttributeError): pass
            checks={
                "acknowledgement_authorization_integrity":ack_integrity,
                "acknowledgement_registry_integrity":bundle.expected_acknowledgement_registry_identity==r.registry_identity,
                "acknowledgement_registry_membership":len(members)==1 and authorization_bound,
                "acknowledgement_effectiveness":len(members)==1 and authorization_bound and not revoked and not superseded,
                "acknowledgement_validity_window":recorded<=now,
                "acknowledgement_freshness":-p.future_timestamp_skew_tolerance_seconds<=age<=p.maximum_acknowledgement_age_seconds,
                "executor_identity":a.executor_identity==c.executor_identity and c.executor_identity in p.allowed_executor_identities,
                "executor_version":a.executor_version==c.executor_version and c.executor_version in p.allowed_executor_versions,
                "executor_instance_identity":a.executor_instance_identity==c.executor_instance_identity,
                "executor_session_identity":a.executor_session_identity==c.executor_session_identity,
                "runtime_instance_identity":a.runtime_instance_identity==c.runtime_instance_identity,
                "activation_generation":a.activation_generation==c.activation_generation and c.activation_generation in p.allowed_activation_generations and not higher_generation,
                "artifact_identity":e.acknowledgement_evidence.artifact_identity==c.artifact_identity,
                "runtime_contract_identity":e.acknowledgement_evidence.runtime_contract_identity==c.runtime_contract_identity and c.runtime_contract_identity in p.allowed_runtime_contracts,
                "target_environment_identity":e.acknowledgement_evidence.target_environment_identity==c.target_environment_identity and c.target_environment_class in p.allowed_environment_classes,
                # The policy requires the contract's declared, stable configuration identity;
                # the contract separately binds the content-addressed policy.  This avoids a
                # cryptographically impossible pair of mutually recursive content digests.
                "startup_contract_integrity":contract_integrity and p.required_startup_contract_identity==c.expected_configuration_identity and c.startup_policy_identity==p.policy_identity,
                "startup_policy_compliance":policy_integrity and bundle.acknowledgement_authority_identity==p.required_acknowledgement_authority_identity,
                "revocation_status":not revoked,
                "supersession_status":not superseded,
                "registry_lineage":bundle.startup_registry.registry_identity==self.registry.registry_identity==bundle.expected_startup_registry_identity and bundle.expected_predecessor_registry_identity==self.registry.previous_registry_identity,
                "startup_generation_replay_protection":not duplicate and not higher_generation and not any(x[0]==a.authorization_identity for x in self.registry.consumed_authorizations),
                "lifecycle_consistency":tuple((x.from_state,x.to_state) for x in e.lifecycle)==(("AUTHORIZED","ACKNOWLEDGED"),("ACKNOWLEDGED","RECORDED"),("RECORDED","ACKNOWLEDGEMENT_COMPLETE"))}
            gate_results=tuple(RuntimeStartupGateResult(g,bool(checks[g]),"VALIDATED" if checks[g] else "REJECTED") for g in STARTUP_GATES)
            decision=STARTUP_AUTHORIZED if all(checks.values()) else STARTUP_REJECTED
            evidence=RuntimeStartupEvidence(bundle.bundle_identity,decision,gate_results,bundle.canonical_evaluation_timestamp)
            result_identity=identity_for("RUNTIME_STARTUP_RESULT",{"evidence":evidence.evidence_identity,"decision":decision})
            authorization=None
            if decision==STARTUP_AUTHORIZED:
                expires=(now+timedelta(seconds=p.maximum_startup_authorization_lifetime_seconds)).isoformat().replace("+00:00","Z")
                authorization=RuntimeStartupAuthorization(result_identity,evidence.evidence_identity,p.policy_identity,c.contract_identity,
                    a.authorization_identity,e.entry_identity,c.runtime_instance_identity,c.executor_identity,c.executor_version,
                    c.executor_instance_identity,c.executor_session_identity,c.activation_generation,c.artifact_identity,
                    c.runtime_contract_identity,c.target_environment_identity,bundle.canonical_evaluation_timestamp,
                    bundle.canonical_evaluation_timestamp,expires)
            flow=SUCCESS_LIFECYCLE if authorization else REJECTION_LIFECYCLE; lifecycle=[]
            for i,(old,new) in enumerate(flow): lifecycle.append(RuntimeStartupLifecycleRecord(result_identity,old,new,
                bundle.canonical_evaluation_timestamp,i+1,None if i==0 else lifecycle[-1].record_identity))
            entry=RuntimeStartupRegistryEntry(key,decision,evidence,authorization,tuple(lifecycle),len(self.registry.entries)+1,
                None if not self.registry.entries else self.registry.entries[-1].entry_identity)
            result=RuntimeStartupResult(decision,result_identity,evidence,authorization,entry)
            try: self.registry=self.registry.append(entry,bundle.expected_startup_registry_identity,bundle.expected_predecessor_registry_identity)
            except ValueError as exc: raise RuntimeStartupError(str(exc),result) from exc
            if decision==STARTUP_REJECTED:
                failed=next(x.gate for x in gate_results if not x.passed)
                raise RuntimeStartupError("STARTUP_VALIDATION_FAILED:"+failed.upper(),result)
            return result

    def consume(self,authorization_identity,consumed_at,expected_registry_identity):
        with self._lock:
            self.registry=self.registry.consume(authorization_identity,consumed_at,expected_registry_identity)
            return self.registry

    def record_status(self,status,expected_registry_identity):
        """Record explicit revocation/supersession evidence without executing anything."""
        with self._lock:
            self.registry=self.registry.apply_status(status,expected_registry_identity)
            return self.registry
