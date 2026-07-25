"""Governance contract tests for the PR177 historical validation boundary."""
from dataclasses import replace
import json
from uuid import uuid4
import pytest

from learning.pattern_memory import PatternMemoryEngine, PatternMemoryRecord, PatternMemoryRepository
from learning.pattern_validation import (PatternValidationEngine, PatternValidationError,
    PatternValidationRepository, ValidationConfig, ValidationRecord)
from test_pr176_pattern_memory import mining_report, record_values


def memory_report(tmp_path):
    return PatternMemoryEngine(PatternMemoryRepository(tmp_path / "memory")).create(mining_report())


def engine(tmp_path, **kwargs):
    return PatternValidationEngine(PatternValidationRepository(tmp_path / "validation"), **kwargs)


def test_only_exact_pr176_artifacts_are_accepted(tmp_path):
    for value in (None, {}, object(), mining_report()):
        with pytest.raises(PatternValidationError, match="INVALID_PATTERN_MEMORY_INPUT"):
            engine(tmp_path).validate(value)


def test_neutral_semantics_and_complete_provenance(tmp_path):
    source = memory_report(tmp_path); result = engine(tmp_path).validate(source); record = result.validation_records[0]
    assert record.validation_state == "STATISTICALLY_CONSISTENT"
    assert result.statistically_consistent_count == 1
    assert record.advisory_only is result.advisory_only is True
    assert record.source_memory_uuid == source.memory_records[0].memory_uuid
    assert record.source_memory_digest == source.memory_records[0].memory_digest
    assert record.source_pattern_uuid == source.memory_records[0].pattern_uuid
    assert record.source_pattern_hash == source.memory_records[0].pattern_hash
    for name in ("source_report_uuid", "policy_uuid", "policy_version", "source_attribution_uuid",
                 "source_digest", "replay_digest", "evidence_envelope_uuid", "evidence_envelope_digest",
                 "knowledge_uuid", "knowledge_version", "engine_version", "mining_config_digest",
                 "outcome_contract", "memory_version", "memory_state"):
        expected = getattr(source.memory_records[0], "report_uuid" if name == "source_report_uuid" else name)
        assert getattr(record, name) == expected


def test_policy_config_and_validator_are_identity_bound(tmp_path):
    source = memory_report(tmp_path)
    base = engine(tmp_path / "a").validate(source).validation_records[0]
    policy = engine(tmp_path / "b", validation_policy_version="changed").validate(source).validation_records[0]
    validator = engine(tmp_path / "c", validator_version="changed").validate(source).validation_records[0]
    config = engine(tmp_path / "d", config=ValidationConfig(minimum_sample_count=31)).validate(source).validation_records[0]
    assert len({x.validation_uuid for x in (base, policy, validator, config)}) == 4
    assert base.validation_config_digest != config.validation_config_digest


def test_random_uuid_tampered_digest_and_json_unsafe_statistics_rejected(tmp_path):
    record = engine(tmp_path).validate(memory_report(tmp_path)).validation_records[0]
    with pytest.raises(ValueError, match="VALIDATION_UUID_MISMATCH"):
        ValidationRecord(**{**record.to_dict(), "validation_uuid": str(uuid4())})
    with pytest.raises(ValueError, match="VALIDATION_DIGEST_MISMATCH"):
        ValidationRecord(**{**record.to_dict(), "validation_digest": "f" * 64})
    for bad in ({"nested": [float("nan")]}, {"x": float("inf")}, {1: "bad"}, {"x": object()}):
        with pytest.raises((ValueError, TypeError)):
            ValidationRecord(**{**record.to_dict(), "validation_statistics": bad})


def test_source_report_and_single_record_binding(tmp_path):
    source = memory_report(tmp_path)
    report_result = engine(tmp_path / "report").validate(source)
    assert report_result.source_artifact_type == "PATTERN_MEMORY_REPORT"
    assert report_result.source_pattern_memory_report_uuid == source.report_uuid
    assert report_result.source_snapshot_uuid == source.snapshot_uuid
    assert report_result.source_snapshot_digest == source.snapshot_digest
    assert report_result.source_pattern_memory_report_digest
    single = engine(tmp_path / "record").validate(source.memory_records[0])
    assert single.source_artifact_type == "PATTERN_MEMORY_RECORD"
    assert single.source_memory_uuid == source.memory_records[0].memory_uuid
    assert single.source_memory_digest == source.memory_records[0].memory_digest
    assert single.report_uuid != report_result.report_uuid


