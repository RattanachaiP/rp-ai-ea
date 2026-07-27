"""PR189 governed advisory execution package assembly tests."""

from dataclasses import FrozenInstanceError, replace
from pathlib import Path
import json
import sys

import pytest

sys.path.insert(0, str(Path(__file__).parents[2]))
sys.path.insert(1, str(Path(__file__).parent))

from learning.execution_package import *
from learning.execution_package.identity import canonical_bytes
from learning.execution_feasibility import ExecutionFeasibilityRepository
from test_pr188_execution_feasibility import setup_engine as setup_feasibility_engine


def setup_engine(root, with_evidence=True):
    readiness, environment, feasibility_engine = setup_feasibility_engine(root, with_evidence=with_evidence)
    feasibility = feasibility_engine.run(readiness, environment).execution_feasibility_records[0]
    engine = GovernedExecutionPackageAssemblyEngine(
        feasibility_engine.readiness_repository, feasibility_engine.environment_repository,
        feasibility_engine.repository, ExecutionPackageRepository(root / "execution_package"))
    return readiness, environment, feasibility, engine


def test_package_assembly_is_advisory_immutable_and_deterministic(tmp_path):
    readiness, environment, feasibility, engine = setup_engine(tmp_path)
    package, report = engine.run(readiness, environment, feasibility)
    replay, replay_report = engine.run(readiness, environment, feasibility)
    assert package.package_state == "PACKAGE_READY"
    assert package.advisory_only and package.authority_scope == "ADVISORY_EXECUTION_PACKAGE_ASSEMBLY_ONLY"
    assert report.validation_status == "PACKAGE_READY"
    assert replay == package and replay_report.duplicate and replay_report.snapshot_uuid == report.snapshot_uuid
    assert replay_report.report_uuid != report.report_uuid
    assert not any(hasattr(engine, name) for name in ("evaluate", "score", "trade", "execute", "order_send"))
    with pytest.raises(FrozenInstanceError):
        package.package_state = "REJECTED"


def test_incomplete_upstream_is_assembled_without_override(tmp_path):
    readiness, environment, feasibility, engine = setup_engine(tmp_path, with_evidence=False)
    package, _ = engine.run(readiness, environment, feasibility)
    assert package.package_state == "PACKAGE_INCOMPLETE"
    assert package.package_reason == "UPSTREAM_ARTIFACTS_INCOMPLETE"


def test_rejects_missing_or_wrong_upstream_artifacts(tmp_path):
    readiness, environment, feasibility, engine = setup_engine(tmp_path)
    with pytest.raises(ExecutionPackageError, match="INVALID_READINESS"):
        engine.run(None, environment, feasibility)
    with pytest.raises(ExecutionPackageError, match="INVALID_ENVIRONMENT"):
        engine.run(readiness, {}, feasibility)
    with pytest.raises(ExecutionPackageError, match="INVALID_FEASIBILITY"):
        engine.run(readiness, environment, object())
    other_readiness, _, _, _ = setup_engine(tmp_path / "other")
    with pytest.raises(ExecutionPackageError, match="BROKEN_PROVENANCE"):
        engine.run(other_readiness, environment, feasibility)


def test_broken_lineage_and_snapshot_mismatch_fail_closed(tmp_path):
    readiness, environment, feasibility, engine = setup_engine(tmp_path)
    with pytest.raises(ValueError, match="INVALID_EXECUTION_FEASIBILITY"):
        broken = replace(feasibility, execution_readiness_uuid="00000000-0000-5000-8000-000000000000")
        engine.run(readiness, environment, broken)
    snapshot = engine.feasibility_repository.latest_snapshot()
    path = engine.feasibility_repository.snapshot_root / f"{snapshot.snapshot_uuid}.json"
    data = json.loads(path.read_text())
    data["repository_digest"] = "0" * 64
    path.write_bytes(canonical_bytes(data))
    with pytest.raises(ExecutionPackageError, match="BROKEN_PROVENANCE"):
        engine.run(readiness, environment, feasibility)


def test_canonical_append_only_repository_and_collision_rejection(tmp_path):
    readiness, environment, feasibility, engine = setup_engine(tmp_path)
    package, report = engine.run(readiness, environment, feasibility)
    path = engine.repository.root / f"{package.execution_package_uuid}.json"
    original = path.read_bytes()
    assert original == canonical_bytes(package.to_dict())
    assert len(engine.repository.records()) == 1
    engine.run(readiness, environment, feasibility)
    assert path.read_bytes() == original and len(engine.repository.records()) == 1
    path.write_text("{}")
    with pytest.raises(ExecutionPackageError, match="REPOSITORY_MISMATCH"):
        engine.repository.records()
    assert report.repository_digest != package.repository_digest


def test_canonical_model_recomputes_and_rejects_tampered_package_uuid(tmp_path):
    readiness, environment, feasibility, engine = setup_engine(tmp_path)
    package, _ = engine.run(readiness, environment, feasibility)

    with pytest.raises(ValueError, match="INVALID_EXECUTION_PACKAGE"):
        replace(
            package,
            execution_package_uuid="00000000-0000-5000-8000-000000000000",
        )


def test_policy_engine_repository_and_replay_collisions_fail_closed(tmp_path):
    readiness, environment, feasibility, engine = setup_engine(tmp_path)
    package, _ = engine.run(readiness, environment, feasibility)
    incompatible = GovernedExecutionPackageAssemblyEngine(
        engine.readiness_repository, engine.environment_repository, engine.feasibility_repository,
        engine.repository, ExecutionPackagePolicy(package_engine_version="PR189.2.0"))
    with pytest.raises(ExecutionPackageError, match="ENGINE_VERSION_MISMATCH"):
        incompatible.run(readiness, environment, feasibility)
    path = engine.repository.root / f"{package.execution_package_uuid}.json"
    path.write_bytes(b"collision")
    with pytest.raises(ExecutionPackageError, match="REPOSITORY_MISMATCH"):
        engine.run(readiness, environment, feasibility)
