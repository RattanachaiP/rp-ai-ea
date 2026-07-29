"""PR275 production-boundary evidence-chain and adversarial tests."""
from dataclasses import replace
import hashlib
import pytest
from learning.deployment import (DeploymentArtifact, DeploymentGovernanceAuthority,
    DeploymentGovernanceBundle, DeploymentPolicy, DeploymentRegistry, HumanApprovalRecord,
    HumanApprovalRegistry, ReleaseRequest, TargetEnvironment)
from learning.promotion import GovernanceQueueRegistry, PromotionAuthority, PromotionRegistry
from tests.learning.test_pr274_governed_promotion import policy as promotion_policy, qualified_bundle as qualified_fixture

@pytest.fixture(scope="module")
def promoted():
    upstream=qualified_fixture.__wrapped__(); result=PromotionAuthority(promotion_policy(upstream)).assess(upstream)
    return result,PromotionRegistry().append(result),GovernanceQueueRegistry().append(result.governance_queue_entry)

def components(promoted,**changes):
    result,promotions,queues=promoted; runtime="runtime-contract-v27-production"
    environment=changes.pop("environment",TargetEnvironment("primary-v27","LIVE_PRODUCTION",runtime))
    policy=changes.pop("policy",DeploymentPolicy("deployment-v2",(result.report.policy.policy_identity,),
        result.report.policy.human_approval_authority_identity,"MODEL_RELEASE_REVIEWER",
        result.report.policy.governance_policy_identity,"production-release-authority-v1",
        ("LIVE_PRODUCTION",),(runtime,),3600))
    request=result.approval_request
    approval=changes.pop("approval",HumanApprovalRecord(result.report.report_identity,request.request_identity,
        result.report.policy.policy_identity,request.governance_policy_identity,request.review_routing_identity,
        result.report.candidate_identity,request.human_approval_authority_identity,"reviewer-42",
        request.required_reviewer_role,"APPROVED","2026-07-29T09:00:00Z","2026-07-29T10:00:00Z"))
    approvals=changes.pop("approvals",HumanApprovalRegistry().append(approval))
    model_hash=hashlib.sha256(result.report.candidate_identity.encode()).hexdigest()
    compatibility={"model_hash":model_hash,"build_provenance_identity":"build-attestation-275",
        "target_environment_identity":environment.environment_identity,"runtime_contract_identity":runtime}
    artifact=changes.pop("artifact",DeploymentArtifact(result.report.candidate_identity,
        hashlib.sha256(b"immutable-package").hexdigest(),model_hash,"build-attestation-275",
        compatibility,environment.environment_identity,runtime))
    values=dict(promotion_result=result,promotion_registry=promotions,
        governance_queue_entry=result.governance_queue_entry,governance_queue_registry=queues,
        human_approval_record=approval,human_approval_registry=approvals,deployment_artifact=artifact,
        target_environment=environment,deployment_policy=policy,assessed_at="2026-07-29T09:30:00Z")
    values.update(changes); return values

def bundle(promoted,**changes): return DeploymentGovernanceBundle(**components(promoted,**changes))

def test_exact_authoritative_bundle_eight_distinct_gates_and_outputs(promoted):
    value=bundle(promoted); authority=DeploymentGovernanceAuthority(); result=authority.assess(value)
    assert result.report.decision=="DEPLOYMENT GOVERNANCE ELIGIBLE" and authority.replay(result,value)
    assert tuple(x.gate for x in result.report.deployment_evidence.gates)==(
        "promotion_eligibility","human_approval_validation","deployment_policy_validation",
        "evidence_completeness","registry_lineage_validation","artifact_integrity",
        "release_routing_integrity","manifest_binding_integrity")
    assert result.report.release_governance_eligible and result.manifest and result.release_request
    assert result.manifest.artifact_identity != result.manifest.candidate_identity
    assert not result.manifest.activation_permitted
    assert not any((result.release_request.production_release_authorized,
        result.release_request.runtime_activation_authorized,result.release_request.broker_access_authorized,
        result.release_request.trade_execution_authorized))

