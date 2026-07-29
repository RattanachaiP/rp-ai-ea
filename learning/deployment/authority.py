"""Pure, fail-closed Deployment Governance Authority."""
from .contracts import (DEPLOYMENT_GATES, DeploymentEvidence, DeploymentGate,
    DeploymentManifest, DeploymentPolicy, DeploymentReadinessReport, DeploymentResult,
    HumanApprovalRecord, ReleaseRequest)

class DeploymentValidationError(ValueError): pass
def _valid(value):
    try: type(value)(**value.__dict__)
    except (AttributeError,TypeError,ValueError) as exc: raise DeploymentValidationError("DEPLOYMENT INPUT INVALID") from exc

class DeploymentGovernanceAuthority:
    """Certify readiness and request release; never perform production release."""
    def __init__(self,policy:DeploymentPolicy): _valid(policy); self.policy=policy
    def assess(self,promotion_registry,promotion_report,promotion_evidence,human_approval:HumanApprovalRecord):
        _valid(promotion_report)
        for value in (promotion_registry,promotion_evidence,human_approval):
            if value is not None: _valid(value)
        registry_entries=() if promotion_registry is None else promotion_registry.entries
        registry_identity="MISSING" if promotion_registry is None else promotion_registry.registry_identity
        evidence_identity="MISSING" if promotion_evidence is None else promotion_evidence.evidence_identity
        approval_identity="MISSING" if human_approval is None else human_approval.record_identity
        artifact_identity="MISSING" if human_approval is None else human_approval.artifact_identity
        matches=tuple(x for x in registry_entries if x.result.report.report_identity==promotion_report.report_identity)
        registry_ok=len(matches)==1 and matches[0].result.report==promotion_report
        entry_identity=matches[0].entry_identity if registry_ok else "MISSING"
        promotion_ok=promotion_report.decision=="ELIGIBLE" and promotion_report.governance_queue_eligible
        evidence_ok=(promotion_evidence is not None and promotion_report.promotion_evidence==promotion_evidence
            and evidence_identity==promotion_report.promotion_evidence.evidence_identity
            and all(x.passed for x in promotion_evidence.gates))
        policy_ok=promotion_report.policy.policy_identity in self.policy.accepted_promotion_policy_identities
        request=matches[0].result.approval_request if registry_ok else None
        approval_ok=(request is not None and human_approval is not None and human_approval.decision=="APPROVED"
            and human_approval.promotion_report_identity==promotion_report.report_identity
            and human_approval.approval_request_identity==request.request_identity
            and human_approval.candidate_identity==promotion_report.candidate_identity
            and human_approval.approval_authority_identity==self.policy.approval_authority_identity
            and human_approval.approver_role==self.policy.required_approver_role)
        artifact_ok=artifact_identity==promotion_report.candidate_identity
        lineage_ok=bool(registry_ok and registry_identity != "MISSING" and entry_identity!="MISSING")
        readiness=promotion_ok and approval_ok and policy_ok and evidence_ok and lineage_ok and artifact_ok
        facts={
          "promotion_eligibility":(promotion_ok,{"promotion_decision":promotion_report.decision}),
          "human_approval_validation":(approval_ok,{"approval_record_identity":approval_identity}),
          "deployment_policy_validation":(policy_ok,{"deployment_policy_identity":self.policy.policy_identity}),
          "evidence_completeness":(evidence_ok,{"promotion_evidence_identity":evidence_identity}),
          "registry_lineage_validation":(lineage_ok,{"promotion_registry_identity":registry_identity,"entry_identity":entry_identity}),
          "artifact_integrity":(artifact_ok,{"candidate_identity":promotion_report.candidate_identity,"artifact_identity":artifact_identity}),
          "release_readiness":(readiness,{"release_authority_identity":self.policy.release_authority_identity}),
          "governance_certification":(readiness,{"scope":"READINESS_CERTIFICATION_ONLY","production_release_performed":False,"trades_executed":False})}
        gates=tuple(DeploymentGate(x,bool(facts[x][0]),"GATE_PASSED" if facts[x][0] else "GATE_FAILED",facts[x][1]) for x in DEPLOYMENT_GATES)
        evidence=DeploymentEvidence(registry_identity,entry_identity,promotion_report.report_identity,
            evidence_identity,approval_identity,self.policy.policy_identity,
            promotion_report.candidate_identity,artifact_identity,gates)
        eligible=all(x.passed for x in gates)
        report=DeploymentReadinessReport(promotion_report.candidate_identity,artifact_identity,
            self.policy,evidence,"DEPLOYMENT ELIGIBLE" if eligible else "DEPLOYMENT REJECTED",governance_certified=eligible,release_ready=eligible)
        if not eligible: return DeploymentResult(report,None,None)
        manifest=DeploymentManifest(report.report_identity,report.candidate_identity,report.artifact_identity,
            promotion_report.report_identity,self.policy.policy_identity)
        release=ReleaseRequest(report.report_identity,manifest.manifest_identity,report.candidate_identity,
            report.artifact_identity,self.policy.release_authority_identity)
        return DeploymentResult(report,manifest,release)
    certify=assess
    def replay(self,expected,*inputs):
        try: _valid(expected); return self.assess(*inputs)==expected
        except (DeploymentValidationError,TypeError,ValueError,AttributeError,KeyError): return False
