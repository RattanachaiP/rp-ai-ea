from dataclasses import replace
import json
import math
from uuid import uuid4

import pytest

from learning.learning_policy import GovernedLearningPolicyReport
from learning.pattern_mining import PatternMiningEngine, PatternMiningError, PatternMiningRepository


def policy(*, eligible=True, evidence=None):
    count = len(evidence) if evidence is not None else 30
    summary = {"outcome_contract": ["REALIZED_PNL", "USD"]}
    if evidence is not None:
        summary["approved_evidence"] = evidence
    return GovernedLearningPolicyReport(
        str(uuid4()), "PR174.2.0", str(uuid4()), "1", 
        "ELIGIBLE_FOR_PATTERN_MINING" if eligible else "REQUIRES_MORE_DATA",
        count, 30, 0 if eligible else max(0, 30-count),
        {"structural_validity": True}, (), (), summary,
        "2026-07-25T00:00:00Z", True, min(1.0, count / 30),
    )


def rows(knowledge_uuid):
    return [
        {"knowledge_uuid": knowledge_uuid, "knowledge_version": "1",
         "outcome_contract": ["REALIZED_PNL", "USD"], "features": {"trend": "up"},
         "market_context": {"session": "LONDON"}, "entry_context": {"side": "BUY"},
         "exit_context": {"kind": "TARGET"}, "risk_context": {"tier": "LOW"}, "outcome": value}
        for value in (2.0, -1.0, 0.0)
    ]


def test_rejects_non_policy_and_non_eligible():
    with pytest.raises(PatternMiningError, match="INVALID_POLICY_REPORT"):
        PatternMiningEngine().mine({})
    with pytest.raises(PatternMiningError, match="POLICY_NOT_ELIGIBLE"):
        PatternMiningEngine().mine(policy(eligible=False))


def test_deterministic_identity_and_aggregate_fallback():
    source = policy()
    first = PatternMiningEngine().mine(source)
    second = PatternMiningEngine().discover(source)
    assert first == second
    assert first.report_uuid == second.report_uuid
    assert first.candidate_patterns[0].pattern_uuid == second.candidate_patterns[0].pattern_uuid
    assert first.candidate_patterns[0].pattern_hash == second.candidate_patterns[0].pattern_hash
    assert first.advisory_only is True


def test_pattern_statistics_and_immutable_context():
    source = policy()
    evidence = rows(source.knowledge_uuid)
    source = replace(source, sample_count=3, minimum_required_samples=3,
                     validation_summary={"outcome_contract": ["REALIZED_PNL", "USD"], "approved_evidence": evidence})
    pattern = PatternMiningEngine().mine(source).candidate_patterns[0]
    assert (pattern.sample_count, pattern.win_count, pattern.loss_count, pattern.neutral_count) == (3, 1, 1, 1)
    assert pattern.support == 1 and pattern.expectancy == pytest.approx(1 / 3)
    assert pattern.confidence == pytest.approx(0.5)
    with pytest.raises(TypeError):
        pattern.market_context["session"] = "NEW_YORK"


def test_rejects_mixed_identity_contract_and_invalid_numbers():
    source = policy()
    evidence = rows(source.knowledge_uuid)
    evidence[1]["knowledge_uuid"] = str(uuid4())
    source = replace(source, validation_summary={"outcome_contract": ["REALIZED_PNL", "USD"], "approved_evidence": evidence})
    with pytest.raises(PatternMiningError, match="MIXED_KNOWLEDGE_UUID"):
        PatternMiningEngine().mine(source)
    evidence = rows(source.knowledge_uuid)
    evidence[1]["outcome_contract"] = ["RETURN", "PERCENT"]
    source = replace(source, validation_summary={"outcome_contract": ["REALIZED_PNL", "USD"], "approved_evidence": evidence})
    with pytest.raises(PatternMiningError, match="MIXED_OUTCOME_CONTRACT"):
        PatternMiningEngine().mine(source)
    evidence = rows(source.knowledge_uuid)
    evidence[0]["outcome"] = math.nan
    object.__setattr__(source, "validation_summary",
                       {"outcome_contract": ["REALIZED_PNL", "USD"], "approved_evidence": evidence})
    with pytest.raises(PatternMiningError, match="INVALID_STATISTICS"):
        PatternMiningEngine().mine(source)


def test_append_only_canonical_idempotent_repository(tmp_path):
    report = PatternMiningEngine().mine(policy())
    repository = PatternMiningRepository(tmp_path)
    path = repository.save(report)
    assert repository.save(report) == path
    assert path.read_bytes() == json.dumps(report.to_dict(), sort_keys=True, separators=(",", ":"), allow_nan=False).encode()
    with pytest.raises(FileExistsError, match="COLLISION"):
        repository.save(replace(report, statistics_summary={"changed": True}))
    with pytest.raises(ValueError, match="INVALID_REPORT_FILENAME"):
        repository.path_for("../escape")
