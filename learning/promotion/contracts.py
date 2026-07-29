"""Immutable, identity-bound contracts for governed promotion eligibility."""
from __future__ import annotations
from dataclasses import dataclass
from typing import Mapping
from learning.common.immutable import freeze, thaw
from .identity import identity_for

PROMOTION_SCHEMA_VERSION = "PR274.PROMOTION.2.0"
PROMOTION_GATES = ("qualification_validity", "promotion_policy_compliance", "evidence_completeness",
    "candidate_integrity", "registry_lineage_validation", "governance_readiness",
    "review_routing_integrity", "governance_entry_eligibility")
PROMOTION_DECISIONS = ("ELIGIBLE", "CONDITIONAL", "REJECTED")
CRITICAL_GATES = frozenset(PROMOTION_GATES[:5] + (PROMOTION_GATES[6],))
def _text(v): return isinstance(v, str) and bool(v.strip())
def _validate(v): type(v)(**v.__dict__)

@dataclass(frozen=True)
class PromotionPolicy:
    policy_reference: str; accepted_qualification_policy_identities: tuple[str, ...]
    human_approval_authority_identity: str; governance_policy_identity: str; required_reviewer_role: str
    conditional_gates: tuple[str, ...] = (); require_qualification_pass: bool = True
    require_governance_eligible: bool = True; schema_version: str = PROMOTION_SCHEMA_VERSION; policy_identity: str = ""
    def __post_init__(self):
        accepted, conditional = tuple(self.accepted_qualification_policy_identities), tuple(self.conditional_gates)
        if (not all(_text(getattr(self,x)) for x in ("policy_reference","human_approval_authority_identity","governance_policy_identity","required_reviewer_role"))
            or not accepted or len(set(accepted)) != len(accepted) or not all(_text(x) for x in accepted)
            or len(set(conditional)) != len(conditional) or any(x not in PROMOTION_GATES or x in CRITICAL_GATES for x in conditional)
            or type(self.require_qualification_pass) is not bool or type(self.require_governance_eligible) is not bool
            or self.schema_version != PROMOTION_SCHEMA_VERSION): raise ValueError("PROMOTION_POLICY_INVALID")
        object.__setattr__(self,"accepted_qualification_policy_identities",accepted); object.__setattr__(self,"conditional_gates",conditional)
        expected=identity_for("PROMOTION_POLICY",self.canonical_payload())
        if self.policy_identity and self.policy_identity != expected: raise ValueError("PROMOTION_POLICY_IDENTITY_INVALID")
        object.__setattr__(self,"policy_identity",expected)
    def canonical_payload(self): return {x:getattr(self,x) for x in self.__dataclass_fields__ if x!="policy_identity"}

@dataclass(frozen=True)
class QualificationBundle:
    candidate_registry: object; evaluation_registry: object; qualification_registry: object
    candidate: object; candidate_evidence: object; evaluation_report: object
    qualification_report: object; qualification_evidence: object; bundle_identity: str = ""
    def __post_init__(self):
        for x in (self.candidate_registry,self.evaluation_registry,self.qualification_registry,self.candidate,
                  self.candidate_evidence,self.evaluation_report,self.qualification_report,self.qualification_evidence): _validate(x)
        candidates=tuple(x for x in self.candidate_registry.entries if x.candidate.model_identity==self.candidate.model_identity)
        evaluations=tuple(x for x in self.evaluation_registry.entries if x.report.report_identity==self.evaluation_report.report_identity)
        qualifications=tuple(x for x in self.qualification_registry.entries if x.report.report_identity==self.qualification_report.report_identity)
        if (len(candidates)!=1 or candidates[0].candidate != self.candidate or candidates[0].evidence != self.candidate_evidence
            or len(evaluations)!=1 or evaluations[0].report != self.evaluation_report
            or len(qualifications)!=1 or qualifications[0].report != self.qualification_report
            or self.evaluation_report.candidate_identity != self.candidate.model_identity
            or self.qualification_report.candidate_identity != self.candidate.model_identity
            or self.qualification_report.evaluation_report_identity != self.evaluation_report.report_identity
            or self.qualification_report.candidate_registry_identity != self.candidate_registry.registry_identity
            or self.qualification_report.evaluation_registry_identity != self.evaluation_registry.registry_identity
            or self.qualification_report.qualification_evidence != self.qualification_evidence): raise ValueError("QUALIFICATION_BUNDLE_BINDING_INVALID")
        expected=identity_for("QUALIFICATION_BUNDLE",self.canonical_payload())
        if self.bundle_identity and self.bundle_identity != expected: raise ValueError("QUALIFICATION_BUNDLE_IDENTITY_INVALID")
        object.__setattr__(self,"bundle_identity",expected)
    def canonical_payload(self): return {"candidate_registry_identity":self.candidate_registry.registry_identity,
        "evaluation_registry_identity":self.evaluation_registry.registry_identity,"qualification_registry_identity":self.qualification_registry.registry_identity,
        "candidate_identity":self.candidate.model_identity,"candidate_evidence_identity":self.candidate_evidence.evidence_identity,
        "evaluation_report_identity":self.evaluation_report.report_identity,"qualification_report_identity":self.qualification_report.report_identity,
        "qualification_evidence_identity":self.qualification_evidence.evidence_identity}

