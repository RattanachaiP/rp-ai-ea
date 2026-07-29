"""Immutable contracts for the offline Deployment Governance Authority."""
from __future__ import annotations
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Mapping
from learning.common.immutable import freeze, thaw
from learning.promotion import GovernanceQueueRegistry, PromotionRegistry, PromotionResult
from learning.promotion.identity import identity_for

DEPLOYMENT_SCHEMA_VERSION = "PR275.DEPLOYMENT.2.0"
DEPLOYMENT_GATES = ("promotion_eligibility", "human_approval_validation",
    "deployment_policy_validation", "evidence_completeness",
    "registry_lineage_validation", "artifact_integrity", "release_routing_integrity",
    "manifest_binding_integrity")
_HASH_LENGTH = 64

def _text(value): return isinstance(value, str) and bool(value.strip())
def _hash(value): return _text(value) and len(value) == _HASH_LENGTH and value == value.lower() and all(c in "0123456789abcdef" for c in value)
def _revalidate(value): type(value)(**value.__dict__)
def _utc(value):
    if not _text(value) or not value.endswith("Z"): raise ValueError("NON_CANONICAL_UTC_TIMESTAMP")
    try: parsed=datetime.fromisoformat(value[:-1]+"+00:00")
    except ValueError as exc: raise ValueError("NON_CANONICAL_UTC_TIMESTAMP") from exc
    if parsed.tzinfo != timezone.utc or parsed.microsecond: raise ValueError("NON_CANONICAL_UTC_TIMESTAMP")
    canonical=parsed.strftime("%Y-%m-%dT%H:%M:%SZ")
    if value != canonical: raise ValueError("NON_CANONICAL_UTC_TIMESTAMP")
    return parsed

@dataclass(frozen=True)
class TargetEnvironment:
    environment_reference: str; environment_class: str; runtime_contract_identity: str
    environment_identity: str = ""
    def __post_init__(self):
        if (not _text(self.environment_reference) or self.environment_class not in ("TEST","DEMO","LIVE_PRODUCTION")
                or not _text(self.runtime_contract_identity)): raise ValueError("TARGET_ENVIRONMENT_INVALID")
        expected=identity_for("DEPLOYMENT_TARGET_ENVIRONMENT",self.canonical_payload())
        if self.environment_identity and self.environment_identity != expected: raise ValueError("TARGET_ENVIRONMENT_IDENTITY_INVALID")
        object.__setattr__(self,"environment_identity",expected)
    def canonical_payload(self): return {x:getattr(self,x) for x in self.__dataclass_fields__ if x!="environment_identity"}

@dataclass(frozen=True)
class DeploymentPolicy:
    policy_reference: str; accepted_promotion_policy_identities: tuple[str,...]
    approval_authority_identity: str; required_approver_role: str
    governance_policy_identity: str; release_authority_identity: str
    permitted_environment_classes: tuple[str,...]; accepted_runtime_contract_identities: tuple[str,...]
    maximum_approval_age_seconds: int; policy_identity: str=""
    schema_version: str=DEPLOYMENT_SCHEMA_VERSION
    def __post_init__(self):
        accepted=tuple(self.accepted_promotion_policy_identities); environments=tuple(self.permitted_environment_classes)
        runtimes=tuple(self.accepted_runtime_contract_identities)
        if (not all(_text(getattr(self,x)) for x in ("policy_reference","approval_authority_identity","required_approver_role","governance_policy_identity","release_authority_identity"))
                or not accepted or len(set(accepted))!=len(accepted) or not all(_text(x) for x in accepted)
                or not environments or len(set(environments))!=len(environments) or any(x not in ("TEST","DEMO","LIVE_PRODUCTION") for x in environments)
                or not runtimes or len(set(runtimes))!=len(runtimes) or not all(_text(x) for x in runtimes)
                or type(self.maximum_approval_age_seconds) is not int or self.maximum_approval_age_seconds < 1
                or self.schema_version != DEPLOYMENT_SCHEMA_VERSION): raise ValueError("DEPLOYMENT_POLICY_INVALID")
        object.__setattr__(self,"accepted_promotion_policy_identities",accepted); object.__setattr__(self,"permitted_environment_classes",environments)
        object.__setattr__(self,"accepted_runtime_contract_identities",runtimes)
        expected=identity_for("DEPLOYMENT_POLICY",self.canonical_payload())
        if self.policy_identity and self.policy_identity!=expected: raise ValueError("DEPLOYMENT_POLICY_IDENTITY_INVALID")
        object.__setattr__(self,"policy_identity",expected)
    def canonical_payload(self): return {x:getattr(self,x) for x in self.__dataclass_fields__ if x!="policy_identity"}

