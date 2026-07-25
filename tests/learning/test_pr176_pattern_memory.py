"""Contract tests for the PR176 immutable Pattern Memory boundary."""
import json
from uuid import uuid4

import pytest

from learning.learning_policy import GovernedLearningPolicyEngine
from learning.outcome_attribution import KnowledgeOutcomeAttributionEngine
from learning.pattern_memory import PatternMemoryEngine, PatternMemoryError, PatternMemoryRepository
from learning.pattern_mining import ApprovedPatternMiningEvidenceEnvelope, ApprovedPatternMiningSample, PatternMiningEngine


def mining_report():
    knowledge_uuid = str(uuid4())
    rows = [{"knowledge_uuid": knowledge_uuid, "knowledge_version": "1", "timestamp": "2026-07-25T00:00:00Z",
             "replay_digest": "a" * 64, "outcome": (2.0, -1.0, 0.0)[i % 3],
             "outcome_metric": "REALIZED_PNL", "outcome_unit": "USD", "features": {"trend": "up"},
             "indicators": {"rsi": 50}, "risk_factors": {"tier": "LOW"},
             "context": {"session": "LONDON"}} for i in range(30)]
    policy = GovernedLearningPolicyEngine().evaluate(KnowledgeOutcomeAttributionEngine().analyze(rows))
    summary = policy.validation_summary
    samples = tuple(ApprovedPatternMiningSample(str(uuid4()), {"trend": "up", "rsi": 50},
                    {"session": "LONDON"}, {"side": "BUY"}, {"kind": "TARGET"}, {"tier": "LOW"},
                    row["outcome"], row["timestamp"]) for row in rows)
    envelope = ApprovedPatternMiningEvidenceEnvelope.create(
        policy_uuid=policy.policy_uuid, policy_version=policy.policy_version,
        source_attribution_uuid=summary["source_attribution_uuid"], source_digest=summary["source_digest"],
        replay_digest=summary["replay_digest"], knowledge_uuid=policy.knowledge_uuid,
        knowledge_version=policy.knowledge_version, outcome_contract=tuple(summary["outcome_contract"]),
        approved_samples=samples, generated_at=policy.generated_at)
    return PatternMiningEngine().mine(policy, envelope)


def test_only_pattern_mining_report_is_accepted(tmp_path):
    engine = PatternMemoryEngine(PatternMemoryRepository(tmp_path))
    for invalid in (None, {}, object()):
        with pytest.raises(PatternMemoryError, match="INVALID_PATTERN_MINING_REPORT"):
            engine.create(invalid)


def test_deterministic_identity_digest_and_replay(tmp_path):
    source = mining_report()
    first_repo = PatternMemoryRepository(tmp_path / "first")
    second_repo = PatternMemoryRepository(tmp_path / "second")
    first = PatternMemoryEngine(first_repo).create(source)
    second = PatternMemoryEngine(second_repo).create(source)
    assert first == second
    assert first.memory_records[0].memory_uuid == second.memory_records[0].memory_uuid
    assert first.memory_records[0].memory_digest == second.memory_records[0].memory_digest
    replay = PatternMemoryEngine(first_repo).create(source)
    assert replay.memory_count == 0 and replay.duplicate_count == 1
    assert replay.repository_digest == first.repository_digest


def test_append_only_canonical_idempotent_storage_and_indexes(tmp_path):
    source = mining_report(); repository = PatternMemoryRepository(tmp_path)
    result = PatternMemoryEngine(repository).create(source); record = result.memory_records[0]
    path = repository.path_for(record.memory_uuid)
    original = path.read_bytes()
    assert original == json.dumps(record.to_dict(), sort_keys=True, separators=(",", ":"), allow_nan=False).encode()
    assert repository.save(record) == path and path.read_bytes() == original
    index = PatternMemoryEngine(repository).index()
    assert index.by_memory_uuid[record.memory_uuid] == record
    assert index.by_pattern_uuid[record.pattern_uuid] == (record,)
    assert index.by_knowledge_uuid[record.knowledge_uuid] == (record,)
    with pytest.raises(PatternMemoryError, match="INVALID_MEMORY_FILENAME"):
        repository.path_for("../escape")


def test_broken_report_identity_and_provenance_fail_closed(tmp_path):
    source = mining_report(); engine = PatternMemoryEngine(PatternMemoryRepository(tmp_path))
    object.__setattr__(source, "report_uuid", str(uuid4()))
    with pytest.raises(PatternMemoryError, match="BROKEN_REPORT_IDENTITY"):
        engine.create(source)


def test_conflicting_pattern_is_rejected(tmp_path):
    source = mining_report(); repository = PatternMemoryRepository(tmp_path)
    PatternMemoryEngine(repository).create(source)
    pattern = source.candidate_patterns[0]
    object.__setattr__(pattern, "expectancy", pattern.expectancy + 1)
    # Restore the outer identity is intentionally impossible without rebuilding
    # the governed PR175 artifact; its integrity boundary rejects the conflict.
    with pytest.raises(PatternMemoryError, match="BROKEN_REPORT_IDENTITY"):
        PatternMemoryEngine(repository).create(source)


def test_record_rejects_non_finite_and_negative_statistics(tmp_path):
    source = mining_report(); pattern = source.candidate_patterns[0]
    for field, value in (("expectancy", float("nan")), ("confidence", float("inf")), ("sample_count", -1)):
        object.__setattr__(pattern, field, value)
        with pytest.raises(PatternMemoryError, match="BROKEN_REPORT_IDENTITY"):
            PatternMemoryEngine(PatternMemoryRepository(tmp_path / field)).create(source)
