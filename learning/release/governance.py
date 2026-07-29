"""Authoritative PR276 production-release evidence chain and lifecycle records."""
from __future__ import annotations
from dataclasses import dataclass
from typing import Mapping

from learning.common.immutable import freeze, thaw
from learning.deployment import (DeploymentArtifact, DeploymentRegistry,
    DeploymentRegistryEntry, DeploymentResult, HumanApprovalRecord,
    HumanApprovalRegistry)
from learning.deployment.contracts import _hash, _revalidate, _text, _utc
from learning.promotion.identity import identity_for
from .contracts import RELEASE_GATES, ReleaseGate, ReleaseEvidence

LIFECYCLE_STATES=("AUTHORIZED","REGISTERED","ACTIVATION_PENDING","ACTIVATION_CONSUMED","ACTIVE","REVOKED","ROLLED_BACK")

def _identity(obj,kind,excluded):
    def canonical(value):
        for name in ("evidence_identity","record_identity","artifact_identity","manifest_identity",
                     "authorization_identity","certificate_identity","decision_identity","entry_identity"):
            if hasattr(value,name): return getattr(value,name)
        return thaw(value) if isinstance(value,Mapping) else value
    payload={k:canonical(v) for k,v in obj.__dict__.items() if k not in excluded}
    return identity_for(kind,payload)

@dataclass(frozen=True)
class RegistryMembershipEvidence:
    registry_identity:str; entry_identity:str; artifact_identity:str
    content_hash:str; registry_kind:str; evidence_identity:str=""
    def __post_init__(self):
        if not all(_text(getattr(self,x)) for x in ("registry_identity","entry_identity","artifact_identity","registry_kind")) or not _hash(self.content_hash): raise ValueError("ARTIFACT_REGISTRY_EVIDENCE_INVALID")
        expected=_identity(self,"ARTIFACT_REGISTRY_MEMBERSHIP",{"evidence_identity"})
        if self.evidence_identity and self.evidence_identity!=expected: raise ValueError("ARTIFACT_REGISTRY_EVIDENCE_IDENTITY_INVALID")
        object.__setattr__(self,"evidence_identity",expected)

@dataclass(frozen=True)
class RollbackArtifact:
    artifact_reference:str; content_hash:str; target_artifact_identity:str
    runtime_contract_identity:str; executor_identity:str; executor_version:str
    artifact_identity:str=""
    def __post_init__(self):
        if not all(_text(getattr(self,x)) for x in ("artifact_reference","target_artifact_identity","runtime_contract_identity","executor_identity","executor_version")) or not _hash(self.content_hash): raise ValueError("ROLLBACK_ARTIFACT_INVALID")
        expected=_identity(self,"ROLLBACK_ARTIFACT",{"artifact_identity"})
        if self.artifact_identity and self.artifact_identity!=expected: raise ValueError("ROLLBACK_ARTIFACT_IDENTITY_INVALID")
        object.__setattr__(self,"artifact_identity",expected)

@dataclass(frozen=True)
class RollbackManifest:
    rollback_artifact_identity:str; target_artifact_identity:str; target_environment_identity:str
    runtime_contract_identity:str; executor_identity:str; compatibility_evidence:Mapping[str,object]
    manifest_identity:str=""
    def __post_init__(self):
        if not all(_text(getattr(self,x)) for x in ("rollback_artifact_identity","target_artifact_identity","target_environment_identity","runtime_contract_identity","executor_identity")) or not isinstance(self.compatibility_evidence,Mapping): raise ValueError("ROLLBACK_MANIFEST_INVALID")
        required={"rollback_artifact_identity":self.rollback_artifact_identity,"target_artifact_identity":self.target_artifact_identity,"runtime_contract_identity":self.runtime_contract_identity,"executor_identity":self.executor_identity}
        if any(self.compatibility_evidence.get(k)!=v for k,v in required.items()): raise ValueError("ROLLBACK_COMPATIBILITY_INVALID")
        object.__setattr__(self,"compatibility_evidence",freeze(dict(self.compatibility_evidence)))
        expected=_identity(self,"ROLLBACK_MANIFEST",{"manifest_identity"})
        if self.manifest_identity and self.manifest_identity!=expected: raise ValueError("ROLLBACK_MANIFEST_IDENTITY_INVALID")
        object.__setattr__(self,"manifest_identity",expected)