@dataclass(frozen=True)
class DeploymentArtifact:
    candidate_identity: str; content_hash: str; model_hash: str
    build_provenance_identity: str; compatibility_evidence: Mapping[str,object]
    target_environment_identity: str; runtime_contract_identity: str; artifact_identity: str=""
    def __post_init__(self):
        if (not _text(self.candidate_identity) or not _hash(self.content_hash) or not _hash(self.model_hash)
                or not all(_text(getattr(self,x)) for x in ("build_provenance_identity","target_environment_identity","runtime_contract_identity"))
                or not isinstance(self.compatibility_evidence,Mapping) or not self.compatibility_evidence): raise ValueError("DEPLOYMENT_ARTIFACT_INVALID")
        object.__setattr__(self,"compatibility_evidence",freeze(dict(self.compatibility_evidence)))
        required={"model_hash":self.model_hash,"build_provenance_identity":self.build_provenance_identity,
            "target_environment_identity":self.target_environment_identity,"runtime_contract_identity":self.runtime_contract_identity}
        if any(self.compatibility_evidence.get(k)!=v for k,v in required.items()): raise ValueError("DEPLOYMENT_ARTIFACT_COMPATIBILITY_INVALID")
        expected=identity_for("DEPLOYMENT_ARTIFACT",self.canonical_payload())
        if self.artifact_identity and self.artifact_identity!=expected: raise ValueError("DEPLOYMENT_ARTIFACT_IDENTITY_INVALID")
        object.__setattr__(self,"artifact_identity",expected)
    def canonical_payload(self): return {x:(thaw(self.compatibility_evidence) if x=="compatibility_evidence" else getattr(self,x)) for x in self.__dataclass_fields__ if x!="artifact_identity"}

@dataclass(frozen=True)
class HumanApprovalRecord:
    promotion_report_identity: str; approval_request_identity: str; promotion_policy_identity: str
    governance_policy_identity: str; review_routing_identity: str; candidate_identity: str
    approval_authority_identity: str; approver_identity: str; required_reviewer_role: str
    decision: str; issued_at: str; expires_at: str; supersedes_record_identity: str|None=None
    record_identity: str=""
    def __post_init__(self):
        if (not all(_text(getattr(self,x)) for x in ("promotion_report_identity","approval_request_identity","promotion_policy_identity","governance_policy_identity","review_routing_identity","candidate_identity","approval_authority_identity","approver_identity","required_reviewer_role"))
                or self.decision not in ("APPROVED","REVOKED") or (self.decision=="REVOKED") != _text(self.supersedes_record_identity)):
            raise ValueError("HUMAN_APPROVAL_RECORD_INVALID")
        issued,expires=_utc(self.issued_at),_utc(self.expires_at)
        if expires <= issued: raise ValueError("HUMAN_APPROVAL_VALIDITY_INVALID")
        expected=identity_for("DEPLOYMENT_HUMAN_APPROVAL",self.canonical_payload())
        if self.record_identity and self.record_identity!=expected: raise ValueError("HUMAN_APPROVAL_RECORD_IDENTITY_INVALID")
        object.__setattr__(self,"record_identity",expected)
    def canonical_payload(self): return {x:getattr(self,x) for x in self.__dataclass_fields__ if x!="record_identity"}

@dataclass(frozen=True)
class HumanApprovalRegistryEntry:
    record:HumanApprovalRecord; sequence:int; previous_entry_identity:str|None; entry_identity:str=""
    def __post_init__(self):
        _revalidate(self.record)
        if type(self.sequence)is not int or self.sequence<1 or (self.sequence==1)!=(self.previous_entry_identity is None): raise ValueError("HUMAN_APPROVAL_REGISTRY_ENTRY_INVALID")
        expected=identity_for("HUMAN_APPROVAL_REGISTRY_ENTRY",{"record_identity":self.record.record_identity,"sequence":self.sequence,"previous_entry_identity":self.previous_entry_identity})
        if self.entry_identity and self.entry_identity!=expected: raise ValueError("HUMAN_APPROVAL_REGISTRY_ENTRY_IDENTITY_INVALID")
        object.__setattr__(self,"entry_identity",expected)

