"""PR272 independent, deterministic, replay-safe model evaluation tests."""
from dataclasses import replace
import pytest
from bridge.v28.offline_learning import build_learning_dataset, create_learning_registry, publish_learning_evidence
from bridge.v28.outcome_analytics import analyze_learning_evidence
from bridge.v28.outcome_evidence import publish_outcome_evidence
from bridge.v28.outcome_registry import create_outcome_registry
from learning.evaluation import DIMENSIONS, EvaluationPolicy, EvaluationRegistry, ModelEvaluator
from learning.training import CandidateRegistry, TrainingConfiguration, TrainingDatasetLoader, TrainingSession
from tests.test_v28_outcome_intelligence import outcome

def authorities():
    outcomes = create_outcome_registry().append(outcome("eval-one"))
    oe = publish_outcome_evidence(outcomes); dataset = build_learning_dataset(outcomes, oe)
    evidence = publish_learning_evidence(outcomes, oe, dataset); learning = create_learning_registry().append(evidence)
    analytics = analyze_learning_evidence(evidence)
    config = TrainingConfiguration(("confidence", "spread"), policy_identity="training-v1", code_version="git:pr271")
    trained = TrainingSession(config).run(TrainingDatasetLoader().load(learning, evidence, analytics))
    return CandidateRegistry().append(trained.candidate, trained.evidence), trained, learning, analytics

def test_report_is_complete_deterministic_and_replay_safe():
    candidates, trained, learning, analytics = authorities(); evaluator = ModelEvaluator(EvaluationPolicy("evaluation-v1", minimum_records=1))
    inputs = (candidates, trained.candidate, trained.evidence, learning, analytics)
    first = evaluator.evaluate(*inputs); second = evaluator.evaluate(*inputs)
    assert first == second and evaluator.replay(first, *inputs)
    assert tuple(x.dimension for x in first.dimensions) == DIMENSIONS
    assert first.statistical_validation.record_count == 1
    assert first.replay_validation.consistent and first.report_identity

def test_authorities_and_registry_are_fail_closed():
    candidates, trained, learning, analytics = authorities(); evaluator = ModelEvaluator(EvaluationPolicy("evaluation-v1", minimum_records=1))
    with pytest.raises(ValueError, match="REGISTRY_BINDING"):
        evaluator.evaluate(CandidateRegistry(), trained.candidate, trained.evidence, learning, analytics)
    report = evaluator.evaluate(candidates, trained.candidate, trained.evidence, learning, analytics)
    registry = EvaluationRegistry().append(report)
    with pytest.raises(ValueError, match="DUPLICATE"): registry.append(report)
    with pytest.raises(ValueError, match="REPORT_INVALID"):
        replace(report, production_authorized=True, report_identity="")

def test_forged_report_and_analytics_do_not_replay():
    candidates, trained, learning, analytics = authorities(); evaluator = ModelEvaluator(EvaluationPolicy("evaluation-v1", minimum_records=1))
    inputs = (candidates, trained.candidate, trained.evidence, learning, analytics)
    report = evaluator.evaluate(*inputs)
    object.__setattr__(report, "candidate_score", 0.0)
    assert not evaluator.replay(report, *inputs)
    original = analytics.report_identity; object.__setattr__(analytics, "report_identity", "forged")
    with pytest.raises(ValueError): evaluator.evaluate(*inputs)
    object.__setattr__(analytics, "report_identity", original)