@dataclass(frozen=True)
class PromotionGate:
    gate: str; passed: bool; reason: str; evidence: Mapping[str,object]
    def __post_init__(self):
        if self.gate not in PROMOTION_GATES or type(self.passed) is not bool or self.reason != ("GATE_PASSED" if self.passed else "GATE_FAILED") or not isinstance(self.evidence,Mapping) or not self.evidence: raise ValueError("PROMOTION_GATE_INVALID")
        object.__setattr__(self,"evidence",freeze(dict(self.evidence)))

@dataclass(frozen=True)
class PromotionEvidence:
    qualification_bundle_identity: str; candidate_identity: str; qualification_report_identity: str
    qualification_registry_identity: str; promotion_policy_identity: str; gates: tuple[PromotionGate,...]; evidence_identity: str = ""
    def __post_init__(self):
        gates=tuple(self.gates)
        if not all(_text(getattr(self,x)) for x in ("qualification_bundle_identity","candidate_identity","qualification_report_identity","qualification_registry_identity","promotion_policy_identity")) or tuple(x.gate for x in gates)!=PROMOTION_GATES: raise ValueError("PROMOTION_EVIDENCE_INVALID")
        for x in gates: PromotionGate(x.gate,x.passed,x.reason,thaw(x.evidence))
        object.__setattr__(self,"gates",gates); expected=identity_for("PROMOTION_EVIDENCE",self.canonical_payload())
        if self.evidence_identity and self.evidence_identity!=expected: raise ValueError("PROMOTION_EVIDENCE_IDENTITY_INVALID")
        object.__setattr__(self,"evidence_identity",expected)
    def canonical_payload(self): return {"qualification_bundle_identity":self.qualification_bundle_identity,"candidate_identity":self.candidate_identity,
      "qualification_report_identity":self.qualification_report_identity,"qualification_registry_identity":self.qualification_registry_identity,
      "promotion_policy_identity":self.promotion_policy_identity,"gates":tuple({"gate":x.gate,"passed":x.passed,"reason":x.reason,"evidence":thaw(x.evidence)} for x in self.gates)}

@dataclass(frozen=True)
class PromotionReport:
    candidate_identity: str; qualification_bundle_identity: str; qualification_report_identity: str
    qualification_registry_identity: str; policy: PromotionPolicy; promotion_evidence: PromotionEvidence
    decision: str; governance_queue_eligible: bool; exception_review_required: bool; report_identity: str = ""
    schema_version: str = PROMOTION_SCHEMA_VERSION; advisory_only: bool = True; human_approved: bool = False
    deployment_authorized: bool = False; production_authorized: bool = False; runtime_authorized: bool = False; broker_authorized: bool = False
    def __post_init__(self):
        _validate(self.policy); _validate(self.promotion_evidence); failed={x.gate for x in self.promotion_evidence.gates if not x.passed}
        expected="ELIGIBLE" if not failed else "CONDITIONAL" if failed <= set(self.policy.conditional_gates) else "REJECTED"
        if (self.decision!=expected or self.decision not in PROMOTION_DECISIONS or self.governance_queue_eligible != (self.decision=="ELIGIBLE")
            or self.exception_review_required != (self.decision=="CONDITIONAL") or self.schema_version!=PROMOTION_SCHEMA_VERSION or self.advisory_only is not True
            or self.human_approved is not False or any((self.deployment_authorized,self.production_authorized,self.runtime_authorized,self.broker_authorized))
            or self.promotion_evidence.qualification_bundle_identity!=self.qualification_bundle_identity or self.promotion_evidence.candidate_identity!=self.candidate_identity
            or self.promotion_evidence.qualification_report_identity!=self.qualification_report_identity or self.promotion_evidence.qualification_registry_identity!=self.qualification_registry_identity
            or self.promotion_evidence.promotion_policy_identity!=self.policy.policy_identity): raise ValueError("PROMOTION_REPORT_INVALID")
        expected_id=identity_for("PROMOTION_REPORT",self.canonical_payload())
        if self.report_identity and self.report_identity!=expected_id: raise ValueError("PROMOTION_REPORT_IDENTITY_INVALID")
        object.__setattr__(self,"report_identity",expected_id)
    def canonical_payload(self): return {x:(self.policy.canonical_payload()|{"policy_identity":self.policy.policy_identity} if x=="policy" else self.promotion_evidence.canonical_payload()|{"evidence_identity":self.promotion_evidence.evidence_identity} if x=="promotion_evidence" else getattr(self,x)) for x in self.__dataclass_fields__ if x!="report_identity"}