@dataclass(frozen=True)
class FinalGovernanceApprovalRecord:
    deployment_result_identity:str; release_request_identity:str; artifact_identity:str
    release_policy_identity:str; authority_identity:str; approver_identity:str
    decision:str; issued_at:str; expires_at:str; supersedes_record_identity:str|None=None
    record_identity:str=""
    def __post_init__(self):
        if not all(_text(getattr(self,x)) for x in ("deployment_result_identity","release_request_identity","artifact_identity","release_policy_identity","authority_identity","approver_identity")) or self.decision not in ("APPROVED","REVOKED") or (self.decision=="REVOKED")!=_text(self.supersedes_record_identity): raise ValueError("FINAL_GOVERNANCE_APPROVAL_INVALID")
        if _utc(self.expires_at)<=_utc(self.issued_at): raise ValueError("FINAL_GOVERNANCE_APPROVAL_VALIDITY_INVALID")
        expected=_identity(self,"FINAL_GOVERNANCE_APPROVAL",{"record_identity"})
        if self.record_identity and self.record_identity!=expected: raise ValueError("FINAL_GOVERNANCE_APPROVAL_IDENTITY_INVALID")
        object.__setattr__(self,"record_identity",expected)

@dataclass(frozen=True)
class FinalGovernanceRegistryEntry:
    record:FinalGovernanceApprovalRecord; sequence:int; previous_entry_identity:str|None; entry_identity:str=""
    def __post_init__(self):
        _revalidate(self.record)
        if type(self.sequence)is not int or self.sequence<1 or (self.sequence==1)!=(self.previous_entry_identity is None): raise ValueError("FINAL_GOVERNANCE_REGISTRY_ENTRY_INVALID")
        expected=identity_for("FINAL_GOVERNANCE_REGISTRY_ENTRY",{"record_identity":self.record.record_identity,"sequence":self.sequence,"previous_entry_identity":self.previous_entry_identity})
        if self.entry_identity and self.entry_identity!=expected: raise ValueError("FINAL_GOVERNANCE_REGISTRY_ENTRY_IDENTITY_INVALID")
        object.__setattr__(self,"entry_identity",expected)

@dataclass(frozen=True)
class FinalGovernanceRegistry:
    entries:tuple[FinalGovernanceRegistryEntry,...]=(); previous_registry_identity:str|None=None; registry_identity:str=""
    def __post_init__(self):
        entries=tuple(self.entries); object.__setattr__(self,"entries",entries)
        for i,e in enumerate(entries):
            _revalidate(e)
            if e.sequence!=i+1 or e.previous_entry_identity!=(None if i==0 else entries[i-1].entry_identity): raise ValueError("FINAL_GOVERNANCE_REGISTRY_LINEAGE_INVALID")
            if e.record.decision=="REVOKED" and not any(x.record.record_identity==e.record.supersedes_record_identity for x in entries[:i]): raise ValueError("FINAL_GOVERNANCE_SUPERSESSION_INVALID")
        predecessor=None if not entries else self._id(entries[:-1])
        if self.previous_registry_identity!=predecessor: raise ValueError("FINAL_GOVERNANCE_REGISTRY_PREDECESSOR_INVALID")
        expected=self._id(entries)
        if self.registry_identity and self.registry_identity!=expected: raise ValueError("FINAL_GOVERNANCE_REGISTRY_IDENTITY_INVALID")
        object.__setattr__(self,"registry_identity",expected)
    @staticmethod
    def _id(entries): return identity_for("FINAL_GOVERNANCE_REGISTRY",tuple(e.entry_identity for e in entries))
    def append(self,record):
        _revalidate(record)
        if any(e.record.record_identity==record.record_identity for e in self.entries): raise ValueError("FINAL_GOVERNANCE_REPLAY")
        return FinalGovernanceRegistry(self.entries+(FinalGovernanceRegistryEntry(record,len(self.entries)+1,None if not self.entries else self.entries[-1].entry_identity),),self.registry_identity)
    def is_effective(self,record):
        matches=[e.record for e in self.entries if e.record.deployment_result_identity==record.deployment_result_identity and e.record.release_request_identity==record.release_request_identity]
        return bool(matches and matches[-1]==record and record.decision=="APPROVED")

