"""PR187 governed advisory execution-environment tests."""

import json
from dataclasses import FrozenInstanceError
from pathlib import Path
import sys
import pytest

sys.path.insert(0, str(Path(__file__).parents[2]))
sys.path.insert(1, str(Path(__file__).parent))
from learning.execution_environment import (
    ExecutionEnvironmentError, ExecutionEnvironmentPolicy,
    ExecutionEnvironmentRepository, GovernedExecutionEnvironmentEngine,
)
from learning.execution_environment.identity import canonical_bytes, digest, execution_environment_uuid
from test_pr186_execution_readiness import setup_engine as setup_readiness_engine


def setup_engine(root):
    recommendation_report, _, readiness_engine = setup_readiness_engine(root)
    readiness_report = readiness_engine.run(recommendation_report)
    engine = GovernedExecutionEnvironmentEngine(
        readiness_engine.repository,
        ExecutionEnvironmentRepository(root / "execution_environment"),
    )
    return readiness_report, readiness_engine.repository, engine


def test_only_readiness_artifacts_are_accepted_and_output_is_advisory(tmp_path):
    report, repository, engine = setup_engine(tmp_path)
    for source in (report.execution_readiness_records[0], report, repository.latest_snapshot()):
        result = engine.run(source)
        record = result.execution_environment_records[0]
        assert record.environment_state == "ENVIRONMENT_READY_FOR_FEASIBILITY"
        assert record.environment_quality == 1.0
        assert len(record.environment_profile) == 10
        assert record.advisory_only is result.advisory_only is True
        assert record.authority_scope == "ADVISORY_EXECUTION_ENVIRONMENT_ONLY"
    for invalid in (None, {}, [], report.execution_readiness_records):
        with pytest.raises(ExecutionEnvironmentError, match="INVALID_EXECUTION_READINESS"):
            engine.run(invalid)
    assert not any(hasattr(engine, name) for name in ("trade", "execute", "activate", "order_send"))


def test_replay_deterministic_uuid_canonical_append_only_and_duplicates(tmp_path):
    report, _, engine = setup_engine(tmp_path)
    first = engine.run(report)
    record = first.execution_environment_records[0]
    path = engine.repository.root / f"{record.execution_environment_uuid}.json"
    paths = tuple(engine.repository.root.glob("*.json"))
    second = engine.run(report)
    assert second.duplicate_count == 1
    assert second.execution_environment_records == first.execution_environment_records
    assert tuple(engine.repository.root.glob("*.json")) == paths
    assert execution_environment_uuid(record.identity_payload()) == record.execution_environment_uuid
    assert digest(record.digest_payload()) == record.execution_environment_digest
    assert path.read_bytes() == canonical_bytes(record.to_dict())
    with pytest.raises(FrozenInstanceError):
        record.environment_state = "REJECTED"


def test_broken_provenance_snapshot_repository_and_policy_fail_closed(tmp_path):
    report, source_repository, engine = setup_engine(tmp_path)
    source = report.execution_readiness_records[0]
    original = source.execution_readiness_digest
    object.__setattr__(source, "execution_readiness_digest", "0" * 64)
    with pytest.raises(ExecutionEnvironmentError, match="BROKEN_PROVENANCE"):
        engine.run(source)
    object.__setattr__(source, "execution_readiness_digest", original)
    values = report.identity_payload()
    values["execution_readiness_records"] = report.execution_readiness_records
    values["repository_digest"] = "0" * 64
    from learning.execution_readiness import ExecutionReadinessReport
    mismatched = ExecutionReadinessReport.create(**values)
    with pytest.raises(ExecutionEnvironmentError, match="REPOSITORY_MISMATCH"):
        engine.run(mismatched)
    with pytest.raises(ValueError, match="INVALID_EXECUTION_ENVIRONMENT_POLICY"):
        ExecutionEnvironmentPolicy(environment_engine_version="PR999")


def test_snapshot_mismatch_repository_tampering_and_collision(tmp_path):
    report, _, engine = setup_engine(tmp_path)
    result = engine.run(report)
    record = result.execution_environment_records[0]
    path = engine.repository.root / f"{record.execution_environment_uuid}.json"
    path.write_text(json.dumps(record.to_dict(), indent=2))
    with pytest.raises(ExecutionEnvironmentError, match="NONCANONICAL_EXECUTION_ENVIRONMENT_JSON"):
        engine.repository.records()
    path.write_bytes(canonical_bytes(record.to_dict()))
    snapshot = engine.readiness_repository.latest_snapshot()
    object.__setattr__(snapshot, "repository_digest", "0" * 64)
    with pytest.raises(ExecutionEnvironmentError, match="SNAPSHOT_MISMATCH"):
        engine.run(snapshot)
    collision = {**record.to_dict(), "environment_reason": "tampered"}
    path.write_bytes(canonical_bytes(collision))
    with pytest.raises(ExecutionEnvironmentError):
        engine.repository.records()


def test_environment_replay_report_and_snapshot_identities(tmp_path):
    from learning.execution_environment.identity import report_uuid, snapshot_uuid
    report, _, engine = setup_engine(tmp_path)
    result = engine.run(report)
    snapshot = engine.repository.latest_snapshot()
    assert report_uuid(result.identity_payload()) == result.report_uuid
    assert digest(result.digest_payload()) == result.report_digest
    assert snapshot_uuid(snapshot.identity_payload()) == snapshot.snapshot_uuid
    assert digest(snapshot.identity_payload()) == snapshot.snapshot_digest
