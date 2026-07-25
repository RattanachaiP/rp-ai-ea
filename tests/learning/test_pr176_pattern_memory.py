"""Contract tests for the PR176 immutable Pattern Memory boundary."""
import json
from uuid import uuid4

import pytest

from learning.learning_policy import GovernedLearningPolicyEngine
from learning.outcome_attribution import KnowledgeOutcomeAttributionEngine
from learning.pattern_memory import (PatternMemoryEngine, PatternMemoryError, PatternMemoryRecord,
                                     PatternMemoryRepository)
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


def record_values(record):
    values = record.to_dict()
    for key in ("memory_uuid", "memory_identity_digest", "memory_digest"):
        values.pop(key)
    return values


def test_complete_provenance_identity_and_stored_state(tmp_path):
    source = mining_report()
    result = PatternMemoryEngine(PatternMemoryRepository(tmp_path)).create(source)
    record = result.memory_records[0]
    assert record.policy_version == source.candidate_patterns[0].policy_version
    assert record.source_digest == source.source_digest
    assert record.replay_digest == source.replay_digest
    assert record.evidence_envelope_digest == source.evidence_envelope_digest
    assert record.mining_config_digest == source.mining_config_digest
    assert record.outcome_contract == source.candidate_patterns[0].outcome_contract
    assert record.memory_state == "STORED"
    assert result.source_pattern_mining_report_uuid == source.report_uuid
    from learning.pattern_memory.memory_identity import digest
    assert result.source_pattern_mining_report_digest == digest(source.to_dict())
    assert result.memory_version == PatternMemoryEngine.memory_version
    assert result.repository_record_count == 1


def test_random_valid_or_tampered_memory_uuid_is_rejected(tmp_path):
    record = PatternMemoryEngine(PatternMemoryRepository(tmp_path)).create(mining_report()).memory_records[0]
    with pytest.raises(ValueError, match="MEMORY_UUID_MISMATCH"):
        record.__class__(**{**record.to_dict(), "memory_uuid": str(uuid4())})


@pytest.mark.parametrize("field,value", [
    ("report_uuid", lambda: str(uuid4())),
    ("policy_version", lambda: "PR174.changed"),
    ("source_digest", lambda: "b" * 64),
    ("replay_digest", lambda: "c" * 64),
    ("evidence_envelope_digest", lambda: "d" * 64),
    ("mining_config_digest", lambda: "e" * 64),
    ("outcome_contract", lambda: ("RETURN", "PERCENT")),
])
def test_every_governance_identity_field_changes_memory_uuid(tmp_path, field, value):
    record = PatternMemoryEngine(PatternMemoryRepository(tmp_path)).create(mining_report()).memory_records[0]
    changed = PatternMemoryRecord.create(**{**record_values(record), field: value()})
    recreated = PatternMemoryRecord.create(**record_values(record))
    assert recreated.memory_uuid == record.memory_uuid
    assert changed.memory_uuid != record.memory_uuid


@pytest.mark.parametrize("context", [
    {"nested": [float("nan")]}, {"nested": {"bad": float("inf")}}, {1: "bad"}, {"bad": object()},
])
def test_nested_context_must_be_json_safe(tmp_path, context):
    record = PatternMemoryEngine(PatternMemoryRepository(tmp_path)).create(mining_report()).memory_records[0]
    with pytest.raises((ValueError, PatternMemoryError)):
        PatternMemoryRecord.create(**{**record_values(record), "market_context": context})


def test_active_and_unknown_memory_states_are_rejected(tmp_path):
    record = PatternMemoryEngine(PatternMemoryRepository(tmp_path)).create(mining_report()).memory_records[0]
    for state in ("ACTIVE", "UNKNOWN"):
        with pytest.raises(ValueError, match="INVALID_PATTERN_MEMORY_RECORD"):
            PatternMemoryRecord.create(**{**record_values(record), "memory_state": state})


def test_memory_uuid_dedup_conflict_and_historical_pattern_versions(tmp_path):
    source = mining_report(); repository = PatternMemoryRepository(tmp_path / "normal")
    first = PatternMemoryEngine(repository).create(source).memory_records[0]
    replay = PatternMemoryEngine(repository).create(source)
    assert replay.duplicate_count == 1
    historical = PatternMemoryRecord.create(**{**record_values(first), "report_uuid": str(uuid4())})
    assert historical.pattern_uuid == first.pattern_uuid and historical.memory_uuid != first.memory_uuid
    repository.save(historical)
    assert len(repository.records()) == 2

    conflicting = PatternMemoryRecord.create(**{**record_values(first), "expectancy": first.expectancy + 1})
    assert conflicting.memory_uuid == first.memory_uuid and conflicting.memory_digest != first.memory_digest

    class ConflictRepository(PatternMemoryRepository):
        def records(self):
            return (conflicting,)
        def latest_snapshot(self):
            return None

    with pytest.raises(PatternMemoryError, match="MEMORY_CONFLICT"):
        PatternMemoryEngine(ConflictRepository(tmp_path / "conflict")).create(source)


