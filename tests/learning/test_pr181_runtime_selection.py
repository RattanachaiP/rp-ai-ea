"""PR181 governed advisory eligibility architecture tests."""

import json
from dataclasses import replace
from pathlib import Path
import sys
from types import SimpleNamespace
from uuid import uuid4

import pytest

sys.path.insert(0, str(Path(__file__).parents[2]))
sys.path.insert(1, str(Path(__file__).parent))

from learning.runtime_knowledge import (
    RuntimeKnowledgeGate,
    RuntimeKnowledgePackage,
    RuntimeKnowledgePackagingReport,
    RuntimeKnowledgeRepository,
    RuntimeKnowledgeSnapshot,
)
from learning.runtime_selection import (
    RuntimeKnowledgeSelectionError,
    RuntimeKnowledgeSelectionPolicy,
    RuntimeKnowledgeSelectionRepository,
    RuntimeKnowledgeSelector,
)
from learning.runtime_selection.models import (
    ELIGIBLE,
    PARTITION_FIELDS,
    SELECTION_SCOPE,
)
from test_pr180_runtime_knowledge import registry_report


def artifacts(root):
    registry_result, registry = registry_report(root)
    runtime_repository = RuntimeKnowledgeRepository(root / "runtime_knowledge")
    packaged = RuntimeKnowledgeGate(
        registry, runtime_repository
    ).prepare_advisory_package(registry_result)
    return packaged, runtime_repository


def selector(root, runtime_repository, policy=None):
    return RuntimeKnowledgeSelector(
        runtime_repository,
        RuntimeKnowledgeSelectionRepository(root / "runtime_selection"),
        policy,
    )


def test_canonical_api_aliases_and_advisory_semantics(tmp_path):
    packaged, runtime_repository = artifacts(tmp_path)
    engine = selector(tmp_path, runtime_repository)
    report = engine.evaluate_eligibility(packaged)
    assert engine.select.__func__ is engine.evaluate_eligibility.__func__
    assert engine.run.__func__ is engine.evaluate_eligibility.__func__
    selection = report.runtime_selections[0]
    assert selection.selection_state == ELIGIBLE
    assert selection.selection_scope == SELECTION_SCOPE
    assert selection.selection_reasons == ("ELIGIBLE_FOR_PR182_CONFIDENCE_EVALUATION",)
    assert selection.advisory_only is report.advisory_only is True


def test_accepts_only_canonical_pr180_artifact_types(tmp_path):
    packaged, runtime_repository = artifacts(tmp_path)
    engine = selector(tmp_path, runtime_repository)
    for value in (None, {}, object(), packaged.runtime_packages):
        with pytest.raises(
            RuntimeKnowledgeSelectionError, match="INVALID_RUNTIME_KNOWLEDGE_INPUT"
        ):
            engine.evaluate_eligibility(value)


def test_selection_retains_complete_policy_partition_lineage_and_evidence(tmp_path):
    packaged, runtime_repository = artifacts(tmp_path)
    report = selector(tmp_path, runtime_repository).evaluate_eligibility(packaged)
    selection = report.runtime_selections[0]
    package = packaged.runtime_packages[0]
    assert selection.selection_policy_uuid == report.selection_policy_uuid
    assert selection.selection_policy_digest == report.selection_policy_digest
    assert selection.source_runtime_package_uuid == package.runtime_package_uuid
    assert selection.source_runtime_package_digest == package.runtime_package_digest
    assert selection.source_registry_digest == package.source_registry_digest
    assert selection.source_promotion_digest == package.source_promotion_digest
    assert selection.source_validation_digest == package.source_validation_digest
    assert selection.source_memory_digest == package.source_memory_digest
    assert selection.source_pattern_hash == package.source_pattern_hash
    assert selection.knowledge_version == package.knowledge_version
    assert selection.source_runtime_package_reasons == package.runtime_package_reasons
    assert selection.source_registry_reasons == package.source_registry_reasons
    assert selection.source_validation_reasons == package.source_validation_reasons
    assert selection.source_promotion_reasons == package.source_promotion_reasons
    assert RuntimeKnowledgePackage(**selection.runtime_package_dict()) == package
    assert all(
        getattr(selection, name) == getattr(report, name) for name in PARTITION_FIELDS
    )