def test_single_record_reconstruction_state_and_advisory_enforced(tmp_path):
    record = memory_report(tmp_path).memory_records[0]
    assert engine(tmp_path).validate(replace(record)).processed_record_count == 1
    for field, value in (("memory_state", "ACTIVE"), ("memory_state", "ARCHIVED"),
                         ("memory_state", "SUPERSEDED"), ("advisory_only", False)):
        object.__setattr__(record, field, value)
        with pytest.raises(PatternValidationError, match="BROKEN_PATTERN_MEMORY_RECORD"):
            engine(tmp_path / str(value)).validate(record)
        object.__setattr__(record, field, "STORED" if field == "memory_state" else True)


def test_invalid_source_statistics_fail_closed(tmp_path):
    for field, value in (("support", -1.0), ("confidence", -1.0), ("expectancy", float("nan")),
                         ("expectancy", float("inf"))):
        record = memory_report(tmp_path / field / str(value)).memory_records[0]
        object.__setattr__(record, field, value)
        with pytest.raises(PatternValidationError, match="BROKEN_PATTERN_MEMORY_RECORD"):
            engine(tmp_path / "out" / field / str(value)).validate(record)
    source = memory_report(tmp_path / "negative-expectancy")
    record = PatternMemoryRecord.create(**{**record_values(source.memory_records[0]), "expectancy": -0.1})
    result = engine(tmp_path / "negative-result").validate(record)
    assert result.invalid_count == 1


def test_duplicate_replay_counts_and_canonical_append_only_storage(tmp_path):
    source = memory_report(tmp_path); repository = PatternValidationRepository(tmp_path / "validation")
    first = PatternValidationEngine(repository).validate(source)
    assert first.new_validation_count == 1 and first.duplicate_validation_count == 0
    path = repository.path_for(first.validation_records[0].validation_uuid)
    assert path.read_bytes() == json.dumps(first.validation_records[0].to_dict(), sort_keys=True,
                                            separators=(",", ":"), allow_nan=False).encode()
    replay = PatternValidationEngine(repository).validate(source)
    assert replay.new_validation_count == 0 and replay.duplicate_validation_count == 1
    assert len(repository.records()) == 1 and len(repository.snapshots()) == 1


def test_snapshot_chain_identity_linkage_and_repository_mismatch(tmp_path):
    repository = PatternValidationRepository(tmp_path / "validation")
    PatternValidationEngine(repository).validate(memory_report(tmp_path / "one"))
    first = repository.latest_snapshot()
    PatternValidationEngine(repository).validate(memory_report(tmp_path / "two"))
    second = repository.latest_snapshot()
    assert second.snapshot_uuid != first.snapshot_uuid
    assert second.previous_snapshot_uuid == first.snapshot_uuid
    assert second.previous_snapshot_digest == first.snapshot_digest
    raw = second.to_dict(); raw["snapshot_digest"] = "f" * 64
    with pytest.raises(ValueError, match="INVALID_VALIDATION_SNAPSHOT"):
        second.__class__(**raw)
    object.__setattr__(second, "record_identities", ())
    class BadRepository(PatternValidationRepository):
        def latest_snapshot(self): return second
    with pytest.raises(PatternValidationError, match="VALIDATION_REPOSITORY_SNAPSHOT_MISMATCH"):
        PatternValidationEngine(BadRepository(repository.root)).validate(memory_report(tmp_path / "three"))


def test_broken_source_replay_snapshot_and_mixed_identity(tmp_path):
    source = memory_report(tmp_path); object.__setattr__(source, "report_uuid", str(uuid4()))
    with pytest.raises(PatternValidationError, match="BROKEN_SOURCE_REPLAY"):
        engine(tmp_path / "a").validate(source)
    source = memory_report(tmp_path / "b"); object.__setattr__(source, "repository_record_identities", ())
    with pytest.raises(PatternValidationError, match="BROKEN_SOURCE_SNAPSHOT"):
        engine(tmp_path / "b-out").validate(source)
    source = memory_report(tmp_path / "c"); original = source.memory_records[0]
    other = PatternMemoryRecord.create(**{**record_values(original), "policy_uuid": str(uuid4())})
    object.__setattr__(source, "memory_records", (original, other))
    pairs = tuple(sorted((*source.repository_record_identities, (other.memory_uuid, other.memory_digest))))
    object.__setattr__(source, "repository_record_identities", pairs)
    with pytest.raises(PatternValidationError):
        engine(tmp_path / "c-out").validate(source)
