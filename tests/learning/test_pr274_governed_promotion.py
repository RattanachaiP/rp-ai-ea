"""PR274 governed promotion pipeline and adversarial boundary tests."""
from dataclasses import replace

import pytest

from learning.promotion import (PROMOTION_GATES, PromotionAuthority, PromotionGate,
    PromotionPolicy, PromotionRegistry, PromotionValidationError)
from learning.qualification import QualificationRegistry
from tests.learning.test_pr273_candidate_qualification import (authority as qualification_authority,
    evaluated as evaluated_fixture, inputs as qualification_inputs)


@pytest.fixture(scope="module")
def qualified():
    evaluated = evaluated_fixture.__wrapped__()
    authority, evidence_registry, evidence = qualification_authority(evaluated)
    report = authority.qualify(*qualification_inputs(evaluated, evidence_registry, evidence))
    gates = tuple(replace(gate, passed=True, reason="GATE_PASSED")
                  if gate.gate == "statistical_confidence" else gate for gate in report.gates)
    report = replace(report, gates=gates, decision="PASS", governance_eligible=True,
                     report_identity="")
    return QualificationRegistry().append(report), report, report.qualification_evidence


def promotion(qualified, **changes):
    policy = PromotionPolicy("promotion-v1", (qualified[1].policy.policy_identity,), **changes)
    return PromotionAuthority(policy)


def test_all_eight_gates_evidence_identity_and_human_queue_are_deterministic(qualified):
    authority = promotion(qualified)
    first = authority.assess(*qualified)
    second = authority.promote(*qualified)
    assert first == second and authority.replay(first, *qualified)
    assert first.report.decision == "ELIGIBLE"
    assert tuple(x.gate for x in first.report.promotion_evidence.gates) == PROMOTION_GATES
    assert first.report.human_approval_required and not first.report.human_approved
    assert first.approval_request.status == "PENDING"
    assert first.governance_queue_entry.queue_status == "AWAITING_HUMAN_REVIEW"
    assert not first.report.deployment_authorized and not first.report.runtime_authorized


def test_registry_is_append_only_identity_policy_evidence_and_lineage_bound(qualified):
    result = promotion(qualified).assess(*qualified)
    empty = PromotionRegistry()
    registry = empty.append(result.report)
    assert registry.previous_registry_identity == empty.registry_identity
    assert registry.append(result.report) is registry  # replay is idempotent
    with pytest.raises(ValueError, match="PREDECESSOR"):
        replace(registry, previous_registry_identity="forged", registry_identity="")
    with pytest.raises(ValueError, match="POLICY_IDENTITY"):
        replace(result.report.policy, policy_reference="forged")
    with pytest.raises(ValueError, match="EVIDENCE_IDENTITY"):
        replace(result.report.promotion_evidence, candidate_identity="forged")


def test_policy_registry_evidence_identity_and_lineage_mismatch_fail_closed(qualified):
    registry, report, evidence = qualified
    rejected = PromotionAuthority(PromotionPolicy("other", ("unaccepted-policy",))).assess(
        registry, report, evidence)
    assert rejected.report.decision == "REJECTED"
    assert rejected.approval_request is None and rejected.governance_queue_entry is None
    assert not next(x for x in rejected.report.promotion_evidence.gates
                    if x.gate == "promotion_policy_compliance").passed
    empty_result = promotion(qualified).assess(QualificationRegistry(), report, evidence)
    assert empty_result.report.decision == "REJECTED"
    assert not next(x for x in empty_result.report.promotion_evidence.gates
                    if x.gate == "registry_lineage_validation").passed
    with pytest.raises(PromotionValidationError):
        promotion(qualified).assess(registry, report, None)


def test_policy_owned_noncritical_failure_is_conditional_and_still_requires_review(qualified):
    registry, report, evidence = qualified
    gates = tuple(replace(gate, passed=False, reason="GATE_FAILED")
                  if gate.gate == "statistical_confidence" else gate for gate in report.gates)
    not_ready = replace(report, gates=gates, decision="CONDITIONAL",
                        governance_eligible=False, report_identity="")
    registry = QualificationRegistry().append(not_ready)
    result = PromotionAuthority(PromotionPolicy("conditional-promotion",
        (report.policy.policy_identity,), conditional_gates=("governance_readiness",),
        require_qualification_pass=False)).assess(registry, not_ready, evidence)
    assert result.report.decision == "CONDITIONAL"
    assert result.approval_request.status == "PENDING"


def test_contract_forgery_critical_conditional_and_adversarial_replay_fail_closed(qualified):
    with pytest.raises(ValueError, match="POLICY_INVALID"):
        PromotionPolicy("bad", (qualified[1].policy.policy_identity,),
                        conditional_gates=("candidate_integrity",))
    with pytest.raises(ValueError, match="GATE_INVALID"):
        PromotionGate("promotion_authorization", False, "GATE_PASSED", {"scope": "x"})
    authority = promotion(qualified)
    result = authority.assess(*qualified)
    object.__setattr__(result.report.promotion_evidence, "candidate_identity", "forged")
    assert not authority.replay(result, *qualified)