@dataclass(frozen=True)
class TargetRuntimeInstance:
    runtime_instance_reference:str; target_environment_identity:str; runtime_contract_identity:str
    executor_identity:str; executor_version:str; activation_generation:int; instance_identity:str=""
    def __post_init__(self):
        if not all(_text(getattr(self,x)) for x in ("runtime_instance_reference","target_environment_identity","runtime_contract_identity","executor_identity","executor_version")) or type(self.activation_generation)is not int or self.activation_generation<1: raise ValueError("TARGET_RUNTIME_INSTANCE_INVALID")
        expected=_identity(self,"TARGET_RUNTIME_INSTANCE",{"instance_identity"})
        if self.instance_identity and self.instance_identity!=expected: raise ValueError("TARGET_RUNTIME_INSTANCE_IDENTITY_INVALID")
        object.__setattr__(self,"instance_identity",expected)

@dataclass(frozen=True)
class ProductionReleaseGovernanceBundle:
    deployment_result:DeploymentResult; deployment_registry_entry:DeploymentRegistryEntry
    deployment_registry:DeploymentRegistry; human_approval_record:HumanApprovalRecord
    human_approval_registry:HumanApprovalRegistry; deployment_artifact:DeploymentArtifact
    artifact_registry_evidence:RegistryMembershipEvidence; rollback_artifact:RollbackArtifact
    rollback_manifest:RollbackManifest; rollback_registry_evidence:RegistryMembershipEvidence
    release_policy:object; final_governance_record:FinalGovernanceApprovalRecord
    final_governance_registry:FinalGovernanceRegistry; target_runtime_instance:TargetRuntimeInstance
    assessed_at:str; bundle_identity:str=""
    def __post_init__(self):
        for x in self.__dataclass_fields__:
            if x not in ("assessed_at","bundle_identity"): _revalidate(getattr(self,x))
        _utc(self.assessed_at)
        expected=identity_for("PRODUCTION_RELEASE_GOVERNANCE_BUNDLE",{x:(getattr(self,x).registry_identity if x.endswith("registry") else getattr(self,x).entry_identity if x=="deployment_registry_entry" else getattr(self,x).record_identity if x in ("human_approval_record","final_governance_record") else getattr(self,x).artifact_identity if x in ("deployment_artifact","rollback_artifact") else getattr(self,x).manifest_identity if x=="rollback_manifest" else getattr(self,x).evidence_identity if x.endswith("evidence") else getattr(self,x).policy_identity if x=="release_policy" else getattr(self,x).instance_identity if x=="target_runtime_instance" else getattr(self,x).result_identity if x=="deployment_result" else getattr(self,x)) for x in self.__dataclass_fields__ if x!="bundle_identity"})
        if self.bundle_identity and self.bundle_identity!=expected: raise ValueError("PRODUCTION_RELEASE_GOVERNANCE_BUNDLE_IDENTITY_INVALID")
        object.__setattr__(self,"bundle_identity",expected)