@dataclass(frozen=True)
class PromotionApprovalRequest:
    report_identity: str; candidate_identity: str; promotion_policy_identity: str; human_approval_authority_identity: str
    governance_policy_identity: str; required_reviewer_role: str; review_routing_identity: str
    status: str = "PENDING_HUMAN_REVIEW"; request_identity: str = ""
    def __post_init__(self):
        if not all(_text(getattr(self,x)) for x in self.__dataclass_fields__ if x!="request_identity") or self.status!="PENDING_HUMAN_REVIEW": raise ValueError("PROMOTION_APPROVAL_REQUEST_INVALID")
        expected=identity_for("PROMOTION_APPROVAL_REQUEST",self.canonical_payload())
        if self.request_identity and self.request_identity!=expected: raise ValueError("PROMOTION_APPROVAL_REQUEST_IDENTITY_INVALID")
        object.__setattr__(self,"request_identity",expected)
    def canonical_payload(self): return {x:getattr(self,x) for x in self.__dataclass_fields__ if x!="request_identity"}

@dataclass(frozen=True)
class GovernanceQueueEntry:
    report_identity: str; approval_request_identity: str; candidate_identity: str; governance_policy_identity: str
    human_approval_authority_identity: str; required_reviewer_role: str; review_routing_identity: str
    queue_status: str = "AWAITING_HUMAN_REVIEW"; queue_identity: str = ""
    def __post_init__(self):
        if not all(_text(getattr(self,x)) for x in self.__dataclass_fields__ if x!="queue_identity") or self.queue_status!="AWAITING_HUMAN_REVIEW": raise ValueError("PROMOTION_GOVERNANCE_QUEUE_ENTRY_INVALID")
        expected=identity_for("PROMOTION_GOVERNANCE_QUEUE_ENTRY",self.canonical_payload())
        if self.queue_identity and self.queue_identity!=expected: raise ValueError("PROMOTION_GOVERNANCE_QUEUE_ENTRY_IDENTITY_INVALID")
        object.__setattr__(self,"queue_identity",expected)
    def canonical_payload(self): return {x:getattr(self,x) for x in self.__dataclass_fields__ if x!="queue_identity"}

@dataclass(frozen=True)
class PromotionResult:
    report: PromotionReport; approval_request: PromotionApprovalRequest|None; governance_queue_entry: GovernanceQueueEntry|None; result_identity: str = ""
    def __post_init__(self):
        _validate(self.report); eligible=self.report.decision=="ELIGIBLE"
        if eligible != (self.approval_request is not None and self.governance_queue_entry is not None): raise ValueError("PROMOTION_RESULT_INVALID")
        if eligible:
            _validate(self.approval_request); _validate(self.governance_queue_entry); p=self.report.policy
            routing_identity=identity_for("PROMOTION_REVIEW_ROUTING",{"qualification_bundle_identity":self.report.qualification_bundle_identity,
                "promotion_policy_identity":p.policy_identity,"human_approval_authority_identity":p.human_approval_authority_identity,
                "governance_policy_identity":p.governance_policy_identity,"required_reviewer_role":p.required_reviewer_role})
            if (self.approval_request.report_identity!=self.report.report_identity or self.governance_queue_entry.report_identity!=self.report.report_identity
                or self.governance_queue_entry.approval_request_identity!=self.approval_request.request_identity
                or self.approval_request.review_routing_identity!=routing_identity or self.governance_queue_entry.review_routing_identity!=routing_identity
                or any(getattr(self.approval_request,x)!=getattr(p,x) for x in ("human_approval_authority_identity","governance_policy_identity","required_reviewer_role"))
                or any(getattr(self.governance_queue_entry,x)!=getattr(p,x) for x in ("human_approval_authority_identity","governance_policy_identity","required_reviewer_role"))): raise ValueError("PROMOTION_RESULT_BINDING_INVALID")
        expected=identity_for("PROMOTION_RESULT",self.canonical_payload())
        if self.result_identity and self.result_identity!=expected: raise ValueError("PROMOTION_RESULT_IDENTITY_INVALID")
        object.__setattr__(self,"result_identity",expected)
    def canonical_payload(self): return {"report_identity":self.report.report_identity,"approval_request_identity":None if self.approval_request is None else self.approval_request.request_identity,"governance_queue_identity":None if self.governance_queue_entry is None else self.governance_queue_entry.queue_identity}
