"""Pure, offline, advisory-only Deployment Governance Authority."""
from datetime import timedelta
from .contracts import (DEPLOYMENT_GATES, DeploymentEvidence, DeploymentGate,
    DeploymentGovernanceBundle, DeploymentManifest, DeploymentReadinessReport,
    DeploymentResult, ReleaseRequest, _revalidate, _utc)

class DeploymentValidationError(ValueError): pass

class DeploymentGovernanceAuthority:
    """Certify governance eligibility; never authorize or perform a release."""
    def assess(self,bundle:DeploymentGovernanceBundle)->DeploymentResult:
        try: _revalidate(bundle)
        except (AttributeError,TypeError,ValueError) as exc: raise DeploymentValidationError("DEPLOYMENT_INPUT_INVALID") from exc
        result=bundle.promotion_result; report=result.report; request=result.approval_request
        queue=bundle.governance_queue_entry; approval=bundle.human_approval_record
        artifact=bundle.deployment_artifact; environment=bundle.target_environment; policy=bundle.deployment_policy
        promotion_ok=(report.decision=="ELIGIBLE" and report.governance_queue_eligible and request is not None
            and queue==result.governance_queue_entry and report.promotion_evidence==result.report.promotion_evidence)
        routing_ok=(request is not None and approval.promotion_report_identity==report.report_identity
            and approval.approval_request_identity==request.request_identity
            and approval.promotion_policy_identity==report.policy.policy_identity
            and approval.governance_policy_identity==request.governance_policy_identity==queue.governance_policy_identity==policy.governance_policy_identity
            and approval.review_routing_identity==request.review_routing_identity==queue.review_routing_identity
            and approval.approval_authority_identity==request.human_approval_authority_identity==queue.human_approval_authority_identity==policy.approval_authority_identity
            and approval.required_reviewer_role==request.required_reviewer_role==queue.required_reviewer_role==policy.required_approver_role
            and approval.candidate_identity==report.candidate_identity)
        assessed,issued,expires=_utc(bundle.assessed_at),_utc(approval.issued_at),_utc(approval.expires_at)
        temporal_ok=issued <= assessed < expires and assessed-issued <= timedelta(seconds=policy.maximum_approval_age_seconds)
        approval_ok=(routing_ok and approval.decision=="APPROVED" and temporal_ok
            and bundle.human_approval_registry.is_effective(approval))
        policy_ok=(report.policy.policy_identity in policy.accepted_promotion_policy_identities
            and environment.environment_class in policy.permitted_environment_classes
            and environment.runtime_contract_identity in policy.accepted_runtime_contract_identities)
        evidence_ok=all(x.passed for x in report.promotion_evidence.gates)
        registry_ok=bool(bundle.promotion_registry.registry_identity and bundle.governance_queue_registry.registry_identity
            and bundle.human_approval_registry.registry_identity)
        artifact_ok=(artifact.candidate_identity==report.candidate_identity
            and artifact.target_environment_identity==environment.environment_identity
            and artifact.runtime_contract_identity==environment.runtime_contract_identity)
        release_routing_ok=(routing_ok and policy.release_authority_identity and environment.environment_class in policy.permitted_environment_classes)
        preliminary=all((promotion_ok,approval_ok,policy_ok,evidence_ok,registry_ok,artifact_ok,release_routing_ok))
        manifest_binding_ok=preliminary
        facts={
          "promotion_eligibility":(promotion_ok,{"promotion_report_identity":report.report_identity}),
          "human_approval_validation":(approval_ok,{"approval_record_identity":approval.record_identity,"approval_registry_identity":bundle.human_approval_registry.registry_identity,"assessed_at":bundle.assessed_at}),
          "deployment_policy_validation":(policy_ok,{"deployment_policy_identity":policy.policy_identity,"environment_class":environment.environment_class}),
          "evidence_completeness":(evidence_ok,{"promotion_evidence_identity":report.promotion_evidence.evidence_identity}),
          "registry_lineage_validation":(registry_ok,{"promotion_registry_identity":bundle.promotion_registry.registry_identity,"governance_queue_registry_identity":bundle.governance_queue_registry.registry_identity}),
          "artifact_integrity":(artifact_ok,{"artifact_identity":artifact.artifact_identity,"content_hash":artifact.content_hash,"model_hash":artifact.model_hash,"build_provenance_identity":artifact.build_provenance_identity}),
          "release_routing_integrity":(release_routing_ok,{"review_routing_identity":approval.review_routing_identity,"release_authority_identity":policy.release_authority_identity}),
          "manifest_binding_integrity":(manifest_binding_ok,{"target_environment_identity":environment.environment_identity,"runtime_contract_identity":environment.runtime_contract_identity,"scope":"ADVISORY_ONLY"})}
        gates=tuple(DeploymentGate(x,bool(facts[x][0]),"GATE_PASSED" if facts[x][0] else "GATE_FAILED",facts[x][1]) for x in DEPLOYMENT_GATES)
        evidence=DeploymentEvidence(bundle.bundle_identity,report.report_identity,approval.record_identity,
            artifact.artifact_identity,environment.environment_identity,environment.runtime_contract_identity,policy.policy_identity,gates)
        eligible=all(x.passed for x in gates)
        readiness=DeploymentReadinessReport(report.candidate_identity,artifact.artifact_identity,report.report_identity,
            approval.record_identity,environment.environment_identity,environment.runtime_contract_identity,
            policy.policy_identity,evidence,"DEPLOYMENT GOVERNANCE ELIGIBLE" if eligible else "DEPLOYMENT REJECTED",
            governance_certified=eligible,release_governance_eligible=eligible)
        if not eligible: return DeploymentResult(readiness,None,None)
        manifest=DeploymentManifest(readiness.report_identity,report.candidate_identity,artifact.artifact_identity,
            report.report_identity,approval.record_identity,policy.policy_identity,environment.environment_identity,
            environment.runtime_contract_identity,policy.release_authority_identity)
        release=ReleaseRequest(readiness.report_identity,manifest.manifest_identity,report.candidate_identity,
            artifact.artifact_identity,policy.policy_identity,report.report_identity,approval.record_identity,
            approval.governance_policy_identity,approval.review_routing_identity,environment.environment_identity,
            environment.runtime_contract_identity,policy.release_authority_identity)
        return DeploymentResult(readiness,manifest,release)
    certify=assess
    def replay(self,expected,bundle):
        try: _revalidate(expected); return self.assess(bundle)==expected
        except (DeploymentValidationError,TypeError,ValueError,AttributeError,KeyError): return False
