"""PR180 governed runtime knowledge consumption tests."""

import json
from dataclasses import replace
from pathlib import Path
import sys

import pytest

sys.path.insert(0, str(Path(__file__).parents[2]))
sys.path.insert(1, str(Path(__file__).parent))

from learning.knowledge_registry import KnowledgeRegistryEngine, KnowledgeRegistryRepository
from learning.pattern_memory import PatternMemoryEngine, PatternMemoryRepository
from learning.pattern_promotion import PatternPromotionEngine, PatternPromotionRepository, PromotionPolicy
from learning.pattern_validation import PatternValidationEngine, PatternValidationRepository
from learning.runtime_knowledge import (RuntimeKnowledgeError, RuntimeKnowledgeGate,
                                        RuntimeKnowledgeRepository)
from test_pr176_pattern_memory import mining_report


def registry_report(root):
    memory = PatternMemoryEngine(PatternMemoryRepository(root / "memory")).create(mining_report())
    validation = PatternValidationEngine(
        PatternValidationRepository(root / "validation")).validate(memory)
    policy = PromotionPolicy(minimum_sample_count=30, minimum_support=0,
                             minimum_confidence=0, minimum_expectancy=0)
    promotion = PatternPromotionEngine(
        PatternPromotionRepository(root / "promotion"), policy).assess(validation)
    registry_repository = KnowledgeRegistryRepository(root / "registry")
    report = KnowledgeRegistryEngine(registry_repository).record_admission(promotion)
    return report, registry_repository


def gate(root, registry_repository, **versions):
    return RuntimeKnowledgeGate(registry_repository,
                                RuntimeKnowledgeRepository(root / "runtime_knowledge"), **versions)


def test_accepts_only_canonical_registry_artifacts_and_is_advisory(tmp_path):
    report, source = registry_report(tmp_path)
    engine = gate(tmp_path, source)
    for value in (None, {}, object(), report.registry_records):
        with pytest.raises(RuntimeKnowledgeError, match="INVALID_REGISTRY"):
            engine.consume(value)
    result = engine.consume(report)
    package = result.runtime_packages[0]
    assert package.advisory_only is result.advisory_only is True
    assert package.registry_uuid == report.registry_records[0].registry_uuid
    assert package.knowledge_uuid == report.registry_records[0].knowledge_uuid
    with pytest.raises(Exception):
        package.knowledge_version = "changed"


def test_registry_report_and_record_replay_are_deterministic(tmp_path):
    report, source = registry_report(tmp_path)
    engine = gate(tmp_path, source)
    first = engine.consume(report)
    replay = engine.consume(report)
    record_replay = engine.consume(report.registry_records[0])
    assert first.runtime_packages == replay.runtime_packages == record_replay.runtime_packages
    assert replay.duplicate_package_count == record_replay.duplicate_package_count == 1
    assert first.report_uuid != record_replay.report_uuid
    assert len(engine.repository.packages()) == 1


def test_registry_corruption_repository_and_snapshot_mismatch_fail_closed(tmp_path):
    report, source = registry_report(tmp_path)
    record_path = source.path_for(report.registry_records[0].registry_uuid)
    raw = json.loads(record_path.read_text())
    raw["registry_digest"] = "f" * 64
    record_path.write_text(json.dumps(raw))
    with pytest.raises(RuntimeKnowledgeError, match="BROKEN_REGISTRY_PROVENANCE"):
        gate(tmp_path, source).consume(report)

    clean_report, clean_source = registry_report(tmp_path / "clean")
    damaged = replace(clean_report)
    object.__setattr__(damaged, "snapshot_digest", "e" * 64)
    with pytest.raises(RuntimeKnowledgeError, match="SNAPSHOT_MISMATCH"):
        gate(tmp_path / "clean", clean_source).consume(damaged)


def test_repository_digest_mismatch_and_broken_provenance_fail_closed(tmp_path):
    report, source = registry_report(tmp_path)
    damaged = replace(report)
    object.__setattr__(damaged, "repository_digest", "e" * 64)
    with pytest.raises(RuntimeKnowledgeError, match="REGISTRY_DIGEST_MISMATCH"):
        gate(tmp_path, source).consume(damaged)

    record = replace(report.registry_records[0])
    object.__setattr__(record, "source_memory_uuid", record.knowledge_uuid)
    with pytest.raises(RuntimeKnowledgeError, match="BROKEN_REGISTRY_PROVENANCE"):
        gate(tmp_path, source).consume(record)


def test_engine_policy_and_registry_partitions_fail_closed(tmp_path):
    report, source = registry_report(tmp_path)
    engine = gate(tmp_path, source)
    engine.consume(report)
    with pytest.raises(RuntimeKnowledgeError, match="ENGINE_VERSION_MISMATCH"):
        gate(tmp_path, source, runtime_engine_version="PR180.changed").consume(report)
    with pytest.raises(RuntimeKnowledgeError, match="POLICY_VERSION_MISMATCH"):
        gate(tmp_path, source,
             runtime_policy_version="PR180-CONSUMPTION-POLICY.changed").consume(report)


def test_deterministic_uuid_append_only_and_canonical_serialization(tmp_path):
    report, source = registry_report(tmp_path / "source")
    first = gate(tmp_path / "one", source).consume(report)
    second = gate(tmp_path / "two", source).consume(report)
    assert first.runtime_packages == second.runtime_packages
    package = first.runtime_packages[0]
    path = RuntimeKnowledgeRepository(tmp_path / "one" / "runtime_knowledge").path_for(
        package.runtime_package_uuid)
    assert path.read_bytes() == json.dumps(package.to_dict(), sort_keys=True,
                                           separators=(",", ":"), allow_nan=False).encode()
    original = path.read_bytes()
    gate(tmp_path / "one", source).consume(report)
    assert path.read_bytes() == original


def test_source_snapshot_is_bound_to_runtime_snapshot(tmp_path):
    report, source = registry_report(tmp_path)
    result = gate(tmp_path, source).consume(report)
    runtime_snapshot = RuntimeKnowledgeRepository(
        tmp_path / "runtime_knowledge").latest_snapshot()
    assert runtime_snapshot.snapshot_uuid == result.snapshot_uuid
    assert runtime_snapshot.source_registry_snapshot_uuid == report.snapshot_uuid
    assert runtime_snapshot.source_registry_repository_digest == report.repository_digest
