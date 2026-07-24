from dataclasses import replace
from uuid import uuid4

import pytest

from learning.learning_policy import (
    GovernedLearningPolicyEngine,
    GovernedLearningPolicyError,
    GovernedLearningPolicyRepository,
)
from learning.outcome_attribution import KnowledgeOutcomeAttributionEngine


def _attribution(count):
    identity = str(uuid4())
    rows = [
        {
            "knowledge_uuid": identity,
            "knowledge_version": "1.0.0",
            "timestamp": "2026-07-24T00:00:00Z",
            "replay_digest": "a" * 64,
            "outcome": 1 if index % 2 else -1,
            "outcome_metric": "REALIZED_PNL",
            "outcome_unit": "USD",
            "features": {"source": "policy-test"},
            "indicators": {"signal": "test"},
            "risk_factors": {"risk": "test"},
            "context": {"regime": "TEST"},
        }
        for index in range(count)
    ]
    return KnowledgeOutcomeAttributionEngine().analyze(rows)


def test_eligibility_classification_is_deterministic():
    engine = GovernedLearningPolicyEngine()
    assert engine.evaluate(_attribution(1)).eligibility_state == "NOT_ELIGIBLE"
    assert engine.evaluate(_attribution(15)).eligibility_state == "REQUIRES_MORE_DATA"
    report = _attribution(30)
    assert engine.evaluate(report).eligibility_state == "ELIGIBLE_FOR_PATTERN_MINING"
    assert engine.evaluate(report).to_dict() == engine.evaluate(report).to_dict()


def test_rejects_non_attribution_invalid_replay_and_mixed_identity():
    engine = GovernedLearningPolicyEngine()
    with pytest.raises(GovernedLearningPolicyError, match="INVALID_OUTCOME_ATTRIBUTION_REPORT"):
        engine.evaluate({})
    report = _attribution(2)
    object.__setattr__(report, "replay_digest", "not-a-digest")
    with pytest.raises(GovernedLearningPolicyError, match="INVALID_ATTRIBUTION_EVIDENCE"):
        engine.evaluate(report)
    report = _attribution(2)
    object.__setattr__(report, "performance_profiles", (replace(report.performance_profiles[0], knowledge_uuid=str(uuid4())),))
    with pytest.raises(GovernedLearningPolicyError, match="MIXED_KNOWLEDGE_IDENTITIES"):
        engine.evaluate(report)


def test_append_only_idempotent_repository(tmp_path):
    policy = GovernedLearningPolicyEngine().evaluate(_attribution(30))
    repository = GovernedLearningPolicyRepository(tmp_path)
    assert repository.save(policy) == repository.save(policy)
    with pytest.raises(FileExistsError, match="APPEND_ONLY_REPORT_COLLISION"):
        repository.save(replace(policy, eligibility_state="REQUIRES_MORE_DATA"))
