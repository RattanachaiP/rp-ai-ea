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
    KnowledgeRegistryRepository, RegistryAdmissionPolicy, RegistryRecord)
from learning.pattern_memory import PatternMemoryEngine, PatternMemoryRepository
from learning.pattern_promotion import PatternPromotionEngine, PatternPromotionRepository, PromotionPolicy
from learning.pattern_validation import PatternValidationEngine, PatternValidationRepository, ValidationConfig


def promotion_report(tmp_path, policy=None):
    memory = PatternMemoryEngine(PatternMemoryRepository(tmp_path / "memory")).create(mining_report())
    validation = PatternValidationEngine(
        PatternValidationRepository(tmp_path / "validation")).validate(memory)
    return PatternPromotionEngine(PatternPromotionRepository(tmp_path / "promotion"),
                                  policy).assess(validation)


def registry(tmp_path, version=None):
    return KnowledgeRegistryEngine(KnowledgeRegistryRepository(tmp_path / "registry"),
                                   registry_engine_version=version)


def permissive_policy():
    return PromotionPolicy(minimum_sample_count=30, minimum_support=0,
                           minimum_confidence=0, minimum_expectancy=0)


def test_accepts_only_canonical_pr178_artifacts(tmp_path):
    engine = registry(tmp_path)
    for value in (None, {}, object(), "promotion"):
        with pytest.raises(KnowledgeRegistryError, match="INVALID_PROMOTION_ARTIFACT"):
            engine.record_admission(value)


def test_registered_is_immutable_advisory_admission_only(tmp_path):
    report = promotion_report(tmp_path, permissive_policy())
    result = registry(tmp_path).record_admission(report); item = result.registry_records[0]
    assert item.registry_state == "ADVISORY_ENTRY_RECORDED" and item.advisory_only is True
    assert result.advisory_entry_recorded_count == 1 and result.rejected_count == 0
    assert item.source_promotion_uuid == report.promotion_records[0].promotion_uuid
    assert item.source_validation_uuid == report.promotion_records[0].source_validation_uuid
    with pytest.raises(Exception): item.registry_state = "NOT_ADMITTED"


def test_nonqualifying_promotions_are_not_admitted(tmp_path):
    report = promotion_report(tmp_path)
    result = registry(tmp_path).record_admission(report)
    assert result.registry_records[0].registry_state == "NOT_ADMITTED"
    assert result.advisory_entry_recorded_count == 0 and result.not_admitted_count == 1 and result.rejected_count == 0


def test_rejected_promotion_remains_separate_from_not_admitted(tmp_path):
    memory = PatternMemoryEngine(PatternMemoryRepository(tmp_path / "memory")).create(mining_report())
    config = ValidationConfig(minimum_expectancy=99)
    validation = PatternValidationEngine(PatternValidationRepository(tmp_path / "validation"),
                                         config=config).validate(memory)
    policy = PromotionPolicy(minimum_sample_count=config.minimum_sample_count,
        minimum_support=config.minimum_support, minimum_confidence=config.minimum_confidence,
        minimum_expectancy=config.minimum_expectancy)
    promotion = PatternPromotionEngine(PatternPromotionRepository(tmp_path / "promotion"),
                                       policy).assess(validation)
    result = registry(tmp_path).record_admission(promotion)
    assert result.registry_records[0].registry_state == "REJECTED"
    assert result.rejected_count == 1 and result.not_admitted_count == 0


def test_single_record_input_and_duplicate_replay_are_safe(tmp_path):
    record = promotion_report(tmp_path, permissive_policy()).promotion_records[0]
    engine = registry(tmp_path)
    first = engine.record_admission(record); replay = engine.record_admission(record)
    assert first.source_artifact_type == "PROMOTION_RECORD"
    assert first.duplicate_registry_record_count == 0 and replay.duplicate_registry_record_count == 1
    assert first.registry_records == replay.registry_records
    assert first.snapshot_uuid == replay.snapshot_uuid
    assert len(engine.repository.records()) == len(engine.repository.snapshots()) == 1


def test_complete_provenance_and_registry_identity_mismatch_fail_closed(tmp_path):
    report = promotion_report(tmp_path, permissive_policy())
    damaged = report.promotion_records[0]
    object.__setattr__(damaged, "source_validation_uuid", str(uuid4()))
    with pytest.raises(KnowledgeRegistryError, match="BROKEN_PROMOTION"):
        registry(tmp_path / "damaged").record_admission(damaged)

    item = registry(tmp_path / "clean").record_admission(
        promotion_report(tmp_path / "second", permissive_policy())).registry_records[0]
    with pytest.raises(ValueError, match="INVALID_REGISTRY_RECORD"):
        RegistryRecord(**{**item.to_dict(), "registry_uuid": str(uuid4())})


def test_mixed_promotion_policy_and_engine_are_rejected(tmp_path):
    engine = registry(tmp_path)
    engine.record_admission(promotion_report(tmp_path / "one", permissive_policy()))
    changed = PromotionPolicy(minimum_sample_count=31, minimum_support=0,
                              minimum_confidence=0, minimum_expectancy=0)
    with pytest.raises(KnowledgeRegistryError, match="PROMOTION_POLICY_UUID_MISMATCH"):
        engine.record_admission(promotion_report(tmp_path / "two", changed))
    other = promotion_report(tmp_path / "three", permissive_policy())
    object.__setattr__(other, "promotion_engine_version", "PR178.changed")
    with pytest.raises(KnowledgeRegistryError, match="BROKEN_PROMOTION_REPORT"):
        engine.record_admission(other)


