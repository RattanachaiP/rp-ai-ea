"""PR188 governed advisory execution feasibility tests."""

from dataclasses import FrozenInstanceError
from pathlib import Path
import json
import sys
import pytest

sys.path.insert(0, str(Path(__file__).parents[2]))
sys.path.insert(1, str(Path(__file__).parent))

from learning.execution_feasibility import *
from learning.execution_feasibility.identity import canonical_bytes
from learning.execution_environment import ExecutionEnvironmentRepository, GovernedExecutionEnvironmentEngine
from test_pr187_execution_environment import setup_engine as setup_environment_engine, evidence_for


def setup_engine(root, with_evidence=True):
    readiness_report, _, environment_engine = setup_environment_engine(root)
    if with_evidence:
        evidence_for(readiness_report, environment_engine)
    environment_report = environment_engine.run(readiness_report)
    readiness = readiness_report.execution_readiness_records[0]
    environment = environment_report.execution_environment_records[0]
    engine = GovernedExecutionFeasibilityEngine(
        environment_engine.readiness_repository,
        environment_engine.repository,
        ExecutionFeasibilityRepository(root / "execution_feasibility"),
    )
    return readiness, environment, engine


def test_feasible_is_advisory_only_and_replay_is_deterministic(tmp_path):
    readiness, environment, engine = setup_engine(tmp_path)
    first = engine.run(readiness, environment)
    second = engine.run(readiness, environment)
    record = first.execution_feasibility_records[0]
    assert record.feasibility_state == "EXECUTION_FEASIBLE"
    assert record.advisory_only and record.authority_scope == "ADVISORY_EXECUTION_FEASIBILITY_ONLY"
    assert all(value == "SATISFIED" for _, value in record.feasibility_dimensions)
    assert second.execution_feasibility_records == first.execution_feasibility_records
    assert second.duplicate_count == 1 and second.snapshot_uuid == first.snapshot_uuid
    assert not any(hasattr(engine, name) for name in ("trade", "execute", "activate", "order_send"))


def test_insufficient_environment_remains_insufficient(tmp_path):
    readiness, environment, engine = setup_engine(tmp_path, with_evidence=False)
    report = engine.run(readiness, environment)
    assert report.execution_feasibility_records[0].feasibility_state == "INSUFFICIENT_EXECUTION_FEASIBILITY"


def test_only_exact_records_are_accepted(tmp_path):
    readiness, environment, engine = setup_engine(tmp_path)
    with pytest.raises(ExecutionFeasibilityError, match="INVALID_READINESS"):
        engine.run({}, environment)
    with pytest.raises(ExecutionFeasibilityError, match="INVALID_ENVIRONMENT"):
        engine.run(readiness, {})


def test_cross_stage_lineage_and_provenance_fail_closed(tmp_path):
    readiness, environment, engine = setup_engine(tmp_path / "one")
    other_readiness, _, _ = setup_engine(tmp_path / "two")
    with pytest.raises(ExecutionFeasibilityError, match="BROKEN_PROVENANCE"):
        engine.run(other_readiness, environment)
    broken = engine.environment_repository.root / f"{environment.execution_environment_uuid}.json"
    data = json.loads(broken.read_text())
    data["environment_reason"] = "tampered"
    broken.write_text(json.dumps(data))
    with pytest.raises(ExecutionFeasibilityError, match="BROKEN_PROVENANCE"):
        engine.run(readiness, environment)


def test_append_only_canonical_storage_and_immutability(tmp_path):
    readiness, environment, engine = setup_engine(tmp_path)
    report = engine.run(readiness, environment)
    record = report.execution_feasibility_records[0]
    path = engine.repository.root / f"{record.execution_feasibility_uuid}.json"
    assert path.read_bytes() == canonical_bytes(record.to_dict())
    with pytest.raises(FrozenInstanceError):
        record.feasibility_state = "REJECTED"
    path.write_text("{}")
    with pytest.raises(ExecutionFeasibilityError, match="CORRUPT_EXECUTION_FEASIBILITY_REPOSITORY"):
        engine.repository.records()


def test_repository_and_snapshot_mismatch_fail_closed(tmp_path):
    readiness, environment, engine = setup_engine(tmp_path)
    engine.run(readiness, environment)
    snapshot = engine.repository.latest_snapshot()
    path = engine.repository.snapshot_root / f"{snapshot.snapshot_uuid}.json"
    data = json.loads(path.read_text())
    data["repository_digest"] = "0" * 64
    path.write_bytes(canonical_bytes(data))
    with pytest.raises(ExecutionFeasibilityError, match="CORRUPT_EXECUTION_FEASIBILITY_SNAPSHOT_REPOSITORY"):
        engine.run(readiness, environment)