def test_package_snapshot_and_report_source_bindings_and_counters(tmp_path):
    packaged, runtime_repository = artifacts(tmp_path)
    package_report = selector(
        tmp_path / "package", runtime_repository
    ).evaluate_eligibility(packaged.runtime_packages[0])
    snapshot_report = selector(
        tmp_path / "snapshot", runtime_repository
    ).evaluate_eligibility(runtime_repository.latest_snapshot())
    packaging_report = selector(
        tmp_path / "report", runtime_repository
    ).evaluate_eligibility(packaged)
    assert package_report.source_artifact_type == "RUNTIME_KNOWLEDGE_PACKAGE"
    assert (
        package_report.source_runtime_package_uuid
        == packaged.runtime_packages[0].runtime_package_uuid
    )
    assert snapshot_report.source_artifact_type == "RUNTIME_KNOWLEDGE_SNAPSHOT"
    assert packaging_report.source_artifact_type == "RUNTIME_KNOWLEDGE_PACKAGING_REPORT"
    assert packaging_report.source_runtime_packaging_report_uuid == packaged.report_uuid
    assert packaging_report.source_runtime_packaging_report_digest is not None
    for report in (package_report, snapshot_report, packaging_report):
        assert (
            report.processed_package_count
            == report.new_selection_count
            == report.eligible_count
            == 1
        )
        assert (
            report.duplicate_selection_count
            == report.insufficient_selection_evidence_count
            == report.rejected_count
            == 0
        )
        assert report.selection_snapshot_uuid and report.selection_snapshot_digest


def test_replay_is_append_only_and_duplicate_counter_is_exact(tmp_path):
    packaged, runtime_repository = artifacts(tmp_path)
    engine = selector(tmp_path, runtime_repository)
    first = engine.evaluate_eligibility(packaged)
    path = engine.repository.path_for(first.runtime_selections[0].selection_uuid)
    original = path.read_bytes()
    replay = engine.evaluate_eligibility(packaged)
    assert replay.new_selection_count == 0
    assert replay.duplicate_selection_count == 1
    assert replay.selection_snapshot_uuid == first.selection_snapshot_uuid
    assert path.read_bytes() == original


def test_historical_resolution_binds_earliest_canonical_snapshot(tmp_path):
    packaged, runtime_repository = artifacts(tmp_path)
    first = runtime_repository.latest_snapshot()
    values = first.identity_payload()
    values.update(
        previous_snapshot_uuid=first.snapshot_uuid,
        previous_snapshot_digest=first.snapshot_digest,
        source_registry_snapshot_uuid=str(uuid4()),
        source_registry_snapshot_digest="a" * 64,
    )
    second = RuntimeKnowledgeSnapshot.create(**values)
    runtime_repository.save_snapshot(second)
    report = selector(tmp_path, runtime_repository).evaluate_eligibility(
        packaged.runtime_packages[0]
    )
    assert report.source_runtime_snapshot_uuid == first.snapshot_uuid
    assert (
        report.runtime_selections[0].source_runtime_snapshot_uuid == first.snapshot_uuid
    )


def test_classification_gathers_all_reasons_in_canonical_order(tmp_path):
    packaged, runtime_repository = artifacts(tmp_path)
    engine = selector(tmp_path, runtime_repository)
    rejected = SimpleNamespace(
        runtime_package_state="BAD",
        source_registry_state="BAD",
        source_validation_state="BAD",
        source_promotion_state="BAD",
    )
    insufficient = SimpleNamespace(
        runtime_package_state="ADVISORY_PACKAGE_PREPARED",
        source_registry_state="ADVISORY_ENTRY_RECORDED",
        source_validation_state="BAD",
        source_promotion_state="BAD",
    )
    assert engine._classify(rejected) == (
        "REJECTED",
        ("RUNTIME_PACKAGE_STATE_NOT_ELIGIBLE", "REGISTRY_STATE_NOT_ELIGIBLE"),
    )
    assert engine._classify(insufficient) == (
        "INSUFFICIENT_SELECTION_EVIDENCE",
        ("VALIDATION_STATE_INSUFFICIENT", "PROMOTION_STATE_INSUFFICIENT"),
    )


def test_policy_field_and_policy_identity_are_exact():
    policy = RuntimeKnowledgeSelectionPolicy()
    assert policy.required_runtime_package_state == "ADVISORY_PACKAGE_PREPARED"
    assert not hasattr(policy, "minimum_package_integrity")
    changed = RuntimeKnowledgeSelectionPolicy(
        selection_policy_version="PR181-SELECTION-POLICY.2.0"
    )
    assert changed.selection_policy_uuid != policy.selection_policy_uuid
    assert changed.selection_policy_digest != policy.selection_policy_digest