@dataclass(frozen=True)
class HumanApprovalRegistry:
    entries:tuple[HumanApprovalRegistryEntry,...]=(); previous_registry_identity:str|None=None; registry_identity:str=""
    def __post_init__(self):
        entries=tuple(self.entries); object.__setattr__(self,"entries",entries)
        for i,x in enumerate(entries):
            HumanApprovalRegistryEntry(**x.__dict__)
            if x.sequence!=i+1 or x.previous_entry_identity!=(None if i==0 else entries[i-1].entry_identity): raise ValueError("HUMAN_APPROVAL_REGISTRY_LINEAGE_INVALID")
            if x.record.decision=="REVOKED" and not any(y.record.record_identity==x.record.supersedes_record_identity for y in entries[:i]): raise ValueError("HUMAN_APPROVAL_SUPERSESSION_INVALID")
        if len({x.record.record_identity for x in entries})!=len(entries): raise ValueError("HUMAN_APPROVAL_REPLAY")
        predecessor=None if not entries else self._identity(entries[:-1])
        if self.previous_registry_identity!=predecessor: raise ValueError("HUMAN_APPROVAL_REGISTRY_PREDECESSOR_INVALID")
        expected=self._identity(entries)
        if self.registry_identity and self.registry_identity!=expected: raise ValueError("HUMAN_APPROVAL_REGISTRY_IDENTITY_INVALID")
        object.__setattr__(self,"registry_identity",expected)
    @staticmethod
    def _identity(entries): return identity_for("HUMAN_APPROVAL_REGISTRY",tuple(x.entry_identity for x in entries))
    def append(self,record):
        _revalidate(record)
        if any(x.record.record_identity==record.record_identity for x in self.entries): raise ValueError("HUMAN_APPROVAL_REPLAY")
        entry=HumanApprovalRegistryEntry(record,len(self.entries)+1,None if not self.entries else self.entries[-1].entry_identity)
        return HumanApprovalRegistry(self.entries+(entry,),self.registry_identity)
    def is_effective(self,record):
        matches=[x for x in self.entries if x.record.approval_request_identity==record.approval_request_identity]
        return bool(matches and matches[-1].record==record and record.decision=="APPROVED")

@dataclass(frozen=True)
class DeploymentGovernanceBundle:
    promotion_result:PromotionResult; promotion_registry:PromotionRegistry
    governance_queue_entry:object; governance_queue_registry:GovernanceQueueRegistry
    human_approval_record:HumanApprovalRecord; human_approval_registry:HumanApprovalRegistry
    deployment_artifact:DeploymentArtifact; target_environment:TargetEnvironment
    deployment_policy:DeploymentPolicy; assessed_at:str; bundle_identity:str=""
    def __post_init__(self):
        for x in (self.promotion_result,self.promotion_registry,self.governance_queue_entry,self.governance_queue_registry,
                self.human_approval_record,self.human_approval_registry,self.deployment_artifact,self.target_environment,self.deployment_policy): _revalidate(x)
        _utc(self.assessed_at)
        result_matches=[x for x in self.promotion_registry.entries if x.result.result_identity==self.promotion_result.result_identity]
        queue_matches=[x for x in self.governance_queue_registry.entries if x.queue_entry.queue_identity==self.governance_queue_entry.queue_identity]
        if (len(result_matches)!=1 or result_matches[0].result!=self.promotion_result or self.promotion_result.governance_queue_entry!=self.governance_queue_entry
                or len(queue_matches)!=1 or queue_matches[0].queue_entry!=self.governance_queue_entry
                or not any(x.record==self.human_approval_record for x in self.human_approval_registry.entries)):
            raise ValueError("DEPLOYMENT_GOVERNANCE_BUNDLE_BINDING_INVALID")
        expected=identity_for("DEPLOYMENT_GOVERNANCE_BUNDLE",self.canonical_payload())
        if self.bundle_identity and self.bundle_identity!=expected: raise ValueError("DEPLOYMENT_GOVERNANCE_BUNDLE_IDENTITY_INVALID")
        object.__setattr__(self,"bundle_identity",expected)
    def canonical_payload(self): return {"promotion_result_identity":self.promotion_result.result_identity,"promotion_registry_identity":self.promotion_registry.registry_identity,"governance_queue_identity":self.governance_queue_entry.queue_identity,"governance_queue_registry_identity":self.governance_queue_registry.registry_identity,"human_approval_record_identity":self.human_approval_record.record_identity,"human_approval_registry_identity":self.human_approval_registry.registry_identity,"artifact_identity":self.deployment_artifact.artifact_identity,"target_environment_identity":self.target_environment.environment_identity,"deployment_policy_identity":self.deployment_policy.policy_identity,"assessed_at":self.assessed_at}