def test_report_replay_and_snapshot_provenance_tampering_fail_closed(tmp_path):
    report = promotion_report(tmp_path, permissive_policy())
    object.__setattr__(report, "duplicate_promotion_count", 4)
    with pytest.raises(KnowledgeRegistryError, match="BROKEN_PROMOTION"):
        registry(tmp_path / "replay").record_admission(report)

    clean = registry(tmp_path / "snapshot")
    result = clean.record_admission(promotion_report(tmp_path / "fresh", permissive_policy()))
    path = clean.repository.snapshot_root / f"{result.snapshot_uuid}.json"
    raw = json.loads(path.read_text()); raw["repository_digest"] = "f" * 64
    path.write_text(json.dumps(raw))
    with pytest.raises(KnowledgeRegistryError, match="CORRUPT_REGISTRY_SNAPSHOT_REPOSITORY"):
        clean.repository.latest_snapshot()


def test_repository_corruption_and_collision_are_rejected(tmp_path):
    engine = registry(tmp_path)
    result = engine.record_admission(promotion_report(tmp_path, permissive_policy()))
    item = result.registry_records[0]; path = engine.repository.path_for(item.registry_uuid)
    raw = json.loads(path.read_text()); raw["promotion_digest"] = "e" * 64
    path.write_text(json.dumps(raw))
    with pytest.raises(KnowledgeRegistryError, match="CORRUPT_REGISTRY_REPOSITORY"):
        engine.repository.records()


def test_deterministic_uuid_canonical_json_and_snapshot_chain(tmp_path):
    source_one = promotion_report(tmp_path / "source", permissive_policy())
    first = registry(tmp_path / "one").record_admission(source_one)
    second = registry(tmp_path / "two").record_admission(source_one)
    assert first == second and first.report_uuid == second.report_uuid
    item = first.registry_records[0]
    path = KnowledgeRegistryRepository(tmp_path / "one" / "registry").path_for(item.registry_uuid)
    assert path.read_bytes() == json.dumps(item.to_dict(), sort_keys=True,
        separators=(",", ":"), allow_nan=False).encode()

    engine = registry(tmp_path / "chain")
    engine.record_admission(source_one); initial = engine.repository.latest_snapshot()
    engine.record_admission(promotion_report(tmp_path / "another", permissive_policy()))
    latest = engine.repository.latest_snapshot()
    assert latest.previous_snapshot_uuid == initial.snapshot_uuid
    assert latest.repository_digest == engine.repository.digest()


def test_complete_pr178_provenance_and_exact_report_source_binding(tmp_path):
    source = promotion_report(tmp_path, permissive_policy())
    result = registry(tmp_path).record_admission(source); item = result.registry_records[0]
    promotion = source.promotion_records[0]
    direct = {"source_promotion_uuid": "promotion_uuid", "source_promotion_digest": "promotion_digest",
        "source_promotion_engine_version": "promotion_engine_version",
        "source_promotion_policy_uuid": "promotion_policy_uuid",
        "source_promotion_policy_digest": "promotion_policy_digest",
        "source_promotion_policy_version": "promotion_policy_version",
        "source_promotion_state": "promotion_state", "source_promotion_reasons": "promotion_reasons",
        "source_promotion_created_at": "created_at"}
    for target, origin in direct.items(): assert getattr(item, target) == getattr(promotion, origin)
    for name in promotion.__dataclass_fields__:
        if name.startswith("source_") or name in ("replay_digest", "evidence_envelope_uuid",
                "evidence_envelope_digest", "knowledge_uuid", "knowledge_version",
                "mining_config_digest", "outcome_contract", "memory_version", "memory_state",
                "promotion_policy_thresholds", "threshold_monotonicity_result"):
            assert dict(item.to_dict())[name] == dict(promotion.to_dict())[name]
    assert result.source_promotion_report_uuid == source.report_uuid
    assert result.source_promotion_snapshot_uuid == source.snapshot_uuid
    assert result.source_promotion_snapshot_digest == source.snapshot_digest
    assert result.source_promotion_repository_digest == source.repository_digest
    assert result.snapshot_digest == registry(tmp_path).repository.latest_snapshot().snapshot_digest


def test_admission_policy_is_immutable_deterministic_and_partition_bound(tmp_path):
    default = RegistryAdmissionPolicy()
    constrained = RegistryAdmissionPolicy(required_promotion_engine_version="PR178.2.0")
    assert default.registry_admission_policy_uuid != constrained.registry_admission_policy_uuid
    assert default.registry_admission_policy_digest != constrained.registry_admission_policy_digest
    with pytest.raises(Exception): default.accepted_promotion_state = "REJECTED"
    source = promotion_report(tmp_path / "source", permissive_policy())
    repository = KnowledgeRegistryRepository(tmp_path / "registry")
    KnowledgeRegistryEngine(repository, default).record_admission(source)
    with pytest.raises(KnowledgeRegistryError, match="REGISTRY_ADMISSION_POLICY_UUID_MISMATCH"):
        KnowledgeRegistryEngine(repository, constrained).record_admission(source)


def test_engine_identity_changes_all_artifact_identities(tmp_path):
    source = promotion_report(tmp_path / "source", permissive_policy())
    first = registry(tmp_path / "one", "PR179.2.0").record_admission(source)
    second = registry(tmp_path / "two", "PR179.changed").record_admission(source)
    assert first.registry_records[0].registry_uuid != second.registry_records[0].registry_uuid
    assert first.snapshot_uuid != second.snapshot_uuid and first.report_uuid != second.report_uuid
