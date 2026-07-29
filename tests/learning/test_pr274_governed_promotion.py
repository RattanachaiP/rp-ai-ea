"""PR274 authoritative promotion-boundary and adversarial tests."""
from dataclasses import replace
import pytest
from learning.evaluation import EvaluationRegistry
from learning.evaluation.models import qualification
from learning.promotion import (GovernanceQueueRegistry,PromotionAuthority,PromotionGate,PromotionPolicy,
    PromotionRegistry,PromotionResult,QualificationBundle)
from learning.qualification import QualificationRegistry
from tests.learning.test_pr273_candidate_qualification import (authority as qualification_authority,
    evaluated as evaluated_fixture,inputs as qualification_inputs)

@pytest.fixture(scope="module")
def qualified_bundle():
    evaluated=evaluated_fixture.__wrapped__(); original=evaluated[-1]; stats=original.statistical_validation
    governed_stats=replace(stats,record_count=30,error_sum=stats.error_sum*30,
        squared_error_sum=stats.squared_error_sum*30,regime_counts={next(iter(stats.regime_counts)):30})
    reasons=qualification(original.policy,governed_stats,original.dimensions)[1]
    er=replace(original,statistical_validation=governed_stats,qualification_reasons=reasons,report_identity="")
    values,candidates,result,_,_=evaluated; evaluations=EvaluationRegistry().append(er)
    evaluated=(values,candidates,result,evaluations,er)
    qa,evidence_registry,qe=qualification_authority(evaluated,conditional=(),require=False)
    qr=qa.qualify(*qualification_inputs(evaluated,evidence_registry,qe))
    assert qr.decision=="PASS" and qr.governance_eligible
    return QualificationBundle(candidates,evaluations,QualificationRegistry().append(qr),result.candidate,result.evidence,er,qr,qe)

def policy(bundle,**changes):
    accepted=changes.pop("accepted_qualification_policy_identities",(bundle.qualification_report.policy.policy_identity,))
    return PromotionPolicy("promotion-v2",accepted,"human-authority-v1","deployment-governance-v1","MODEL_RELEASE_REVIEWER",**changes)

def conditional_bundle():
    evaluated=evaluated_fixture.__wrapped__(); qa,evidence_registry,qe=qualification_authority(evaluated)
    qr=qa.qualify(*qualification_inputs(evaluated,evidence_registry,qe))
    assert qr.decision=="CONDITIONAL" and not qr.governance_eligible
    values,candidates,result,evaluations,er=evaluated
    return QualificationBundle(candidates,evaluations,QualificationRegistry().append(qr),result.candidate,result.evidence,er,qr,qe)

def test_exact_bundle_eight_gates_replay_result_identity_and_queue(qualified_bundle):
    authority=PromotionAuthority(policy(qualified_bundle)); result=authority.assess(qualified_bundle)
    assert result.report.decision=="ELIGIBLE" and authority.replay(result,qualified_bundle)
    assert result.result_identity and result.report.governance_queue_eligible
    assert result.approval_request.human_approval_authority_identity=="human-authority-v1"
    assert result.governance_queue_entry.required_reviewer_role=="MODEL_RELEASE_REVIEWER"
    assert not result.report.deployment_authorized and not result.report.production_authorized

def test_exact_upstream_object_and_reconstructed_registry_binding(qualified_bundle):
    with pytest.raises(ValueError,match="BUNDLE_BINDING"):
        replace(qualified_bundle,qualification_registry=QualificationRegistry(),bundle_identity="")
    entry=qualified_bundle.qualification_registry.entries[0]
    with pytest.raises(ValueError,match="ANCESTRY|ENTRY"):
        replace(qualified_bundle.qualification_registry,entries=(replace(entry,sequence=2,entry_identity=""),),registry_identity="")

def test_conditional_uses_exception_path_and_never_governance_queue(qualified_bundle):
    bundle=conditional_bundle()
    result=PromotionAuthority(policy(bundle,conditional_gates=("governance_readiness","governance_entry_eligibility"),require_qualification_pass=False)).assess(bundle)
    assert result.report.decision=="CONDITIONAL" and result.report.exception_review_required
    assert not result.report.governance_queue_eligible and result.approval_request is None and result.governance_queue_entry is None
    rejected_policy=policy(qualified_bundle,accepted_qualification_policy_identities=("other",))
    rejected=PromotionAuthority(rejected_policy).assess(qualified_bundle)
    assert rejected.report.decision=="REJECTED" and rejected.approval_request is None

def test_registry_and_queue_are_append_only_replay_safe_and_identity_bound(qualified_bundle):
    result=PromotionAuthority(policy(qualified_bundle)).assess(qualified_bundle)
    promotions=PromotionRegistry().append(result); assert promotions.append(result) is promotions
    queue=GovernanceQueueRegistry().append(result.governance_queue_entry)
    with pytest.raises(ValueError,match="DUPLICATE_GOVERNANCE_ENQUEUE"): queue.append(result.governance_queue_entry)
    with pytest.raises(ValueError,match="PREDECESSOR"): replace(queue,previous_registry_identity="forged",registry_identity="")
    with pytest.raises(ValueError,match="RESULT_BINDING|REQUEST_IDENTITY"):
        forged=replace(result.approval_request,required_reviewer_role="ATTACKER",request_identity="")
        replace(result,approval_request=forged,result_identity="")

    other=PromotionAuthority(PromotionPolicy("promotion-v2-other",(qualified_bundle.qualification_report.policy.policy_identity,),
        "human-authority-v1","deployment-governance-v2","MODEL_RELEASE_REVIEWER")).assess(qualified_bundle)
    two=queue.append(other.governance_queue_entry)
    with pytest.raises(ValueError,match="LINEAGE"):
        replace(two,entries=tuple(reversed(two.entries)),previous_registry_identity=None,registry_identity="")

def test_queue_result_and_gate_forgery_fail_closed(qualified_bundle):
    result=PromotionAuthority(policy(qualified_bundle)).assess(qualified_bundle)
    with pytest.raises(ValueError,match="RESULT_BINDING|QUEUE_ENTRY_IDENTITY"):
        forged=replace(result.governance_queue_entry,governance_policy_identity="forged",queue_identity="")
        replace(result,governance_queue_entry=forged,result_identity="")
    with pytest.raises(ValueError,match="RESULT_IDENTITY"): replace(result,result_identity="0"*64)
    rejected=PromotionAuthority(policy(qualified_bundle,accepted_qualification_policy_identities=("other",))).assess(qualified_bundle)
    with pytest.raises(ValueError,match="RESULT_INVALID"):
        replace(rejected,approval_request=result.approval_request,
                governance_queue_entry=result.governance_queue_entry,result_identity="")
    with pytest.raises(ValueError,match="GATE_INVALID"): PromotionGate("governance_entry_eligibility",False,"GATE_PASSED",{"scope":"x"})