@dataclass(frozen=True)
class DeploymentGate:
    gate:str; passed:bool; reason:str; evidence:Mapping[str,object]
    def __post_init__(self):
        if self.gate not in DEPLOYMENT_GATES or type(self.passed)is not bool or self.reason != ("GATE_PASSED" if self.passed else "GATE_FAILED") or not isinstance(self.evidence,Mapping) or not self.evidence: raise ValueError("DEPLOYMENT_GATE_INVALID")
        object.__setattr__(self,"evidence",freeze(dict(self.evidence)))

@dataclass(frozen=True)
class DeploymentEvidence:
    bundle_identity:str; promotion_report_identity:str; approval_record_identity:str
    artifact_identity:str; target_environment_identity:str; runtime_contract_identity:str
    deployment_policy_identity:str; gates:tuple[DeploymentGate,...]; evidence_identity:str=""
    def __post_init__(self):
        gates=tuple(self.gates)
        if not all(_text(getattr(self,x)) for x in self.__dataclass_fields__ if x not in ("gates","evidence_identity")) or tuple(x.gate for x in gates)!=DEPLOYMENT_GATES: raise ValueError("DEPLOYMENT_EVIDENCE_INVALID")
        for x in gates: DeploymentGate(x.gate,x.passed,x.reason,thaw(x.evidence))
        object.__setattr__(self,"gates",gates); expected=identity_for("DEPLOYMENT_EVIDENCE",self.canonical_payload())
        if self.evidence_identity and self.evidence_identity!=expected: raise ValueError("DEPLOYMENT_EVIDENCE_IDENTITY_INVALID")
        object.__setattr__(self,"evidence_identity",expected)
    def canonical_payload(self): return {x:(tuple({"gate":g.gate,"passed":g.passed,"reason":g.reason,"evidence":thaw(g.evidence)} for g in self.gates) if x=="gates" else getattr(self,x)) for x in self.__dataclass_fields__ if x!="evidence_identity"}

@dataclass(frozen=True)
class DeploymentReadinessReport:
    candidate_identity:str; artifact_identity:str; promotion_report_identity:str
    approval_record_identity:str; target_environment_identity:str; runtime_contract_identity:str
    deployment_policy_identity:str; deployment_evidence:DeploymentEvidence; decision:str
    governance_certified:bool=False; release_governance_eligible:bool=False; report_identity:str=""
    deployment_performed:bool=False; production_released:bool=False; runtime_activated:bool=False
    broker_access_authorized:bool=False; trades_executed:bool=False
    def __post_init__(self):
        _revalidate(self.deployment_evidence); passed=all(x.passed for x in self.deployment_evidence.gates)
        if (self.decision != ("DEPLOYMENT GOVERNANCE ELIGIBLE" if passed else "DEPLOYMENT REJECTED") or self.governance_certified is not passed
                or self.release_governance_eligible is not passed or any((self.deployment_performed,self.production_released,self.runtime_activated,self.broker_access_authorized,self.trades_executed))
                or any(getattr(self,x)!=getattr(self.deployment_evidence,x) for x in ("artifact_identity","promotion_report_identity","approval_record_identity","target_environment_identity","runtime_contract_identity","deployment_policy_identity"))): raise ValueError("DEPLOYMENT_READINESS_REPORT_INVALID")
        expected=identity_for("DEPLOYMENT_READINESS_REPORT",self.canonical_payload())
        if self.report_identity and self.report_identity!=expected: raise ValueError("DEPLOYMENT_READINESS_REPORT_IDENTITY_INVALID")
        object.__setattr__(self,"report_identity",expected)
    def canonical_payload(self): return {x:(self.deployment_evidence.evidence_identity if x=="deployment_evidence" else getattr(self,x)) for x in self.__dataclass_fields__ if x!="report_identity"}

