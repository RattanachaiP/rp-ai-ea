"""Immutable contracts owned by Deployment Governance Authority."""
from __future__ import annotations
from dataclasses import dataclass
from typing import Mapping
from learning.common.immutable import freeze, thaw
from learning.promotion.identity import identity_for

DEPLOYMENT_SCHEMA_VERSION = "PR275.DEPLOYMENT.1.0"
DEPLOYMENT_GATES = ("promotion_eligibility", "human_approval_validation",
    "deployment_policy_validation", "evidence_completeness",
    "registry_lineage_validation", "artifact_integrity", "release_readiness",
    "governance_certification")

def _text(value): return isinstance(value, str) and bool(value.strip())
def _revalidate(value): type(value)(**value.__dict__)

@dataclass(frozen=True)
class DeploymentPolicy:
    policy_reference: str
    accepted_promotion_policy_identities: tuple[str, ...]
    approval_authority_identity: str
    required_approver_role: str
    release_authority_identity: str
    policy_identity: str = ""
    schema_version: str = DEPLOYMENT_SCHEMA_VERSION
    def __post_init__(self):
        accepted = tuple(self.accepted_promotion_policy_identities)
        if (not all(_text(getattr(self, name)) for name in ("policy_reference",
                "approval_authority_identity", "required_approver_role", "release_authority_identity"))
                or not accepted or len(set(accepted)) != len(accepted)
                or not all(_text(x) for x in accepted)
                or self.schema_version != DEPLOYMENT_SCHEMA_VERSION):
            raise ValueError("DEPLOYMENT_POLICY_INVALID")
        object.__setattr__(self, "accepted_promotion_policy_identities", accepted)
        expected = identity_for("DEPLOYMENT_POLICY", self.canonical_payload())
        if self.policy_identity and self.policy_identity != expected: raise ValueError("DEPLOYMENT_POLICY_IDENTITY_INVALID")
        object.__setattr__(self, "policy_identity", expected)
    def canonical_payload(self): return {x:getattr(self,x) for x in self.__dataclass_fields__ if x != "policy_identity"}

@dataclass(frozen=True)
class HumanApprovalRecord:
    promotion_report_identity: str
    approval_request_identity: str
    candidate_identity: str
    approval_authority_identity: str
    approver_identity: str
    approver_role: str
    artifact_identity: str
    decision: str
    approved_at: str
    record_identity: str = ""
    def __post_init__(self):
        if (not all(_text(getattr(self,x)) for x in self.__dataclass_fields__ if x != "record_identity")
                or self.decision not in ("APPROVED", "REJECTED")):
            raise ValueError("HUMAN_APPROVAL_RECORD_INVALID")
        expected=identity_for("DEPLOYMENT_HUMAN_APPROVAL",self.canonical_payload())
        if self.record_identity and self.record_identity != expected: raise ValueError("HUMAN_APPROVAL_RECORD_IDENTITY_INVALID")
        object.__setattr__(self,"record_identity",expected)
    def canonical_payload(self): return {x:getattr(self,x) for x in self.__dataclass_fields__ if x != "record_identity"}

@dataclass(frozen=True)
class DeploymentGate:
    gate: str; passed: bool; reason: str; evidence: Mapping[str, object]
    def __post_init__(self):
        if (self.gate not in DEPLOYMENT_GATES or type(self.passed) is not bool
                or self.reason != ("GATE_PASSED" if self.passed else "GATE_FAILED")
                or not isinstance(self.evidence, Mapping) or not self.evidence): raise ValueError("DEPLOYMENT_GATE_INVALID")
        object.__setattr__(self,"evidence",freeze(dict(self.evidence)))

@dataclass(frozen=True)
class DeploymentEvidence:
    promotion_registry_identity: str; promotion_registry_entry_identity: str
    promotion_report_identity: str; promotion_evidence_identity: str
    human_approval_record_identity: str; deployment_policy_identity: str
    candidate_identity: str; artifact_identity: str; gates: tuple[DeploymentGate,...]
    evidence_identity: str = ""
    def __post_init__(self):
        gates=tuple(self.gates)
        if (not all(_text(getattr(self,x)) for x in self.__dataclass_fields__ if x not in ("gates","evidence_identity"))
                or tuple(x.gate for x in gates) != DEPLOYMENT_GATES): raise ValueError("DEPLOYMENT_EVIDENCE_INVALID")
        for gate in gates: DeploymentGate(gate.gate,gate.passed,gate.reason,thaw(gate.evidence))
        object.__setattr__(self,"gates",gates)
        expected=identity_for("DEPLOYMENT_EVIDENCE",self.canonical_payload())
        if self.evidence_identity and self.evidence_identity != expected: raise ValueError("DEPLOYMENT_EVIDENCE_IDENTITY_INVALID")
        object.__setattr__(self,"evidence_identity",expected)
    def canonical_payload(self):
        return {x:(tuple({"gate":g.gate,"passed":g.passed,"reason":g.reason,"evidence":thaw(g.evidence)} for g in self.gates) if x=="gates" else getattr(self,x)) for x in self.__dataclass_fields__ if x != "evidence_identity"}

