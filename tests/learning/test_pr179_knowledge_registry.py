"""PR179 admission, replay, identity, and repository integrity tests."""
from dataclasses import replace
import json
from pathlib import Path
import sys
from uuid import uuid4
import pytest

sys.path.insert(0, str(Path(__file__).parents[2]))
sys.path.insert(1, str(Path(__file__).parent))
from test_pr176_pattern_memory import mining_report

from learning.knowledge_registry import (KnowledgeRegistryEngine, KnowledgeRegistryError,
    KnowledgeRegistryRepository, RegistryRecord)
from learning.pattern_memory import PatternMemoryEngine, PatternMemoryRepository
from learning.pattern_promotion import PatternPromotionEngine, PatternPromotionRepository, PromotionPolicy
from learning.pattern_validation import PatternValidationEngine, PatternValidationRepository


def promotion_report(tmp_path, policy=None):
    memory = PatternMemoryEngine(PatternMemoryRepository(tmp_path / "memory")).create(mining_report())
    validation = PatternValidationEngine(
        PatternValidationRepository(tmp_path / "validation")).validate(memory)
    return PatternPromotionEngine(PatternPromotionRepository(tmp_path / "promotion"),
                                  policy).assess(validation)


def registry(tmp_path, version=None):
    return KnowledgeRegistryEngine(KnowledgeRegistryRepository(tmp_path / "registry"),
                                   registry_version=version)


def permissive_policy():
    return PromotionPolicy(minimum_sample_count=30, minimum_support=0,
                           minimum_confidence=0, minimum_expectancy=0)


def test_accepts_only_canonical_pr178_artifacts(tmp_path):
    engine = registry(tmp_path)
    for value in (None, {}, object(), "promotion"):
        with pytest.raises(KnowledgeRegistryError, match="INVALID_PROMOTION_ARTIFACT"):
            engine.admit(value)


def test_registered_is_immutable_advisory_admission_only(tmp_path):
    report = promotion_report(tmp_path, permissive_policy())
    result = registry(tmp_path).admit(report); item = result.registry_records[0]
    assert item.registry_state == "REGISTERED" and item.advisory_only is True
    assert result.registered_count == 1 and result.rejected_count == 0
    assert item.promotion_uuid == report.promotion_records[0].promotion_uuid
    assert item.validation_uuid == report.promotion_records[0].source_validation_uuid
    assert not hasattr(result, "runtime_active") and not hasattr(result, "execution_approved")
    with pytest.raises(Exception): item.registry_state = "ACTIVE"


def test_nonqualifying_promotions_are_not_admitted(tmp_path):
    report = promotion_report(tmp_path)
    result = registry(tmp_path).admit(report)
    assert result.registry_records[0].registry_state == "NOT_ADMITTED"
    assert result.registered_count == 0 and result.rejected_count == 1


def test_single_record_input_and_duplicate_replay_are_safe(tmp_path):
    record = promotion_report(tmp_path, permissive_policy()).promotion_records[0]
    engine = registry(tmp_path)
    first = engine.admit(record); replay = engine.admit(record)
    assert first.source_artifact_type == "PROMOTION_RECORD"
    assert first.duplicate_count == 0 and replay.duplicate_count == 1
    assert first.registry_records == replay.registry_records
    assert first.snapshot_uuid == replay.snapshot_uuid
    assert len(engine.repository.records()) == len(engine.repository.snapshots()) == 1


def test_complete_provenance_and_registry_identity_mismatch_fail_closed(tmp_path):
    report = promotion_report(tmp_path, permissive_policy())
    damaged = report.promotion_records[0]
    object.__setattr__(damaged, "source_validation_uuid", str(uuid4()))
    with pytest.raises(KnowledgeRegistryError, match="BROKEN_PROMOTION"):
        registry(tmp_path / "damaged").admit(damaged)

    item = registry(tmp_path / "clean").admit(
        promotion_report(tmp_path / "second", permissive_policy())).registry_records[0]
    with pytest.raises(ValueError, match="INVALID_REGISTRY_RECORD"):
        RegistryRecord(**{**item.to_dict(), "registry_uuid": str(uuid4())})


def test_mixed_promotion_policy_and_engine_are_rejected(tmp_path):
    engine = registry(tmp_path)
    engine.admit(promotion_report(tmp_path / "one", permissive_policy()))
    changed = PromotionPolicy(minimum_sample_count=31, minimum_support=0,
                              minimum_confidence=0, minimum_expectancy=0)
    with pytest.raises(KnowledgeRegistryError, match="MIXED_PROMOTION_POLICY"):
        engine.admit(promotion_report(tmp_path / "two", changed))
    other = promotion_report(tmp_path / "three", permissive_policy())
    object.__setattr__(other, "promotion_engine_version", "PR178.changed")
    with pytest.raises(KnowledgeRegistryError, match="BROKEN_PROMOTION_REPORT"):
        engine.admit(other)


def test_report_replay_and_snapshot_provenance_tampering_fail_closed(tmp_path):
    report = promotion_report(tmp_path, permissive_policy())
    object.__setattr__(report, "duplicate_promotion_count", 4)
    with pytest.raises(KnowledgeRegistryError, match="BROKEN_PROMOTION"):
        registry(tmp_path / "replay").admit(report)

    clean = registry(tmp_path / "snapshot")
    result = clean.admit(promotion_report(tmp_path / "fresh", permissive_policy()))
    path = clean.repository.snapshot_root / f"{result.snapshot_uuid}.json"
    raw = json.loads(path.read_text()); raw["repository_digest"] = "f" * 64
    path.write_text(json.dumps(raw))
    with pytest.raises(KnowledgeRegistryError, match="CORRUPT_REGISTRY_SNAPSHOT_REPOSITORY"):
        clean.repository.latest_snapshot()


def test_repository_corruption_and_collision_are_rejected(tmp_path):
    engine = registry(tmp_path)
    result = engine.admit(promotion_report(tmp_path, permissive_policy()))
    item = result.registry_records[0]; path = engine.repository.path_for(item.registry_uuid)
    raw = json.loads(path.read_text()); raw["promotion_digest"] = "e" * 64
    path.write_text(json.dumps(raw))
    with pytest.raises(KnowledgeRegistryError, match="CORRUPT_REGISTRY_REPOSITORY"):
        engine.repository.records()


def test_deterministic_uuid_canonical_json_and_snapshot_chain(tmp_path):
    source_one = promotion_report(tmp_path / "source", permissive_policy())
    first = registry(tmp_path / "one").admit(source_one)
    second = registry(tmp_path / "two").admit(source_one)
    assert first == second and first.report_uuid == second.report_uuid
    item = first.registry_records[0]
    path = KnowledgeRegistryRepository(tmp_path / "one" / "registry").path_for(item.registry_uuid)
    assert path.read_bytes() == json.dumps(item.to_dict(), sort_keys=True,
        separators=(",", ":"), allow_nan=False).encode()

    engine = registry(tmp_path / "chain")
    engine.admit(source_one); initial = engine.repository.latest_snapshot()
    engine.admit(promotion_report(tmp_path / "another", permissive_policy()))
    latest = engine.repository.latest_snapshot()
    assert latest.previous_snapshot_uuid == initial.snapshot_uuid
    assert latest.repository_digest == engine.repository.digest()