@dataclass(frozen=True)
class DeploymentManifest:
    readiness_report_identity:str; candidate_identity:str; artifact_identity:str
    promotion_report_identity:str; approval_record_identity:str; deployment_policy_identity:str
    target_environment_identity:str; runtime_contract_identity:str; release_authority_identity:str
    supersedes_manifest_identity:str|None=None; activation_permitted:bool=False; manifest_identity:str=""
    def __post_init__(self):
        if not all(_text(getattr(self,x)) for x in self.__dataclass_fields__ if x not in ("supersedes_manifest_identity","activation_permitted","manifest_identity")) or self.activation_permitted is not False: raise ValueError("DEPLOYMENT_MANIFEST_INVALID")
        expected=identity_for("DEPLOYMENT_MANIFEST",self.canonical_payload())
        if self.manifest_identity and self.manifest_identity!=expected: raise ValueError("DEPLOYMENT_MANIFEST_IDENTITY_INVALID")
        object.__setattr__(self,"manifest_identity",expected)
    def canonical_payload(self): return {x:getattr(self,x) for x in self.__dataclass_fields__ if x!="manifest_identity"}

@dataclass(frozen=True)
class ReleaseRequest:
    readiness_report_identity:str; manifest_identity:str; candidate_identity:str; artifact_identity:str
    deployment_policy_identity:str; promotion_report_identity:str; human_approval_record_identity:str
    governance_policy_identity:str; review_routing_identity:str; target_environment_identity:str
    runtime_contract_identity:str; release_authority_identity:str
    status:str="PENDING_PRODUCTION_RELEASE_AUTHORITY"; request_identity:str=""
    production_release_authorized:bool=False; runtime_activation_authorized:bool=False
    broker_access_authorized:bool=False; trade_execution_authorized:bool=False
    def __post_init__(self):
        if (not all(_text(getattr(self,x)) for x in self.__dataclass_fields__ if x not in ("request_identity","production_release_authorized","runtime_activation_authorized","broker_access_authorized","trade_execution_authorized"))
                or self.status!="PENDING_PRODUCTION_RELEASE_AUTHORITY" or any((self.production_release_authorized,self.runtime_activation_authorized,self.broker_access_authorized,self.trade_execution_authorized))): raise ValueError("RELEASE_REQUEST_INVALID")
        expected=identity_for("RELEASE_REQUEST",self.canonical_payload())
        if self.request_identity and self.request_identity!=expected: raise ValueError("RELEASE_REQUEST_IDENTITY_INVALID")
        object.__setattr__(self,"request_identity",expected)
    def canonical_payload(self): return {x:getattr(self,x) for x in self.__dataclass_fields__ if x!="request_identity"}

@dataclass(frozen=True)
class DeploymentResult:
    report:DeploymentReadinessReport; manifest:DeploymentManifest|None; release_request:ReleaseRequest|None; result_identity:str=""
    def __post_init__(self):
        _revalidate(self.report); eligible=self.report.decision=="DEPLOYMENT GOVERNANCE ELIGIBLE"
        if eligible != (self.manifest is not None and self.release_request is not None): raise ValueError("DEPLOYMENT_RESULT_INVALID")
        if eligible:
            _revalidate(self.manifest); _revalidate(self.release_request); m=self.manifest; r=self.release_request; report=self.report
            fields=("candidate_identity","artifact_identity","promotion_report_identity","deployment_policy_identity","target_environment_identity","runtime_contract_identity")
            if (m.readiness_report_identity!=report.report_identity or r.readiness_report_identity!=report.report_identity or r.manifest_identity!=m.manifest_identity
                    or any(getattr(m,x)!=getattr(report,x) for x in fields) or any(getattr(r,x)!=getattr(report,x) for x in fields)
                    or m.approval_record_identity!=report.approval_record_identity or r.human_approval_record_identity!=report.approval_record_identity
                    or m.release_authority_identity!=r.release_authority_identity): raise ValueError("DEPLOYMENT_RESULT_BINDING_INVALID")
        expected=identity_for("DEPLOYMENT_RESULT",self.canonical_payload())
        if self.result_identity and self.result_identity!=expected: raise ValueError("DEPLOYMENT_RESULT_IDENTITY_INVALID")
        object.__setattr__(self,"result_identity",expected)
    def canonical_payload(self): return {"report_identity":self.report.report_identity,"manifest_identity":None if self.manifest is None else self.manifest.manifest_identity,"release_request_identity":None if self.release_request is None else self.release_request.request_identity}