@dataclass(frozen=True)
class AuthoritativeReleaseCertificate:
    deployment_result_identity:str; deployment_registry_entry_identity:str; candidate_identity:str
    artifact_identity:str; promotion_report_identity:str; deployment_policy_identity:str
    governance_policy_identity:str; review_routing_identity:str; human_approval_record_identity:str
    release_request_identity:str; deployment_manifest_identity:str; release_policy_identity:str
    release_authority_identity:str; final_governance_record_identity:str; final_governance_authority_identity:str
    target_environment_identity:str; runtime_contract_identity:str; runtime_instance_identity:str
    executor_identity:str; executor_version:str; activation_generation:int; rollback_manifest_identity:str
    evidence:ReleaseEvidence; issued_at:str; certificate_identity:str=""; lifecycle_state:str="AUTHORIZED"
    runtime_activation_authorized:bool=True; broker_access_authorized:bool=False; trade_execution_authorized:bool=False
    def __post_init__(self):
        _revalidate(self.evidence); _utc(self.issued_at)
        if not all(g.passed for g in self.evidence.gates) or self.lifecycle_state!="AUTHORIZED" or self.runtime_activation_authorized is not True or self.broker_access_authorized or self.trade_execution_authorized or type(self.activation_generation)is not int: raise ValueError("RELEASE_CERTIFICATE_INVALID")
        expected=_identity(self,"AUTHORITATIVE_RELEASE_CERTIFICATE",{"certificate_identity"})
        if self.certificate_identity and self.certificate_identity!=expected: raise ValueError("RELEASE_CERTIFICATE_IDENTITY_INVALID")
        object.__setattr__(self,"certificate_identity",expected)

@dataclass(frozen=True)
class AuthoritativeReleaseManifest:
    certificate_identity:str; artifact_identity:str; release_policy_identity:str; target_environment_identity:str
    runtime_contract_identity:str; runtime_instance_identity:str; executor_identity:str; executor_version:str
    activation_generation:int; rollback_manifest_identity:str; manifest_identity:str=""
    def __post_init__(self):
        expected=_identity(self,"AUTHORITATIVE_RELEASE_MANIFEST",{"manifest_identity"})
        if self.manifest_identity and self.manifest_identity!=expected: raise ValueError("RELEASE_MANIFEST_IDENTITY_INVALID")
        object.__setattr__(self,"manifest_identity",expected)

@dataclass(frozen=True)
class AuthoritativeRuntimeActivationAuthorization:
    certificate_identity:str; release_manifest_identity:str; artifact_identity:str; release_policy_identity:str
    executor_identity:str; executor_version:str; runtime_instance_identity:str; target_environment_identity:str
    runtime_contract_identity:str; activation_generation:int; valid_from:str; valid_until:str
    authorization_identity:str=""; lifecycle_state:str="ACTIVATION_PENDING"; runtime_activation_authorized:bool=True
    broker_access_authorized:bool=False; trade_execution_authorized:bool=False
    def __post_init__(self):
        if _utc(self.valid_until)<=_utc(self.valid_from) or self.lifecycle_state!="ACTIVATION_PENDING" or self.runtime_activation_authorized is not True or self.broker_access_authorized or self.trade_execution_authorized: raise ValueError("RUNTIME_ACTIVATION_AUTHORIZATION_INVALID")
        expected=_identity(self,"AUTHORITATIVE_RUNTIME_ACTIVATION_AUTHORIZATION",{"authorization_identity"})
        if self.authorization_identity and self.authorization_identity!=expected: raise ValueError("RUNTIME_ACTIVATION_AUTHORIZATION_IDENTITY_INVALID")
        object.__setattr__(self,"authorization_identity",expected)

