"""Adversarial PR273 independent candidate-qualification authority tests."""
from dataclasses import replace
import pytest
from learning.qualification import (CandidateQualificationAuthority, QualificationAttestation,
    QualificationEvidenceIssuer, QualificationEvidenceRegistry, QualificationGate, QualificationPolicy, QualificationRegistry)
from tests.learning.test_pr272_independent_evaluation import governed as pr272_governed, evaluate

@pytest.fixture(scope="module")
def evaluated():
    values = pr272_governed.__wrapped__()
    _, _, report = evaluate(values)
    candidates, result, *_ = values
    from learning.evaluation import EvaluationRegistry
    return values, candidates, result, EvaluationRegistry().append(report), report

def authority(evaluated, conditional=("statistical_confidence",), require=False):
    report = evaluated[-1]
    issuers = tuple(QualificationEvidenceIssuer(domain, domain + ":issuer-v1") for domain in
        ("governance_compliance", "policy_compliance", "architecture_compatibility"))
    policy = QualificationPolicy("qualification-v1", (report.policy.policy_identity,), tuple(x.issuer_identity for x in issuers),
        require_evaluation_qualified=require, minimum_candidate_score=0, minimum_records=30,
        minimum_regime_records=2, maximum_error_stddev=99, maximum_mean_squared_error=99,
        maximum_confidence_brier_score=1, minimum_risk_score=0, minimum_calibration_score=0,
        conditional_gates=conditional)
    registry = QualificationEvidenceRegistry()
    for issuer in issuers:
        registry = registry.append(issuer.issue(report.candidate_identity, report.report_identity,
            policy.policy_identity, True, issuer.domain + ":v1"))
    evidence = registry.evidence_for(report.candidate_identity, report.report_identity, policy.policy_identity)
    return CandidateQualificationAuthority(policy), registry, evidence

def inputs(evaluated, evidence_registry, evidence):
    _, candidates, result, evaluations, report = evaluated
    return candidates, evaluations, result.candidate, result.evidence, report, evidence_registry, evidence

def test_authoritative_evidence_and_exact_registry_objects_are_mandatory(evaluated):
    engine, registry, evidence = authority(evaluated)
    report = engine.qualify(*inputs(evaluated, registry, evidence))
    assert report.qualification_evidence == evidence
    assert report.candidate_evidence_identity == evaluated[2].evidence.evidence_identity
    forged = replace(evidence, qualification_policy_identity="forged", evidence_identity="")
    with pytest.raises(ValueError, match="EVIDENCE_BINDING"): engine.qualify(*inputs(evaluated, registry, forged))
    with pytest.raises(ValueError, match="CANDIDATE_REGISTRY_BINDING"):
        engine.qualify(*((*inputs(evaluated, registry, evidence)[:3], replace(evaluated[2].evidence,
            replay_digest="forged", evidence_identity=""), *inputs(evaluated, registry, evidence)[4:])))

def test_policy_is_fail_closed_and_critical_gates_cannot_be_conditional(evaluated):
    with pytest.raises(ValueError, match="POLICY_INVALID"): QualificationPolicy("x", (), ("a", "b", "c"))
    with pytest.raises(ValueError, match="POLICY_INVALID"):
        QualificationPolicy("x", (evaluated[-1].policy.policy_identity,), ("a", "b", "c"), conditional_gates=("replay_integrity",))
    with pytest.raises(ValueError, match="POLICY_INVALID"):
        QualificationPolicy("x", (evaluated[-1].policy.policy_identity,), ("a", "b", "c"), minimum_records=29)

def test_conditional_is_not_governance_eligible_and_prerequisite_is_policy_owned(evaluated):
    engine, registry, evidence = authority(evaluated, require=False)
    report = engine.qualify(*inputs(evaluated, registry, evidence))
    assert report.decision == "CONDITIONAL" and not report.governance_eligible
    strict, strict_registry, strict_evidence = authority(evaluated, require=True)
    rejected = strict.qualify(*inputs(evaluated, strict_registry, strict_evidence))
    assert rejected.decision == "REJECTED" and not rejected.governance_eligible
    assert strict.policy.policy_identity != engine.policy.policy_identity

def test_gate_and_report_forgery_and_replay_fail_closed(evaluated):
    engine, registry, evidence = authority(evaluated)
    args = inputs(evaluated, registry, evidence); report = engine.qualify(*args)
    assert engine.replay(report, *args)
    with pytest.raises(ValueError, match="GATE_INVALID"):
        QualificationGate("risk_acceptance", False, "GATE_PASSED", {"observed": 0})
    object.__setattr__(report.qualification_evidence, "qualification_policy_identity", "forged")
    assert not engine.replay(report, *args)

def test_registry_ancestry_duplicate_and_policy_tampering(evaluated):
    engine, evidence_registry, evidence = authority(evaluated)
    report = engine.qualify(*inputs(evaluated, evidence_registry, evidence)); empty = QualificationRegistry(); one = empty.append(report)
    assert one.previous_registry_identity == empty.registry_identity
    with pytest.raises(ValueError, match="DUPLICATE"): one.append(report)
    with pytest.raises(ValueError, match="PREDECESSOR"):
        replace(one, previous_registry_identity="forged", registry_identity="")
    with pytest.raises(ValueError, match="POLICY_IDENTITY"):
        replace(engine.policy, maximum_mean_squared_error=100)
