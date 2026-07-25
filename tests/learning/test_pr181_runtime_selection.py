"""PR181 governed Runtime knowledge selection tests."""

import json
from dataclasses import replace
from pathlib import Path
import sys
import pytest

sys.path.insert(0, str(Path(__file__).parents[2]))
sys.path.insert(1, str(Path(__file__).parent))
from learning.runtime_knowledge import (
    RuntimeKnowledgeGate,
    RuntimeKnowledgePackage,
    RuntimeKnowledgePackagingReport,
    RuntimeKnowledgeRepository,
)
from learning.runtime_selection import (
    RuntimeKnowledgeSelectionError,
    RuntimeKnowledgeSelectionPolicy,
    RuntimeKnowledgeSelectionRepository,
    RuntimeKnowledgeSelector,
)
from test_pr180_runtime_knowledge import registry_report


def artifacts(root):
    report, registry = registry_report(root)
    runtime_repository = RuntimeKnowledgeRepository(root / "runtime_knowledge")
    packaged = RuntimeKnowledgeGate(
        registry, runtime_repository
    ).prepare_advisory_package(report)
    return packaged, runtime_repository


def selector(root, runtime_repository, policy=None):
    return RuntimeKnowledgeSelector(
        runtime_repository,
        RuntimeKnowledgeSelectionRepository(root / "runtime_selection"),
        policy,
    )


def test_accepts_only_pr180_artifacts_and_selected_is_advisory(tmp_path):
    packaged, runtime_repository = artifacts(tmp_path)
    engine = selector(tmp_path, runtime_repository)
    for source in (None, {}, object(), packaged.runtime_packages):
        with pytest.raises(
            RuntimeKnowledgeSelectionError, match="INVALID_RUNTIME_KNOWLEDGE_INPUT"
        ):
            engine.select(source)
    result = engine.select(packaged)
    selection = engine.repository.selections()[0]
    assert result.selected_count == 1
    assert selection.selection_state == "SELECTED"
    assert selection.selection_reason == "ELIGIBLE_FOR_RUNTIME_CONFIDENCE_EVALUATION"
    assert selection.advisory_only is result.advisory_only is True
    with pytest.raises(Exception):
        selection.selection_state = "APPLIED"


def test_package_snapshot_and_report_replay_are_deterministic(tmp_path):
    packaged, runtime_repository = artifacts(tmp_path)
    engine = selector(tmp_path, runtime_repository)
    first = engine.select(packaged)
    second = engine.select(packaged.runtime_packages[0])
    third = engine.select(runtime_repository.latest_snapshot())
    assert second.duplicate_count == third.duplicate_count == 1
    assert (
        first.repository_digest == second.repository_digest == third.repository_digest
    )
    assert len(engine.repository.selections()) == 1


def test_broken_package_provenance_snapshot_and_repository_fail_closed(tmp_path):
    packaged, runtime_repository = artifacts(tmp_path)
    broken = replace(packaged.runtime_packages[0])
    object.__setattr__(broken, "runtime_package_digest", "f" * 64)
    with pytest.raises(
        RuntimeKnowledgeSelectionError,
        match="BROKEN_RUNTIME_PACKAGE|BROKEN_PACKAGE_PROVENANCE",
    ):
        selector(tmp_path, runtime_repository).select(broken)
    damaged = replace(packaged)
    object.__setattr__(damaged, "snapshot_digest", "e" * 64)
    with pytest.raises(
        RuntimeKnowledgeSelectionError,
        match="BROKEN_RUNTIME_PACKAGING_REPORT|SNAPSHOT_MISMATCH",
    ):
        selector(tmp_path, runtime_repository).select(damaged)
    damaged = replace(packaged)
    object.__setattr__(damaged, "repository_digest", "e" * 64)
    with pytest.raises(
        RuntimeKnowledgeSelectionError,
        match="BROKEN_RUNTIME_PACKAGING_REPORT|REPOSITORY_MISMATCH",
    ):
        selector(tmp_path, runtime_repository).select(damaged)


def test_policy_mismatch_and_replay_collision_fail_closed(tmp_path):
    packaged, runtime_repository = artifacts(tmp_path)
    engine = selector(tmp_path, runtime_repository)
    engine.select(packaged)
    changed = RuntimeKnowledgeSelectionPolicy(
        selection_policy_version="PR181-SELECTION-POLICY.2.0"
    )
    with pytest.raises(
        RuntimeKnowledgeSelectionError, match="SELECTION_POLICY_MISMATCH"
    ):
        selector(tmp_path, runtime_repository, changed).select(packaged)
    path = engine.repository.path_for(engine.repository.selections()[0].selection_uuid)
    raw = json.loads(path.read_text())
    raw["selection_digest"] = "f" * 64
    path.write_text(json.dumps(raw))
    with pytest.raises(
        RuntimeKnowledgeSelectionError, match="CORRUPT_SELECTION_REPOSITORY"
    ):
        engine.select(packaged)


def test_packaging_policy_partition_mismatch_fails_closed(tmp_path):
    packaged, runtime_repository = artifacts(tmp_path)
    package_values = packaged.runtime_packages[0].identity_payload()
    package_values["runtime_engine_version"] = "PR180.forged"
    forged_package = RuntimeKnowledgePackage.create(**package_values)
    report_values = packaged.identity_payload()
    report_values["runtime_engine_version"] = "PR180.forged"
    report_values["runtime_packages"] = (forged_package,)
    forged_report = RuntimeKnowledgePackagingReport.create(**report_values)

    with pytest.raises(
        RuntimeKnowledgeSelectionError, match="RUNTIME_PACKAGING_POLICY_MISMATCH"
    ):
        selector(tmp_path, runtime_repository).select(forged_report)


def test_deterministic_identity_canonical_append_only_storage(tmp_path):
    packaged, runtime_repository = artifacts(tmp_path / "source")
    one = selector(tmp_path / "one", runtime_repository)
    two = selector(tmp_path / "two", runtime_repository)
    one.select(packaged)
    two.select(packaged)
    left = one.repository.selections()[0]
    right = two.repository.selections()[0]
    assert left == right
    path = one.repository.path_for(left.selection_uuid)
    original = path.read_bytes()
    assert (
        original
        == json.dumps(
            left.to_dict(), sort_keys=True, separators=(",", ":"), allow_nan=False
        ).encode()
    )
    one.select(packaged)
    assert path.read_bytes() == original


def test_snapshot_chain_detects_repository_tampering(tmp_path):
    packaged, runtime_repository = artifacts(tmp_path)
    engine = selector(tmp_path, runtime_repository)
    engine.select(packaged)
    path = engine.repository.path_for(engine.repository.selections()[0].selection_uuid)
    path.unlink()
    with pytest.raises(
        RuntimeKnowledgeSelectionError, match="SELECTION_SNAPSHOT_MISMATCH"
    ):
        engine.select(packaged)