def test_approval_is_bound_to_exact_request_policy_governance_route_and_role(promoted):
    base=components(promoted); approval=base["human_approval_record"]
    for field in ("approval_request_identity","promotion_policy_identity","governance_policy_identity",
            "review_routing_identity","approval_authority_identity","required_reviewer_role"):
        forged=replace(approval,**{field:"forged"},record_identity="")
        rejected=DeploymentGovernanceAuthority().assess(bundle(promoted,approval=forged,
            approvals=HumanApprovalRegistry().append(forged)))
        assert rejected.report.decision=="DEPLOYMENT REJECTED"

def test_queue_absence_and_cross_object_forgery_are_rejected_at_bundle_boundary(promoted):
    values=components(promoted)
    with pytest.raises(ValueError,match="BUNDLE_BINDING"):
        DeploymentGovernanceBundle(**(values|{"governance_queue_registry":GovernanceQueueRegistry()}))
    with pytest.raises(ValueError,match="BUNDLE_BINDING"):
        DeploymentGovernanceBundle(**(values|{"promotion_registry":PromotionRegistry()}))

def test_artifact_hash_build_compatibility_and_environment_mismatch(promoted):
    values=components(promoted); artifact=values["deployment_artifact"]
    with pytest.raises(ValueError,match="ARTIFACT_INVALID"):
        replace(artifact,content_hash="not-a-hash",artifact_identity="")
    forged=dict(artifact.compatibility_evidence); forged["build_provenance_identity"]="other-build"
    with pytest.raises(ValueError,match="COMPATIBILITY"):
        replace(artifact,compatibility_evidence=forged,artifact_identity="")
    other=TargetEnvironment("demo","DEMO",artifact.runtime_contract_identity)
    rejected=DeploymentGovernanceAuthority().assess(bundle(promoted,environment=other,artifact=artifact))
    assert rejected.report.decision=="DEPLOYMENT REJECTED"

def test_expired_noncanonical_replayed_and_revoked_approvals_fail_closed(promoted):
    with pytest.raises(ValueError,match="NON_CANONICAL"):
        replace(components(promoted)["human_approval_record"],issued_at="2026-07-29T09:00:00+00:00",record_identity="")
    expired=DeploymentGovernanceAuthority().assess(bundle(promoted,assessed_at="2026-07-29T10:00:00Z"))
    assert expired.report.decision=="DEPLOYMENT REJECTED"
    approval=components(promoted)["human_approval_record"]; registry=HumanApprovalRegistry().append(approval)
    with pytest.raises(ValueError,match="REPLAY"): registry.append(approval)
    revoked=replace(approval,decision="REVOKED",issued_at="2026-07-29T09:40:00Z",
        expires_at="2026-07-29T10:40:00Z",supersedes_record_identity=approval.record_identity,record_identity="")
    revoked_registry=registry.append(revoked)
    rejected=DeploymentGovernanceAuthority().assess(bundle(promoted,approvals=revoked_registry))
    assert rejected.report.decision=="DEPLOYMENT REJECTED"

def test_release_authority_and_cross_artifact_binding_forgery(promoted):
    result=DeploymentGovernanceAuthority().assess(bundle(promoted))
    with pytest.raises(ValueError,match="RELEASE_REQUEST_IDENTITY"):
        replace(result.release_request,release_authority_identity="attacker",request_identity=result.release_request.request_identity)
    with pytest.raises(ValueError,match="RESULT_BINDING"):
        forged=replace(result.release_request,artifact_identity="0"*64,request_identity="")
        replace(result,release_request=forged,result_identity="")
    with pytest.raises(ValueError,match="RELEASE_REQUEST_INVALID"):
        replace(result.release_request,production_release_authorized=True,request_identity="")

def test_registry_composite_key_requires_explicit_supersession(promoted):
    result=DeploymentGovernanceAuthority().assess(bundle(promoted)); registry=DeploymentRegistry().append(result)
    assert registry.append(result) is registry
    successor=DeploymentGovernanceAuthority().assess(bundle(promoted,assessed_at="2026-07-29T09:31:00Z"))
    with pytest.raises(ValueError,match="REQUIRES_SUPERSESSION"): registry.append(successor)
    superseded=registry.append(successor,registry.entries[-1].entry_identity)
    assert superseded.entries[-1].supersedes_entry_identity==registry.entries[-1].entry_identity
    with pytest.raises(ValueError,match="NOT_REGISTRABLE"):
        rejected=DeploymentGovernanceAuthority().assess(bundle(promoted,assessed_at="2026-07-29T10:00:00Z"))
        DeploymentRegistry().append(rejected)
