"""Append-only production release certificate registry and lifecycle."""
from dataclasses import dataclass
from learning.deployment.contracts import _revalidate,_utc
from learning.promotion.identity import identity_for
from .governance import (ActivationRevocation,AuthoritativeReleaseDecision,
    EmergencyRollbackAuthorization,ReleaseCertificateRevocation)

@dataclass(frozen=True)
class ReleaseRegistryEntry:
    decision:AuthoritativeReleaseDecision; sequence:int; previous_entry_identity:str|None
    lifecycle_state:str="REGISTERED"; entry_identity:str=""
    def __post_init__(self):
        _revalidate(self.decision)
        if self.decision.certificate is None or self.lifecycle_state not in ("REGISTERED","ACTIVATION_PENDING","ACTIVATION_CONSUMED","ACTIVE","REVOKED","ROLLED_BACK"): raise ValueError("RELEASE_REGISTRY_ENTRY_INVALID")
        expected=identity_for("RELEASE_REGISTRY_ENTRY",{"decision_identity":self.decision.decision_identity,"sequence":self.sequence,"previous_entry_identity":self.previous_entry_identity,"lifecycle_state":self.lifecycle_state})
        if self.entry_identity and self.entry_identity!=expected: raise ValueError("RELEASE_REGISTRY_ENTRY_IDENTITY_INVALID")
        object.__setattr__(self,"entry_identity",expected)
    @property
    def activation_scope(self):
        c=self.decision.certificate
        return (c.release_request_identity,c.deployment_manifest_identity,c.artifact_identity,c.target_environment_identity,
            c.runtime_contract_identity,c.release_policy_identity,c.executor_identity,c.activation_generation)

@dataclass(frozen=True)
class ReleaseRegistry:
    entries:tuple[ReleaseRegistryEntry,...]=(); certificate_revocations:tuple[ReleaseCertificateRevocation,...]=()
    activation_revocations:tuple[ActivationRevocation,...]=(); rollback_authorizations:tuple[EmergencyRollbackAuthorization,...]=()
    registry_identity:str=""
    def __post_init__(self):
        entries=tuple(self.entries); object.__setattr__(self,"entries",entries)
        for i,e in enumerate(entries):
            _revalidate(e)
            if e.sequence!=i+1 or e.previous_entry_identity!=(None if i==0 else entries[i-1].entry_identity): raise ValueError("RELEASE_REGISTRY_LINEAGE_INVALID")
        scopes=[e.activation_scope for e in entries]
        if len(scopes)!=len(set(scopes)): raise ValueError("MULTIPLE_RELEASE_CERTIFICATES_FOR_ACTIVATION")
        for collection in (self.certificate_revocations,self.activation_revocations,self.rollback_authorizations):
            for record in collection:_revalidate(record)
        expected=identity_for("RELEASE_REGISTRY",{"entries":tuple(e.entry_identity for e in entries),"certificate_revocations":tuple(x.revocation_identity for x in self.certificate_revocations),"activation_revocations":tuple(x.revocation_identity for x in self.activation_revocations),"rollbacks":tuple(x.rollback_authorization_identity for x in self.rollback_authorizations)})
        if self.registry_identity and self.registry_identity!=expected: raise ValueError("RELEASE_REGISTRY_IDENTITY_INVALID")
        object.__setattr__(self,"registry_identity",expected)
    def append(self,decision):
        _revalidate(decision)
        if decision.certificate is None: raise ValueError("REJECTED_RELEASE_NOT_REGISTRABLE")
        if any(e.decision.decision_identity==decision.decision_identity for e in self.entries): return self
        probe=ReleaseRegistryEntry(decision,len(self.entries)+1,None if not self.entries else self.entries[-1].entry_identity)
        if any(e.activation_scope==probe.activation_scope for e in self.entries): raise ValueError("MULTIPLE_RELEASE_CERTIFICATES_FOR_ACTIVATION")
        return ReleaseRegistry(self.entries+(probe,),self.certificate_revocations,self.activation_revocations,self.rollback_authorizations)
    def revoke_certificate(self,record):
        _revalidate(record)
        if not any(e.decision.certificate.certificate_identity==record.certificate_identity for e in self.entries): raise ValueError("CERTIFICATE_NOT_REGISTERED")
        if any(x.certificate_identity==record.certificate_identity for x in self.certificate_revocations): raise ValueError("CERTIFICATE_REVOCATION_REPLAY")
        return ReleaseRegistry(self.entries,self.certificate_revocations+(record,),self.activation_revocations,self.rollback_authorizations)
    def revoke_activation(self,record):
        _revalidate(record)
        if not any(e.decision.runtime_activation_authorization.authorization_identity==record.authorization_identity for e in self.entries): raise ValueError("ACTIVATION_NOT_REGISTERED")
        return ReleaseRegistry(self.entries,self.certificate_revocations,self.activation_revocations+(record,),self.rollback_authorizations)
    def authorize_rollback(self,record):
        _revalidate(record)
        if not any(e.decision.certificate.certificate_identity==record.certificate_identity and e.decision.certificate.rollback_manifest_identity==record.rollback_manifest_identity for e in self.entries): raise ValueError("ROLLBACK_BINDING_INVALID")
        return ReleaseRegistry(self.entries,self.certificate_revocations,self.activation_revocations,self.rollback_authorizations+(record,))
