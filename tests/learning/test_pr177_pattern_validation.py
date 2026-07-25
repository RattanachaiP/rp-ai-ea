"""Contract tests for the PR177 governed validation boundary."""
import json
from uuid import uuid4

import pytest

from learning.pattern_validation import (PatternValidationEngine, PatternValidationError,
                                         PatternValidationRepository)
from test_pr176_pattern_memory import mining_report, record_values
from learning.pattern_memory import PatternMemoryEngine, PatternMemoryRecord, PatternMemoryRepository


def memory_report(tmp_path):
    return PatternMemoryEngine(PatternMemoryRepository(tmp_path / "memory")).create(mining_report())


def test_only_memory_artifacts_are_accepted(tmp_path):
    engine = PatternValidationEngine(PatternValidationRepository(tmp_path / "validation"))
    for value in (None, {}, object(), mining_report()):
        with pytest.raises(PatternValidationError, match="INVALID_PATTERN_MEMORY_INPUT"):
            engine.validate(value)


def test_validation_is_deterministic_advisory_and_not_promotion(tmp_path):
    source = memory_report(tmp_path)
    first = PatternValidationEngine(PatternValidationRepository(tmp_path / "one")).validate(source)
    second = PatternValidationEngine(PatternValidationRepository(tmp_path / "two")).validate(source)
    assert first == second
    assert first.validation_records[0].validation_uuid == second.validation_records[0].validation_uuid
    assert first.advisory_only is True
    assert not ({"approved", "promoted", "active", "tradable"} & set(first.validation_records[0].to_dict()))


def test_append_only_canonical_storage_and_replay(tmp_path):
    repository = PatternValidationRepository(tmp_path / "validation")
    source = memory_report(tmp_path)
    report = PatternValidationEngine(repository).validate(source)
    record = report.validation_records[0]; path = repository.path_for(record.validation_uuid)
    expected = json.dumps(record.to_dict(), sort_keys=True, separators=(",", ":"), allow_nan=False).encode()
    assert path.read_bytes() == expected
    assert repository.save(record) == path
    replay = PatternValidationEngine(repository).validate(source)
    assert replay.validation_records == report.validation_records
    assert replay.repository_digest == report.repository_digest


@pytest.mark.parametrize("field,error", [
    ("memory_digest", "BROKEN_MEMORY_DIGEST"),
    ("memory_uuid", "BROKEN_MEMORY_IDENTITY"),
])
def test_broken_memory_integrity_fails_closed(tmp_path, field, error):
    record = memory_report(tmp_path).memory_records[0]
    object.__setattr__(record, field, "f" * 64 if field.endswith("digest") else str(uuid4()))
    with pytest.raises(PatternValidationError, match=error):
        PatternValidationEngine(PatternValidationRepository(tmp_path / "validation")).validate(record)


def test_broken_replay_snapshot_and_mixed_identity_fail_closed(tmp_path):
    source = memory_report(tmp_path)
    object.__setattr__(source, "report_uuid", str(uuid4()))
    with pytest.raises(PatternValidationError, match="BROKEN_REPLAY"):
        PatternValidationEngine(PatternValidationRepository(tmp_path / "a")).validate(source)

    source = memory_report(tmp_path / "second")
    object.__setattr__(source, "repository_record_identities", ())
    with pytest.raises(PatternValidationError, match="BROKEN_SNAPSHOT_CHAIN"):
        PatternValidationEngine(PatternValidationRepository(tmp_path / "b")).validate(source)

    source = memory_report(tmp_path / "third"); original = source.memory_records[0]
    other = PatternMemoryRecord.create(**{**record_values(original), "policy_uuid": str(uuid4())})
    object.__setattr__(source, "memory_records", (original, other))
    with pytest.raises(PatternValidationError):
        PatternValidationEngine(PatternValidationRepository(tmp_path / "c")).validate(source)


def test_repository_corruption_is_rejected(tmp_path):
    root = tmp_path / "validation"; root.mkdir()
    (root / f"{uuid4()}.json").write_text("{")
    with pytest.raises(PatternValidationError, match="CORRUPT_VALIDATION_REPOSITORY"):
        PatternValidationRepository(root).records()


def test_insufficient_evidence_is_not_approval(tmp_path):
    report = PatternValidationEngine(PatternValidationRepository(tmp_path / "validation")).validate(memory_report(tmp_path))
    assert report.insufficient_count == 0
    assert report.validated_count == 1
    assert report.invalid_count == 0
    assert report.validation_records[0].validation_state == "VALIDATED"
