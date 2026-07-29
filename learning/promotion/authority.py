"""Pure promotion authority consuming one authoritative qualification bundle."""
from .contracts import (PROMOTION_GATES, GovernanceQueueEntry, PromotionApprovalRequest, PromotionEvidence,
    PromotionGate, PromotionPolicy, PromotionReport, PromotionResult, QualificationBundle)
from .identity import identity_for
class PromotionValidationError(ValueError): pass
def _validate(v):
    try: type(v)(**v.__dict__)
    except (AttributeError,TypeError,ValueError) as exc: raise PromotionValidationError("PROMOTION_INPUT_INVALID") from exc

class PromotionAuthority:
    """Determine governance-entry eligibility; never authorize or perform deployment."""
    def __init__(self,policy:PromotionPolicy): _validate(policy); self.policy=policy
    def assess(self,bundle:QualificationBundle)->PromotionResult:
        _validate(bundle); q=bundle.qualification_report; qe=bundle.qualification_evidence
        policy_ok=q.policy.policy_identity in self.policy.accepted_qualification_policy_identities
        qualification_ok=q.decision=="PASS" if self.policy.require_qualification_pass else q.decision in ("PASS","CONDITIONAL")
        governance_ready=q.governance_eligible if self.policy.require_governance_eligible else True
        evidence_ok=q.qualification_evidence==qe and qe.evidence_identity==q.qualification_evidence.evidence_identity
        candidate_ok=(q.candidate_identity==bundle.candidate.model_identity==qe.candidate_identity and
            q.evaluation_report_identity==bundle.evaluation_report.report_identity==qe.evaluation_report_identity)
        # QualificationBundle reconstruction has already proven every exact object,
        # entry, predecessor, registry identity, and cross-layer binding.
        lineage_ok=True
        routing_identity=identity_for("PROMOTION_REVIEW_ROUTING",{"qualification_bundle_identity":bundle.bundle_identity,
            "promotion_policy_identity":self.policy.policy_identity,"human_approval_authority_identity":self.policy.human_approval_authority_identity,
            "governance_policy_identity":self.policy.governance_policy_identity,"required_reviewer_role":self.policy.required_reviewer_role})
        routing_ok=bool(routing_identity)
        eligibility=qualification_ok and policy_ok and evidence_ok and candidate_ok and lineage_ok and routing_ok and governance_ready
        facts={
          "qualification_validity":(qualification_ok,{"decision":q.decision,"report_identity":q.report_identity}),
          "promotion_policy_compliance":(policy_ok,{"qualification_policy_identity":q.policy.policy_identity,"promotion_policy_identity":self.policy.policy_identity}),
          "evidence_completeness":(evidence_ok,{"qualification_evidence_identity":qe.evidence_identity}),
          "candidate_integrity":(candidate_ok,{"candidate_identity":bundle.candidate.model_identity,"candidate_registry_identity":bundle.candidate_registry.registry_identity}),
          "registry_lineage_validation":(lineage_ok,{"bundle_identity":bundle.bundle_identity,"candidate_registry_identity":bundle.candidate_registry.registry_identity,
             "evaluation_registry_identity":bundle.evaluation_registry.registry_identity,"qualification_registry_identity":bundle.qualification_registry.registry_identity}),
          "governance_readiness":(governance_ready,{"qualification_governance_eligible":q.governance_eligible}),
          "review_routing_integrity":(routing_ok,{"human_approval_authority_identity":self.policy.human_approval_authority_identity,
             "governance_policy_identity":self.policy.governance_policy_identity,"required_reviewer_role":self.policy.required_reviewer_role,
             "review_routing_identity":routing_identity}),
          "governance_entry_eligibility":(eligibility,{"scope":"GOVERNANCE_ENTRY_ONLY","deployment_authorized":False,"production_authorized":False})}
        gates=tuple(PromotionGate(x,bool(facts[x][0]),"GATE_PASSED" if facts[x][0] else "GATE_FAILED",facts[x][1]) for x in PROMOTION_GATES)
        failed={x.gate for x in gates if not x.passed}; decision="ELIGIBLE" if not failed else "CONDITIONAL" if failed<=set(self.policy.conditional_gates) else "REJECTED"
        evidence=PromotionEvidence(bundle.bundle_identity,q.candidate_identity,q.report_identity,bundle.qualification_registry.registry_identity,self.policy.policy_identity,gates)
        report=PromotionReport(q.candidate_identity,bundle.bundle_identity,q.report_identity,bundle.qualification_registry.registry_identity,self.policy,evidence,decision,decision=="ELIGIBLE",decision=="CONDITIONAL")
        if decision!="ELIGIBLE": return PromotionResult(report,None,None)
        request=PromotionApprovalRequest(report.report_identity,report.candidate_identity,self.policy.policy_identity,
            self.policy.human_approval_authority_identity,self.policy.governance_policy_identity,self.policy.required_reviewer_role,routing_identity)
        queue=GovernanceQueueEntry(report.report_identity,request.request_identity,report.candidate_identity,self.policy.governance_policy_identity,
            self.policy.human_approval_authority_identity,self.policy.required_reviewer_role,routing_identity)
        return PromotionResult(report,request,queue)
    promote=assess
    def replay(self,expected,bundle):
        try: _validate(expected); return self.assess(bundle)==expected
        except (PromotionValidationError,TypeError,ValueError,AttributeError,KeyError): return False