@dataclass(frozen=True)
class AuthoritativeReleaseDecision:
    evidence:ReleaseEvidence; decision:str; certificate:AuthoritativeReleaseCertificate|None=None
    release_manifest:AuthoritativeReleaseManifest|None=None
    runtime_activation_authorization:AuthoritativeRuntimeActivationAuthorization|None=None; decision_identity:str=""
    def __post_init__(self):
        approved=all(g.passed for g in self.evidence.gates); values=(self.certificate,self.release_manifest,self.runtime_activation_authorization)
        if self.decision != ("PRODUCTION_RELEASE_AUTHORIZED" if approved else "PRODUCTION_RELEASE_REJECTED") or approved!=all(v is not None for v in values): raise ValueError("RELEASE_DECISION_INVALID")
        if approved:
            c,m,a=values
            for v in values:_revalidate(v)
            fields=("artifact_identity","release_policy_identity","target_environment_identity","runtime_contract_identity","runtime_instance_identity","executor_identity","executor_version","activation_generation")
            if m.certificate_identity!=c.certificate_identity or a.certificate_identity!=c.certificate_identity or a.release_manifest_identity!=m.manifest_identity or any(getattr(c,x)!=getattr(m,x) or getattr(c,x)!=getattr(a,x) for x in fields): raise ValueError("RELEASE_DECISION_BINDING_INVALID")
        expected=identity_for("AUTHORITATIVE_RELEASE_DECISION",{"evidence":self.evidence.evidence_identity,"decision":self.decision,"certificate":None if self.certificate is None else self.certificate.certificate_identity,"manifest":None if self.release_manifest is None else self.release_manifest.manifest_identity,"authorization":None if self.runtime_activation_authorization is None else self.runtime_activation_authorization.authorization_identity})
        if self.decision_identity and self.decision_identity!=expected: raise ValueError("RELEASE_DECISION_IDENTITY_INVALID")
        object.__setattr__(self,"decision_identity",expected)

@dataclass(frozen=True)
class ReleaseCertificateRevocation:
    certificate_identity:str; authority_identity:str; reason:str; issued_at:str; revocation_identity:str=""
    def __post_init__(self):
        _utc(self.issued_at); expected=_identity(self,"RELEASE_CERTIFICATE_REVOCATION",{"revocation_identity"})
        if self.revocation_identity and self.revocation_identity!=expected: raise ValueError("CERTIFICATE_REVOCATION_IDENTITY_INVALID")
        object.__setattr__(self,"revocation_identity",expected)
@dataclass(frozen=True)
class ActivationRevocation:
    authorization_identity:str; authority_identity:str; reason:str; issued_at:str; revocation_identity:str=""
    def __post_init__(self):
        _utc(self.issued_at); expected=_identity(self,"ACTIVATION_REVOCATION",{"revocation_identity"})
        if self.revocation_identity and self.revocation_identity!=expected: raise ValueError("ACTIVATION_REVOCATION_IDENTITY_INVALID")
        object.__setattr__(self,"revocation_identity",expected)
@dataclass(frozen=True)
class EmergencyRollbackAuthorization:
    certificate_identity:str; rollback_manifest_identity:str; runtime_instance_identity:str
    authority_identity:str; reason:str; issued_at:str; rollback_authorization_identity:str=""; lifecycle_state:str="ROLLED_BACK"
    def __post_init__(self):
        _utc(self.issued_at)
        if self.lifecycle_state!="ROLLED_BACK": raise ValueError("ROLLBACK_AUTHORIZATION_INVALID")
        expected=_identity(self,"EMERGENCY_ROLLBACK_AUTHORIZATION",{"rollback_authorization_identity"})
        if self.rollback_authorization_identity and self.rollback_authorization_identity!=expected: raise ValueError("ROLLBACK_AUTHORIZATION_IDENTITY_INVALID")
        object.__setattr__(self,"rollback_authorization_identity",expected)

