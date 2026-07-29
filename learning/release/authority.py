"""Final, non-executing Production Release Authority."""
from datetime import timedelta
from learning.deployment.contracts import _revalidate, _utc
from .contracts import RELEASE_GATES, ReleaseEvidence, ReleaseGate
from .governance import (AuthoritativeReleaseCertificate, AuthoritativeReleaseDecision,
    AuthoritativeReleaseManifest, AuthoritativeRuntimeActivationAuthorization,
    ProductionReleaseGovernanceBundle)

class ReleaseValidationError(ValueError): pass

class ProductionReleaseAuthority:
    """Authorize data for the existing V27 executor; never activate it."""
    def assess(self,bundle:ProductionReleaseGovernanceBundle)->AuthoritativeReleaseDecision:
        try:_revalidate(bundle)
        except (AttributeError,TypeError,ValueError) as exc: raise ReleaseValidationError("PRODUCTION_RELEASE_INPUT_INVALID") from exc
        result=bundle.deployment_result; entry=bundle.deployment_registry_entry
        registry=bundle.deployment_registry; report=result.report; manifest=result.manifest; request=result.release_request
        approval=bundle.human_approval_record; policy=bundle.release_policy; artifact=bundle.deployment_artifact
        final=bundle.final_governance_record; runtime=bundle.target_runtime_instance
        assessed=_utc(bundle.assessed_at)
        registry_matches=[x for x in registry.entries if x.entry_identity==entry.entry_identity and x==entry and x.result==result]
        superseded=any(x.supersedes_entry_identity==entry.entry_identity for x in registry.entries)
        deployment_ok=(len(registry_matches)==1 and not superseded and report.decision=="DEPLOYMENT GOVERNANCE ELIGIBLE"
            and manifest is not None and request is not None and all(g.passed for g in report.deployment_evidence.gates))
        approval_ok=(bundle.human_approval_registry.is_effective(approval) and approval.decision=="APPROVED"
            and approval.record_identity==report.approval_record_identity==request.human_approval_record_identity
            and _utc(approval.issued_at)<=assessed<_utc(approval.expires_at))
        policy_ok=(report.deployment_policy_identity in policy.accepted_deployment_policy_identities
            and request.release_authority_identity==manifest.release_authority_identity==policy.release_authority_identity
            and approval.required_reviewer_role==policy.required_approver_role)
        binding_ok=(request.manifest_identity==manifest.manifest_identity and manifest.readiness_report_identity==report.report_identity
            and request.readiness_report_identity==report.report_identity and request.artifact_identity==manifest.artifact_identity==report.artifact_identity
            and request.target_environment_identity==manifest.target_environment_identity==report.target_environment_identity
            and request.runtime_contract_identity==manifest.runtime_contract_identity==report.runtime_contract_identity)
        membership=bundle.artifact_registry_evidence
        artifact_ok=(artifact.artifact_identity==report.artifact_identity and artifact.candidate_identity==report.candidate_identity
            and artifact.target_environment_identity==report.target_environment_identity and artifact.runtime_contract_identity==report.runtime_contract_identity
            and membership.artifact_identity==artifact.artifact_identity and membership.content_hash==artifact.content_hash
            and membership.registry_kind=="DEPLOYMENT_ARTIFACT" and bool(membership.registry_identity and membership.entry_identity))
        runtime_ok=(runtime.target_environment_identity==report.target_environment_identity
            and runtime.runtime_contract_identity==report.runtime_contract_identity
            and runtime.runtime_contract_identity in policy.accepted_runtime_contract_identities)
        rollback=bundle.rollback_artifact; rollback_manifest=bundle.rollback_manifest; rollback_membership=bundle.rollback_registry_evidence
        rollback_ok=(rollback.target_artifact_identity==artifact.artifact_identity and rollback.runtime_contract_identity==runtime.runtime_contract_identity
            and rollback.executor_identity==runtime.executor_identity and rollback.executor_version==runtime.executor_version
            and rollback_manifest.rollback_artifact_identity==rollback.artifact_identity
            and rollback_manifest.target_artifact_identity==artifact.artifact_identity
            and rollback_manifest.target_environment_identity==runtime.target_environment_identity
            and rollback_manifest.runtime_contract_identity==runtime.runtime_contract_identity
            and rollback_manifest.executor_identity==runtime.executor_identity
            and rollback_membership.artifact_identity==rollback.artifact_identity
            and rollback_membership.content_hash==rollback.content_hash and rollback_membership.registry_kind=="ROLLBACK_ARTIFACT")
        final_ok=(bundle.final_governance_registry.is_effective(final) and final.decision=="APPROVED"
            and final.deployment_result_identity==result.result_identity and final.release_request_identity==request.request_identity
            and final.artifact_identity==artifact.artifact_identity and final.release_policy_identity==policy.policy_identity
            and final.authority_identity==policy.final_governance_authority_identity
            and _utc(final.issued_at)<=assessed<_utc(final.expires_at))
        facts={
          "deployment_readiness":(deployment_ok,{"deployment_result_identity":result.result_identity,"deployment_registry_identity":registry.registry_identity,"deployment_registry_entry_identity":entry.entry_identity}),
          "human_approval":(approval_ok,{"approval_record_identity":approval.record_identity,"approval_registry_identity":bundle.human_approval_registry.registry_identity}),
          "release_policy":(policy_ok,{"release_policy_identity":policy.policy_identity}),
          "release_manifest_integrity":(binding_ok,{"deployment_manifest_identity":manifest.manifest_identity if manifest else "MISSING","release_request_identity":request.request_identity if request else "MISSING"}),
          "artifact_integrity":(artifact_ok,{"artifact_identity":artifact.artifact_identity,"artifact_registry_evidence_identity":membership.evidence_identity}),
          "runtime_compatibility":(runtime_ok,{"runtime_instance_identity":runtime.instance_identity,"executor_identity":runtime.executor_identity,"executor_version":runtime.executor_version}),
          "rollback_readiness":(rollback_ok,{"rollback_artifact_identity":rollback.artifact_identity,"rollback_manifest_identity":rollback_manifest.manifest_identity,"rollback_registry_evidence_identity":rollback_membership.evidence_identity}),
          "final_governance_certification":(final_ok,{"final_governance_record_identity":final.record_identity,"final_governance_registry_identity":bundle.final_governance_registry.registry_identity})}
        gates=tuple(ReleaseGate(x,bool(facts[x][0]),"GATE_PASSED" if facts[x][0] else "GATE_FAILED",facts[x][1]) for x in RELEASE_GATES)
        evidence=ReleaseEvidence(bundle.bundle_identity,gates)
        if not all(g.passed for g in gates): return AuthoritativeReleaseDecision(evidence,"PRODUCTION_RELEASE_REJECTED")
        cert=AuthoritativeReleaseCertificate(result.result_identity,entry.entry_identity,report.candidate_identity,
            artifact.artifact_identity,report.promotion_report_identity,report.deployment_policy_identity,
            approval.governance_policy_identity,approval.review_routing_identity,approval.record_identity,
            request.request_identity,manifest.manifest_identity,policy.policy_identity,policy.release_authority_identity,
            final.record_identity,final.authority_identity,runtime.target_environment_identity,runtime.runtime_contract_identity,
            runtime.instance_identity,runtime.executor_identity,runtime.executor_version,runtime.activation_generation,
            rollback_manifest.manifest_identity,evidence,bundle.assessed_at)
        release_manifest=AuthoritativeReleaseManifest(cert.certificate_identity,artifact.artifact_identity,policy.policy_identity,
            runtime.target_environment_identity,runtime.runtime_contract_identity,runtime.instance_identity,runtime.executor_identity,
            runtime.executor_version,runtime.activation_generation,rollback_manifest.manifest_identity)
        valid_until=(assessed+timedelta(seconds=900)).strftime("%Y-%m-%dT%H:%M:%SZ")
        activation=AuthoritativeRuntimeActivationAuthorization(cert.certificate_identity,release_manifest.manifest_identity,
            artifact.artifact_identity,policy.policy_identity,runtime.executor_identity,runtime.executor_version,
            runtime.instance_identity,runtime.target_environment_identity,runtime.runtime_contract_identity,
            runtime.activation_generation,bundle.assessed_at,valid_until)
        return AuthoritativeReleaseDecision(evidence,"PRODUCTION_RELEASE_AUTHORIZED",cert,release_manifest,activation)
    authorize=assess; certify=assess
    def replay(self,expected,bundle):
        try:return self.assess(bundle)==expected
        except (ReleaseValidationError,AttributeError,TypeError,ValueError):return False