@dataclass(frozen=True)
class DeploymentReadinessReport:
    candidate_identity: str; artifact_identity: str; policy: DeploymentPolicy
    deployment_evidence: DeploymentEvidence; decision: str
    report_identity: str = ""; governance_certified: bool = False
    release_ready: bool = False; deployment_performed: bool = False
    production_released: bool = False; trades_executed: bool = False
    schema_version: str = DEPLOYMENT_SCHEMA_VERSION
    def __post_init__(self):
        _revalidate(self.policy); _revalidate(self.deployment_evidence)
        passed=all(x.passed for x in self.deployment_evidence.gates)
        if (self.decision != ("DEPLOYMENT ELIGIBLE" if passed else "DEPLOYMENT REJECTED")
                or self.governance_certified is not passed or self.release_ready is not passed
                or any((self.deployment_performed,self.production_released,self.trades_executed))
                or self.schema_version != DEPLOYMENT_SCHEMA_VERSION
                or self.candidate_identity != self.deployment_evidence.candidate_identity
                or self.artifact_identity != self.deployment_evidence.artifact_identity
                or self.policy.policy_identity != self.deployment_evidence.deployment_policy_identity):
            raise ValueError("DEPLOYMENT_READINESS_REPORT_INVALID")
        expected=identity_for("DEPLOYMENT_READINESS_REPORT",self.canonical_payload())
        if self.report_identity and self.report_identity != expected: raise ValueError("DEPLOYMENT_READINESS_REPORT_IDENTITY_INVALID")
        object.__setattr__(self,"report_identity",expected)
    def canonical_payload(self): return {x:(self.policy.policy_identity if x=="policy" else self.deployment_evidence.evidence_identity if x=="deployment_evidence" else getattr(self,x)) for x in self.__dataclass_fields__ if x != "report_identity"}

@dataclass(frozen=True)
class DeploymentManifest:
    readiness_report_identity: str; candidate_identity: str; artifact_identity: str
    promotion_report_identity: str; deployment_policy_identity: str
    manifest_identity: str = ""; activation_permitted: bool = False
    def __post_init__(self):
        if not all(_text(getattr(self,x)) for x in ("readiness_report_identity","candidate_identity","artifact_identity","promotion_report_identity","deployment_policy_identity")) or self.activation_permitted is not False: raise ValueError("DEPLOYMENT_MANIFEST_INVALID")
        expected=identity_for("DEPLOYMENT_MANIFEST",self.canonical_payload())
        if self.manifest_identity and self.manifest_identity != expected: raise ValueError("DEPLOYMENT_MANIFEST_IDENTITY_INVALID")
        object.__setattr__(self,"manifest_identity",expected)
    def canonical_payload(self): return {x:getattr(self,x) for x in self.__dataclass_fields__ if x != "manifest_identity"}

@dataclass(frozen=True)
class ReleaseRequest:
    readiness_report_identity: str; manifest_identity: str; candidate_identity: str
    artifact_identity: str; release_authority_identity: str
    status: str = "PENDING_PRODUCTION_RELEASE_AUTHORITY"; request_identity: str = ""
    def __post_init__(self):
        if not all(_text(getattr(self,x)) for x in self.__dataclass_fields__ if x != "request_identity") or self.status != "PENDING_PRODUCTION_RELEASE_AUTHORITY": raise ValueError("RELEASE_REQUEST_INVALID")
        expected=identity_for("RELEASE_REQUEST",self.canonical_payload())
        if self.request_identity and self.request_identity != expected: raise ValueError("RELEASE_REQUEST_IDENTITY_INVALID")
        object.__setattr__(self,"request_identity",expected)
    def canonical_payload(self): return {x:getattr(self,x) for x in self.__dataclass_fields__ if x != "request_identity"}

@dataclass(frozen=True)
class DeploymentResult:
    report: DeploymentReadinessReport; manifest: DeploymentManifest|None
    release_request: ReleaseRequest|None; result_identity: str = ""
    def __post_init__(self):
        _revalidate(self.report); eligible=self.report.decision=="DEPLOYMENT ELIGIBLE"
        if eligible != (self.manifest is not None and self.release_request is not None): raise ValueError("DEPLOYMENT_RESULT_INVALID")
        if eligible:
            _revalidate(self.manifest); _revalidate(self.release_request)
            if (self.manifest.readiness_report_identity != self.report.report_identity
                    or self.release_request.readiness_report_identity != self.report.report_identity
                    or self.release_request.manifest_identity != self.manifest.manifest_identity): raise ValueError("DEPLOYMENT_RESULT_BINDING_INVALID")
        expected=identity_for("DEPLOYMENT_RESULT",self.canonical_payload())
        if self.result_identity and self.result_identity != expected: raise ValueError("DEPLOYMENT_RESULT_IDENTITY_INVALID")
        object.__setattr__(self,"result_identity",expected)
    def canonical_payload(self): return {"report_identity":self.report.report_identity,"manifest_identity":None if self.manifest is None else self.manifest.manifest_identity,"release_request_identity":None if self.release_request is None else self.release_request.request_identity}
