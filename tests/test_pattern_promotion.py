"""PR176 -> PR177 -> PR178 governance and corruption tests."""
from dataclasses import replace
import json
from pathlib import Path
import sys
from uuid import uuid4
import pytest

sys.path.insert(0, str(Path(__file__).parent / "learning"))
from test_pr176_pattern_memory import mining_report

from learning.pattern_memory import PatternMemoryEngine, PatternMemoryRepository
from learning.pattern_promotion import (PatternPromotionEngine, PatternPromotionError,
    PatternPromotionRepository, PromotionPolicy, PromotionRecord)
from learning.pattern_validation import (PatternValidationEngine, PatternValidationRepository,
                                         ValidationConfig, ValidationRecord)
from learning.pattern_validation.identity import digest as validation_digest


def pipeline(tmp_path, *, validation_config=None):
    memory = PatternMemoryEngine(PatternMemoryRepository(tmp_path / "memory")).create(mining_report())
    validation = PatternValidationEngine(PatternValidationRepository(tmp_path / "validation"),
                                         config=validation_config).validate(memory)
    return memory, validation


def record_values(record):
    return {k: v for k, v in record.to_dict().items() if k not in ("validation_uuid", "validation_digest")}


def engine(tmp_path, policy=None, version=None):
    return PatternPromotionEngine(PatternPromotionRepository(tmp_path / "promotion"), policy,
                                  promotion_engine_version=version)


def test_real_pipeline_complete_provenance_and_exact_source_binding(tmp_path):
    memory, validation = pipeline(tmp_path)
    result = engine(tmp_path).assess(validation); item = result.promotion_records[0]
    source = validation.validation_records[0]
    assert result.source_artifact_type == "PATTERN_VALIDATION_REPORT"
    assert result.source_validation_report_uuid == validation.report_uuid
    assert result.source_validation_report_digest == validation_digest(validation.to_dict())
    assert result.source_validation_snapshot_uuid == validation.snapshot_uuid
    assert result.source_validation_snapshot_digest == validation.snapshot_digest
    assert result.source_validation_repository_digest == validation.repository_digest
    pairs = {
        "source_validation_uuid": "validation_uuid", "source_validation_digest": "validation_digest",
        "source_validator_version": "validator_version", "source_memory_uuid": "source_memory_uuid",
        "source_memory_digest": "source_memory_digest", "source_pattern_hash": "source_pattern_hash",
        "source_policy_uuid": "policy_uuid", "source_policy_version": "policy_version",
        "source_engine_version": "engine_version", "source_validation_state": "validation_state",
        "source_validation_statistics": "validation_statistics"}
    for target, origin in pairs.items(): assert getattr(item, target) == getattr(source, origin)
    assert item.source_memory_uuid == memory.memory_records[0].memory_uuid
    assert item.promotion_policy_uuid == result.promotion_policy_uuid
    assert item.promotion_policy_digest == result.promotion_policy_digest
    assert item.promotion_engine_version == result.promotion_engine_version == "PR178.2.0"
    assert item.threshold_monotonicity_result == "PASSED"


def test_neutral_states_and_independent_default_selectivity(tmp_path):
    _, validation = pipeline(tmp_path)
    default = engine(tmp_path / "default").assess(validation)
    assert default.promotion_records[0].promotion_state == "INSUFFICIENT_PROMOTION_EVIDENCE"
    permissive = PromotionPolicy(minimum_sample_count=30, minimum_support=0,
        minimum_confidence=0, minimum_expectancy=0)
    met = engine(tmp_path / "met", permissive).assess(validation)
    assert met.promotion_records[0].promotion_state == "POLICY_CRITERIA_MET"