@dataclass(frozen=True)
class RuntimeActivationRegistryEntry:
    authorization:AuthoritativeRuntimeActivationAuthorization; sequence:int; previous_entry_identity:str|None
    state:str; consumed_at:str|None=None; entry_identity:str=""
    def __post_init__(self):
        _revalidate(self.authorization)
        if self.state not in LIFECYCLE_STATES or self.state not in ("ACTIVATION_PENDING","ACTIVATION_CONSUMED","ACTIVE","REVOKED","ROLLED_BACK"): raise ValueError("ACTIVATION_STATE_INVALID")
        if self.state in ("ACTIVATION_CONSUMED","ACTIVE") and not _text(self.consumed_at): raise ValueError("ACTIVATION_CONSUMPTION_MISSING")
        if self.consumed_at:_utc(self.consumed_at)
        expected=_identity(self,"RUNTIME_ACTIVATION_REGISTRY_ENTRY",{"entry_identity"})
        if self.entry_identity and self.entry_identity!=expected: raise ValueError("ACTIVATION_REGISTRY_ENTRY_IDENTITY_INVALID")
        object.__setattr__(self,"entry_identity",expected)
@dataclass(frozen=True)
class RuntimeActivationRegistry:
    entries:tuple[RuntimeActivationRegistryEntry,...]=()
    def __post_init__(self):
        for i,e in enumerate(self.entries):
            _revalidate(e)
            if e.sequence!=i+1 or e.previous_entry_identity!=(None if i==0 else self.entries[i-1].entry_identity): raise ValueError("ACTIVATION_REGISTRY_LINEAGE_INVALID")
            prior=[x for x in self.entries[:i] if x.authorization.authorization_identity==e.authorization.authorization_identity]
            allowed=(("ACTIVATION_PENDING","ACTIVATION_CONSUMED"),("ACTIVATION_CONSUMED","ACTIVE"),("ACTIVATION_PENDING","REVOKED"),("ACTIVATION_CONSUMED","REVOKED"),("ACTIVE","REVOKED"),("ACTIVE","ROLLED_BACK"))
            if e.state!="ACTIVATION_PENDING" and (not prior or (prior[-1].state,e.state) not in allowed): raise ValueError("ACTIVATION_LIFECYCLE_INVALID")
    def register(self,authorization):
        if any(e.authorization.authorization_identity==authorization.authorization_identity for e in self.entries): raise ValueError("ACTIVATION_REPLAY")
        return RuntimeActivationRegistry(self.entries+(RuntimeActivationRegistryEntry(authorization,len(self.entries)+1,None if not self.entries else self.entries[-1].entry_identity,"ACTIVATION_PENDING"),))
    def consume(self,authorization,executor_identity,executor_version,runtime_instance_identity,consumed_at):
        matches=[e for e in self.entries if e.authorization.authorization_identity==authorization.authorization_identity]
        if len(matches)!=1 or matches[0].state!="ACTIVATION_PENDING": raise ValueError("ACTIVATION_REPLAY")
        if not (_utc(authorization.valid_from)<=_utc(consumed_at)<_utc(authorization.valid_until)): raise ValueError("ACTIVATION_EXPIRED")
        if (executor_identity,executor_version,runtime_instance_identity)!=(authorization.executor_identity,authorization.executor_version,authorization.runtime_instance_identity): raise ValueError("ACTIVATION_TARGET_MISMATCH")
        event=RuntimeActivationRegistryEntry(authorization,len(self.entries)+1,self.entries[-1].entry_identity,"ACTIVATION_CONSUMED",consumed_at)
        return RuntimeActivationRegistry(self.entries+(event,))
    def transition(self,authorization,state,at):
        matches=[e for e in self.entries if e.authorization.authorization_identity==authorization.authorization_identity]
        if not matches: raise ValueError("ACTIVATION_NOT_REGISTERED")
        event=RuntimeActivationRegistryEntry(authorization,len(self.entries)+1,self.entries[-1].entry_identity,state,at if state in ("ACTIVATION_CONSUMED","ACTIVE") else None)
        return RuntimeActivationRegistry(self.entries+(event,))
