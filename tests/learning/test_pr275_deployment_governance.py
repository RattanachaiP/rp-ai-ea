"""PR275 deployment-governance authority and fail-closed boundary tests."""
from dataclasses import replace
import pytest
from learning.deployment import (DeploymentGovernanceAuthority, DeploymentPolicy,
    DeploymentRegistry, HumanApprovalRecord)
from learning.promotion import PromotionAuthority, PromotionRegistry
from tests.learning.test_pr274_governed_promotion import policy, qualified_bundle as bundle_fixture

@pytest.fixture(scope="module")
def promoted():
    bundle=bundle_fixture.__wrapped__()
    result=PromotionAuthority(policy(bundle)).assess(bundle)
    return PromotionRegistry().append(result),result

def deployment_policy(result):
    return DeploymentPolicy("deployment-v1",(result.report.policy.policy_identity,),
        result.report.policy.human_approval_authority_identity,"MODEL_RELEASE_REVIEWER","production-release-authority-v1")

def approval(result,**changes):
    values=dict(promotion_report_identity=result.report.report_identity,
        approval_request_identity=result.approval_request.request_identity,
        candidate_identity=result.report.candidate_identity,
        approval_authority_identity=result.report.policy.human_approval_authority_identity,
        approver_identity="human-reviewer-42",approver_role="MODEL_RELEASE_REVIEWER",
        artifact_identity=result.report.candidate_identity,decision="APPROVED",approved_at="2026-07-29T00:00:00Z")
    values.update(changes); return HumanApprovalRecord(**values)

def test_eight_gates_outputs_and_deterministic_replay(promoted):
    registry,promotion=promoted; authority=DeploymentGovernanceAuthority(deployment_policy(promotion))
    result=authority.assess(registry,promotion.report,promotion.report.promotion_evidence,approval(promotion))
    assert result.report.decision=="DEPLOYMENT ELIGIBLE"
    assert tuple(x.gate for x in result.report.deployment_evidence.gates)==(
        "promotion_eligibility","human_approval_validation","deployment_policy_validation",
        "evidence_completeness","registry_lineage_validation","artifact_integrity",
        "release_readiness","governance_certification")
    assert all(x.passed for x in result.report.deployment_evidence.gates)
    assert result.manifest and result.release_request and authority.replay(result,registry,promotion.report,promotion.report.promotion_evidence,approval(promotion))
    assert result.release_request.status=="PENDING_PRODUCTION_RELEASE_AUTHORITY"
    assert not result.manifest.activation_permitted and not result.report.deployment_performed
    assert not result.report.production_released and not result.report.trades_executed

@pytest.mark.parametrize("change",[
    {"decision":"REJECTED"},{"approval_request_identity":"missing"},
    {"approval_authority_identity":"other"},{"approver_role":"other"},
    {"artifact_identity":"forged-artifact"}])
def test_missing_or_invalid_mandatory_authority_fails_closed(promoted,change):
    registry,promotion=promoted
    result=DeploymentGovernanceAuthority(deployment_policy(promotion)).assess(
        registry,promotion.report,promotion.report.promotion_evidence,approval(promotion,**change))
    assert result.report.decision=="DEPLOYMENT REJECTED"
    assert not result.report.governance_certified and result.manifest is None and result.release_request is None

def test_missing_evidence_approval_or_registry_fails_closed(promoted):
    registry,promotion=promoted; authority=DeploymentGovernanceAuthority(deployment_policy(promotion))
    for inputs in ((registry,promotion.report,None,approval(promotion)),
            (registry,promotion.report,promotion.report.promotion_evidence,None),
            (None,promotion.report,promotion.report.promotion_evidence,approval(promotion))):
        result=authority.assess(*inputs)
        assert result.report.decision=="DEPLOYMENT REJECTED"
        assert result.manifest is None and result.release_request is None

def test_policy_evidence_lineage_and_identity_forgery_fail_closed(promoted):
    registry,promotion=promoted
    wrong=DeploymentPolicy("other",("unknown-promotion-policy",),"human-authority-v1",
        "MODEL_RELEASE_REVIEWER","production-release-authority-v1")
    rejected=DeploymentGovernanceAuthority(wrong).assess(registry,promotion.report,
        promotion.report.promotion_evidence,approval(promotion))
    assert rejected.report.decision=="DEPLOYMENT REJECTED"
    with pytest.raises(ValueError,match="IDENTITY"):
        replace(approval(promotion),record_identity="0"*64)
    with pytest.raises(ValueError,match="PREDECESSOR"):
        replace(registry,previous_registry_identity="forged",registry_identity="")

def test_deployment_registry_is_immutable_and_replay_safe(promoted):
    promotion_registry,promotion=promoted
    result=DeploymentGovernanceAuthority(deployment_policy(promotion)).assess(promotion_registry,
        promotion.report,promotion.report.promotion_evidence,approval(promotion))
    registry=DeploymentRegistry().append(result)
    assert registry.append(result) is registry
    with pytest.raises(ValueError,match="PREDECESSOR"):
        replace(registry,previous_registry_identity="forged",registry_identity="")
    rejected=DeploymentGovernanceAuthority(DeploymentPolicy("bad",("bad",),"human-authority-v1",
        "MODEL_RELEASE_REVIEWER","production-release-authority-v1")).assess(promotion_registry,
        promotion.report,promotion.report.promotion_evidence,approval(promotion))
    with pytest.raises(ValueError,match="NOT_REGISTRABLE"): DeploymentRegistry().append(rejected)