def test_invalid_and_insufficient_pr177_states_map_neutrally(tmp_path):
    _, insufficient = pipeline(tmp_path / "insufficient", validation_config=ValidationConfig(minimum_sample_count=31))
    policy = PromotionPolicy(minimum_sample_count=60, minimum_support=.6,
                             minimum_confidence=.55, minimum_expectancy=.05)
    assert engine(tmp_path / "a", policy).assess(insufficient).insufficient_promotion_evidence_count == 1
    _, invalid = pipeline(tmp_path / "invalid", validation_config=ValidationConfig(minimum_expectancy=99))
    strict = PromotionPolicy(minimum_sample_count=60, minimum_support=.6,
                             minimum_confidence=.55, minimum_expectancy=99)
    assert engine(tmp_path / "b", strict).assess(invalid).rejected_count == 1


def test_single_record_binding_replay_counts_and_snapshot_reuse(tmp_path):
    _, validation = pipeline(tmp_path); source = validation.validation_records[0]
    promotion = engine(tmp_path)
    first = promotion.assess(source); replay = promotion.assess(source)
    assert first.source_artifact_type == "VALIDATION_RECORD"
    assert first.source_validation_uuid == source.validation_uuid
    assert first.new_promotion_count == 1 and first.duplicate_promotion_count == 0
    assert replay.new_promotion_count == 0 and replay.duplicate_promotion_count == 1
    assert replay.snapshot_uuid == first.snapshot_uuid
    assert len(promotion.repository.snapshots()) == 1


def test_snapshot_chain_progression_and_policy_engine_binding(tmp_path):
    promotion = engine(tmp_path)
    promotion.assess(pipeline(tmp_path / "one")[1]); first = promotion.repository.latest_snapshot()
    promotion.assess(pipeline(tmp_path / "two")[1]); second = promotion.repository.latest_snapshot()
    assert second.previous_snapshot_uuid == first.snapshot_uuid
    assert second.record_count == 2
    assert second.promotion_policy_uuid == promotion.policy.policy_uuid
    assert second.promotion_policy_digest == promotion.policy.policy_digest
    assert second.promotion_engine_version == promotion.promotion_engine_version


def test_only_exact_canonical_inputs_and_assess_api(tmp_path):
    promotion = engine(tmp_path)
    assert not hasattr(promotion, "promote")
    for value in (None, {}, object()):
        with pytest.raises(PatternPromotionError, match="INVALID_VALIDATION_INPUT"):
            promotion.assess(value)


def test_policy_identity_immutability_constraint_and_artifact_identity(tmp_path):
    _, validation = pipeline(tmp_path)
    first = PromotionPolicy(); changed = PromotionPolicy(minimum_sample_count=61)
    with pytest.raises(Exception): first.minimum_sample_count = 1
    assert first.policy_uuid != changed.policy_uuid and first.policy_digest != changed.policy_digest
    one = engine(tmp_path / "one", first).assess(validation).promotion_records[0]
    two = engine(tmp_path / "two", changed).assess(validation).promotion_records[0]
    assert one.promotion_uuid != two.promotion_uuid
    with pytest.raises(ValueError, match="INVALID_PROMOTION_POLICY"):
        PromotionPolicy(required_validation_state="INVALID")


def test_promotion_policy_downgrade_fails_closed(tmp_path):
    _, validation = pipeline(tmp_path, validation_config=ValidationConfig(minimum_sample_count=70))
    with pytest.raises(PatternPromotionError, match="PROMOTION_POLICY_DOWNGRADE"):
        engine(tmp_path, PromotionPolicy()).assess(validation)


def test_mixed_policy_and_engine_repository_rejected(tmp_path):
    _, validation = pipeline(tmp_path)
    repository = PatternPromotionRepository(tmp_path / "promotion")
    PatternPromotionEngine(repository).assess(validation)
    with pytest.raises(PatternPromotionError, match="PROMOTION_POLICY_DIGEST_MISMATCH"):
        PatternPromotionEngine(repository, PromotionPolicy(minimum_sample_count=61)).assess(validation)
    with pytest.raises(PatternPromotionError, match="PROMOTION_ENGINE_VERSION_MISMATCH"):
        PatternPromotionEngine(repository, promotion_engine_version="PR178.changed").assess(validation)


