from dataclasses import replace
import json
from uuid import uuid4

import pytest

from learning.pattern_promotion import (PatternPromotionEngine, PatternPromotionError,
    PatternPromotionRepository, PromotionPolicy)
from learning.pattern_promotion.identity import digest
from learning.pattern_validation.models import PatternValidationReport, ValidationRecord


def validation_record(state="STATISTICALLY_CONSISTENT", **statistics):
    identifier = lambda: str(uuid4())
    hashes = lambda: "a" * 64
    stats = {"sample_count": 50, "support": .8, "confidence": .7, "expectancy": .2,
             "thresholds": {}}
    stats.update(statistics)
    return ValidationRecord.create(validator_version="PR177.2.0",
        validation_policy_version="PR177-POLICY.1.0", validation_config_digest=hashes(),
        source_memory_uuid=identifier(), source_memory_digest=hashes(),
        source_pattern_uuid=identifier(), source_pattern_hash=hashes(), source_report_uuid=identifier(),
        policy_uuid=identifier(), policy_version="PR174", source_attribution_uuid=identifier(),
        source_digest=hashes(), replay_digest=hashes(), evidence_envelope_uuid=identifier(),
        evidence_envelope_digest=hashes(), knowledge_uuid=identifier(), knowledge_version="v1",
        engine_version="PR175", mining_config_digest=hashes(), outcome_contract=("v1", "closed"),
        memory_version="PR176", memory_state="STORED", validation_state=state,
        validation_reasons=("VALIDATED",), validation_statistics=stats,
        validated_at="2026-07-25T00:00:00+00:00", advisory_only=True)


def validation_report(record):
    values = dict(validator_version="PR177.2.0", validation_policy_version="policy",
        validation_config_digest="b" * 64, source_artifact_type="PATTERN_MEMORY_RECORD",
        source_pattern_memory_report_uuid=None, source_pattern_memory_report_digest=None,
        source_snapshot_uuid=None, source_snapshot_digest=None,
        source_memory_uuid=record.source_memory_uuid, source_memory_digest=record.source_memory_digest,
        validation_records=(record,), processed_record_count=1, new_validation_count=1,
        duplicate_validation_count=0,
        statistically_consistent_count=int(record.validation_state == "STATISTICALLY_CONSISTENT"),
        invalid_count=int(record.validation_state == "INVALID"),
        insufficient_count=int(record.validation_state == "INSUFFICIENT_EVIDENCE"),
        repository_digest="c" * 64, snapshot_uuid=str(uuid4()), snapshot_digest="d" * 64,
        generated_at=record.validated_at, advisory_only=True)
    return PatternValidationReport.create(**values)


def test_accepts_only_canonical_validation_artifacts(tmp_path):
    engine = PatternPromotionEngine(PatternPromotionRepository(tmp_path))
    for value in (None, {}, object()):
        with pytest.raises(PatternPromotionError, match="INVALID_VALIDATION_INPUT"):
            engine.promote(value)
    assert engine.promote(validation_report(validation_record())).eligible_count == 1


def test_policy_states_and_thresholds(tmp_path):
    policy = PromotionPolicy(minimum_sample_count=40, minimum_support=.5,
                             minimum_confidence=.6, minimum_expectancy=.1)
    engine = PatternPromotionEngine(PatternPromotionRepository(tmp_path), policy)
    assert engine.promote(validation_record()).promotion_records[0].promotion_state == "PROMOTION_ELIGIBLE"
    assert engine.promote(validation_record("INVALID")).promotion_records[0].promotion_state == "REJECTED"
    pending = engine.promote(validation_record("INSUFFICIENT_EVIDENCE"))
    assert pending.promotion_records[0].promotion_state == "NOT_YET_ELIGIBLE"
    below = engine.promote(validation_record(expectancy=.01))
    assert below.promotion_records[0].promotion_reasons == ("MINIMUM_EXPECTANCY_NOT_MET",)


def test_policy_configuration_is_immutable_and_changes_identity():
    first = PromotionPolicy(); second = PromotionPolicy(minimum_sample_count=31)
    with pytest.raises(Exception):
        first.minimum_sample_count = 1
    assert first.policy_uuid != second.policy_uuid
    assert first.policy_digest != second.policy_digest


def test_deterministic_identity_and_duplicate_replay(tmp_path):
    engine = PatternPromotionEngine(PatternPromotionRepository(tmp_path))
    source = validation_record()
    first = engine.promote(source); second = engine.promote(source)
    assert first.report_uuid == second.report_uuid
    assert first.promotion_records[0] == second.promotion_records[0]
    assert len(engine.repository.records()) == len(engine.repository.snapshots()) == 1


def test_broken_provenance_fails_closed(tmp_path):
    source = validation_record()
    object.__setattr__(source, "validation_digest", "f" * 64)
    with pytest.raises(PatternPromotionError, match="BROKEN_VALIDATION_PROVENANCE"):
        PatternPromotionEngine(PatternPromotionRepository(tmp_path)).promote(source)


def test_repository_and_snapshot_integrity(tmp_path):
    repository = PatternPromotionRepository(tmp_path)
    report = PatternPromotionEngine(repository).promote(validation_record())
    record_path = repository.path_for(report.promotion_records[0].promotion_uuid)
    raw = json.loads(record_path.read_text()); raw["promotion_state"] = "REJECTED"
    record_path.write_text(json.dumps(raw))
    with pytest.raises(PatternPromotionError, match="CORRUPT_PROMOTION_REPOSITORY"):
        repository.records()


def test_broken_snapshot_chain_is_rejected(tmp_path):
    repository = PatternPromotionRepository(tmp_path)
    engine = PatternPromotionEngine(repository)
    engine.promote(validation_record())
    engine.promote(validation_record())
    latest = repository.latest_snapshot()
    path = repository.snapshot_root / f"{latest.snapshot_uuid}.json"
    raw = json.loads(path.read_text()); raw["previous_snapshot_digest"] = digest("tampered")
    path.write_text(json.dumps(raw))
    with pytest.raises(PatternPromotionError, match="CORRUPT_PROMOTION_SNAPSHOT_REPOSITORY"):
        repository.latest_snapshot()