def test_tampered_package_report_snapshot_repository_and_counters_fail_closed(tmp_path):
    packaged, runtime_repository = artifacts(tmp_path)
    engine = selector(tmp_path, runtime_repository)
    broken_package = replace(packaged.runtime_packages[0])
    object.__setattr__(broken_package, "runtime_package_digest", "f" * 64)
    with pytest.raises(
        RuntimeKnowledgeSelectionError,
        match="BROKEN_RUNTIME_PACKAGE|BROKEN_PACKAGE_PROVENANCE",
    ):
        engine.evaluate_eligibility(broken_package)
    damaged = replace(packaged)
    object.__setattr__(damaged, "snapshot_digest", "e" * 64)
    with pytest.raises(
        RuntimeKnowledgeSelectionError, match="BROKEN_RUNTIME_PACKAGING_REPORT"
    ):
        engine.evaluate_eligibility(damaged)
    damaged = replace(packaged)
    object.__setattr__(damaged, "processed_record_count", 99)
    with pytest.raises(
        RuntimeKnowledgeSelectionError,
        match="RUNTIME_PACKAGING_REPORT_COUNTER_MISMATCH",
    ):
        engine.evaluate_eligibility(damaged)


def test_packaging_report_partition_and_package_set_fail_closed(tmp_path):
    packaged, runtime_repository = artifacts(tmp_path)
    package_values = packaged.runtime_packages[0].identity_payload()
    package_values["runtime_engine_version"] = "PR180.forged"
    forged_package = RuntimeKnowledgePackage.create(**package_values)
    values = {
        name: getattr(packaged, name)
        for name in packaged.__dataclass_fields__
        if name != "report_uuid"
    }
    values.update(
        runtime_engine_version="PR180.forged", runtime_packages=(forged_package,)
    )
    forged = RuntimeKnowledgePackagingReport.create(**values)
    with pytest.raises(
        RuntimeKnowledgeSelectionError,
        match="RUNTIME_PACKAGING_REPORT_PARTITION_MISMATCH",
    ):
        selector(tmp_path, runtime_repository).evaluate_eligibility(forged)


def test_repository_policy_and_upstream_partitions_fail_closed(tmp_path):
    packaged, runtime_repository = artifacts(tmp_path)
    engine = selector(tmp_path, runtime_repository)
    engine.evaluate_eligibility(packaged)
    changed = RuntimeKnowledgeSelectionPolicy(
        selection_policy_version="PR181-SELECTION-POLICY.2.0"
    )
    with pytest.raises(
        RuntimeKnowledgeSelectionError, match="MIXED_SELECTION_REPOSITORY_PARTITION"
    ):
        selector(tmp_path, runtime_repository, changed).evaluate_eligibility(packaged)


def test_canonical_serialization_deterministic_identity_and_tamper_detection(tmp_path):
    packaged, runtime_repository = artifacts(tmp_path / "source")
    one = selector(tmp_path / "one", runtime_repository)
    two = selector(tmp_path / "two", runtime_repository)
    left = one.evaluate_eligibility(packaged).runtime_selections[0]
    right = two.evaluate_eligibility(packaged).runtime_selections[0]
    assert left == right
    path = one.repository.path_for(left.selection_uuid)
    assert (
        path.read_bytes()
        == json.dumps(
            left.to_dict(), sort_keys=True, separators=(",", ":"), allow_nan=False
        ).encode()
    )
    raw = json.loads(path.read_text())
    raw["selection_scope"] = "OPERATIONAL"
    path.write_text(json.dumps(raw))
    with pytest.raises(
        RuntimeKnowledgeSelectionError, match="CORRUPT_SELECTION_REPOSITORY"
    ):
        one.evaluate_eligibility(packaged)


def test_snapshot_chain_missing_predecessor_and_multiple_heads_fail_closed(tmp_path):
    packaged, runtime_repository = artifacts(tmp_path)
    engine = selector(tmp_path, runtime_repository)
    report = engine.evaluate_eligibility(packaged)
    snapshot_path = (
        engine.repository.snapshot_root / f"{report.selection_snapshot_uuid}.json"
    )
    raw = json.loads(snapshot_path.read_text())
    raw["previous_snapshot_uuid"] = str(uuid4())
    raw["previous_snapshot_digest"] = "b" * 64
    snapshot_path.write_text(json.dumps(raw))
    with pytest.raises(
        RuntimeKnowledgeSelectionError,
        match="CORRUPT_SELECTION_SNAPSHOT_REPOSITORY|BROKEN_SELECTION_SNAPSHOT_CHAIN",
    ):
        engine.evaluate_eligibility(packaged)