def test_repository_collision_cleanup_corruption_and_filename_identity(tmp_path):
    source = mining_report(); repository = PatternMemoryRepository(tmp_path)
    record = PatternMemoryEngine(repository).create(source).memory_records[0]
    conflict = PatternMemoryRecord.create(**{**record_values(record), "expectancy": record.expectancy + 1})
    with pytest.raises(PatternMemoryError, match="MEMORY_COLLISION"):
        repository.save(conflict)
    assert not tuple(tmp_path.glob(".pattern-memory-*"))

    corrupt_root = tmp_path / "corrupt"; corrupt_root.mkdir()
    (corrupt_root / f"{uuid4()}.json").write_text("{")
    with pytest.raises(PatternMemoryError, match="CORRUPT_PATTERN_MEMORY"):
        PatternMemoryRepository(corrupt_root).records()

    mismatch_root = tmp_path / "mismatch"; mismatch_root.mkdir()
    other_uuid = str(uuid4())
    (mismatch_root / f"{other_uuid}.json").write_text(json.dumps(record.to_dict()))
    with pytest.raises(PatternMemoryError, match="MEMORY_FILENAME_IDENTITY_MISMATCH"):
        PatternMemoryRepository(mismatch_root).records()

    invalid_root = tmp_path / "invalid"; invalid_root.mkdir()
    raw = record.to_dict(); invalid_uuid = str(uuid4()); raw["memory_uuid"] = invalid_uuid
    (invalid_root / f"{invalid_uuid}.json").write_text(json.dumps(raw))
    with pytest.raises(PatternMemoryError, match="CORRUPT_PATTERN_MEMORY"):
        PatternMemoryRepository(invalid_root).records()


def test_snapshot_chain_and_expanded_indexes(tmp_path):
    repository = PatternMemoryRepository(tmp_path)
    source = mining_report()
    first_report = PatternMemoryEngine(repository).create(source)
    first_snapshot = repository.latest_snapshot()
    assert first_snapshot.record_count == 1
    replay = PatternMemoryEngine(repository).create(source)
    assert replay.snapshot_uuid == first_report.snapshot_uuid
    assert repository.latest_snapshot() == first_snapshot

    second_report = PatternMemoryEngine(repository).create(mining_report())
    second_snapshot = repository.latest_snapshot()
    assert second_snapshot.snapshot_uuid != first_snapshot.snapshot_uuid
    assert second_snapshot.snapshot_digest != first_snapshot.snapshot_digest
    assert second_snapshot.previous_snapshot_uuid == first_snapshot.snapshot_uuid
    assert second_snapshot.previous_snapshot_digest == first_snapshot.snapshot_digest
    assert second_snapshot.record_count == 2

    index = PatternMemoryEngine(repository).index()
    second_record = repository.records()[1]
    assert index.by_report_uuid[second_record.report_uuid]
    assert index.by_source_attribution_uuid[second_record.source_attribution_uuid]
    assert index.by_evidence_envelope_uuid[second_record.evidence_envelope_uuid]
    assert index.by_source_digest[second_record.source_digest]
    assert index.by_replay_digest[second_record.replay_digest]
    assert index.by_mining_config_digest[second_record.mining_config_digest]
    assert index.by_memory_state["STORED"]

    raw = second_snapshot.to_dict(); raw["record_count"] += 1
    with pytest.raises(ValueError, match="INVALID_PATTERN_MEMORY_SNAPSHOT"):
        second_snapshot.__class__(**raw)
    raw = second_snapshot.to_dict(); raw["record_identities"] = []
    with pytest.raises(ValueError):
        second_snapshot.__class__(**raw)


@pytest.mark.parametrize("field", ["source_digest", "replay_digest"])
def test_explicit_pattern_provenance_validation_precedes_outer_identity(field, tmp_path):
    source = mining_report()
    object.__setattr__(source.candidate_patterns[0], field, "f" * 64)
    with pytest.raises(PatternMemoryError, match="BROKEN_PATTERN_PROVENANCE"):
        PatternMemoryEngine(PatternMemoryRepository(tmp_path)).create(source)


@pytest.mark.parametrize("field,value,error", [
    ("policy_version", "different", "MIXED_POLICY_VERSION"),
    ("knowledge_uuid", lambda: str(uuid4()), "MIXED_KNOWLEDGE_IDENTITY"),
    ("knowledge_version", "different", "MIXED_KNOWLEDGE_IDENTITY"),
    ("outcome_contract", ("RETURN", "PERCENT"), "MIXED_OUTCOME_CONTRACT"),
])
def test_mixed_pattern_governance_is_rejected_explicitly(field, value, error, tmp_path):
    source = mining_report(); original = source.candidate_patterns[0]
    from dataclasses import replace
    changed = replace(original, **{field: value() if callable(value) else value})
    object.__setattr__(source, "candidate_patterns", (original, changed))
    with pytest.raises(PatternMemoryError, match=error):
        PatternMemoryEngine(PatternMemoryRepository(tmp_path)).create(source)


def test_memory_report_source_identity_and_tamper_protection(tmp_path):
    repository = PatternMemoryRepository(tmp_path)
    first = PatternMemoryEngine(repository).create(mining_report())
    second = PatternMemoryEngine(repository).create(mining_report())
    assert first.source_pattern_mining_report_uuid != second.source_pattern_mining_report_uuid
    assert first.report_uuid != second.report_uuid
    from dataclasses import replace
    with pytest.raises(ValueError, match="INVALID_PATTERN_MEMORY_REPORT"):
        replace(second, source_pattern_mining_report_digest="f" * 64)