def test_random_uuid_digest_and_nested_record_corruption_rejected(tmp_path):
    _, validation = pipeline(tmp_path); item = engine(tmp_path).assess(validation).promotion_records[0]
    for field, value in (("promotion_uuid", str(uuid4())), ("promotion_digest", "f" * 64),
                         ("source_validation_uuid", str(uuid4())),
                         ("source_validation_digest", "e" * 64)):
        with pytest.raises(ValueError, match="INVALID_PROMOTION_RECORD"):
            PromotionRecord(**{**item.to_dict(), field: value})
    for stats in ({"x": float("nan")}, {"x": float("inf")}, {1: "bad"}):
        with pytest.raises((ValueError, TypeError)):
            PromotionRecord(**{**item.to_dict(), "source_validation_statistics": stats})


def test_malformed_missing_and_wrong_digest_thresholds_rejected(tmp_path):
    _, validation = pipeline(tmp_path); source = validation.validation_records[0]
    for thresholds, config_digest, error in (({}, validation_digest({}), "MALFORMED_VALIDATION_THRESHOLDS"),
            ({"minimum_sample_count": 30}, validation_digest({"minimum_sample_count": 30}),
             "MALFORMED_VALIDATION_THRESHOLDS"),
            ({"minimum_sample_count": 30, "minimum_support": 0, "minimum_confidence": 0,
              "minimum_expectancy": 0}, "f" * 64, "VALIDATION_CONFIG_DIGEST_MISMATCH")):
        stats = {**dict(source.validation_statistics), "thresholds": thresholds}
        changed = ValidationRecord.create(**{**record_values(source), "validation_statistics": stats,
                                             "validation_config_digest": config_digest})
        with pytest.raises(PatternPromotionError, match=error): engine(tmp_path / str(len(thresholds))).assess(changed)


def test_tampered_source_report_and_nonadvisory_fail_closed(tmp_path):
    _, report = pipeline(tmp_path)
    object.__setattr__(report, "report_uuid", str(uuid4()))
    with pytest.raises(PatternPromotionError, match="BROKEN_VALIDATION_REPORT"):
        engine(tmp_path / "uuid").assess(report)
    _, report = pipeline(tmp_path / "advisory"); object.__setattr__(report, "advisory_only", False)
    with pytest.raises(PatternPromotionError, match="BROKEN_VALIDATION_REPORT"):
        engine(tmp_path / "advisory-out").assess(report)


def test_repository_record_and_snapshot_tampering_detected(tmp_path):
    _, validation = pipeline(tmp_path); promotion = engine(tmp_path); result = promotion.assess(validation)
    record_path = promotion.repository.path_for(result.promotion_records[0].promotion_uuid)
    raw = json.loads(record_path.read_text()); raw["promotion_digest"] = "f" * 64
    record_path.write_text(json.dumps(raw))
    with pytest.raises(PatternPromotionError, match="CORRUPT_PROMOTION_REPOSITORY"):
        promotion.repository.records()

    clean = engine(tmp_path / "snapshot"); result = clean.assess(validation)
    path = clean.repository.snapshot_root / f"{result.snapshot_uuid}.json"
    raw = json.loads(path.read_text()); raw["snapshot_digest"] = "e" * 64; path.write_text(json.dumps(raw))
    with pytest.raises(PatternPromotionError, match="CORRUPT_PROMOTION_SNAPSHOT_REPOSITORY"):
        clean.repository.latest_snapshot()


def test_canonical_storage_and_report_identity_are_deterministic(tmp_path):
    _, validation = pipeline(tmp_path)
    first = engine(tmp_path / "one").assess(validation); second = engine(tmp_path / "two").assess(validation)
    assert first == second and first.report_uuid == second.report_uuid
    repository = PatternPromotionRepository(tmp_path / "one" / "promotion")
    item = first.promotion_records[0]
    assert repository.path_for(item.promotion_uuid).read_bytes() == json.dumps(
        item.to_dict(), sort_keys=True, separators=(",", ":"), allow_nan=False).encode()
