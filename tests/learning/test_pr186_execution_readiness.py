"""PR186 governed advisory execution-readiness tests."""

import json
from dataclasses import FrozenInstanceError
from pathlib import Path
import sys

import pytest

sys.path.insert(0, str(Path(__file__).parents[2]))
sys.path.insert(1, str(Path(__file__).parent))
from learning.execution_readiness import (
    ExecutionReadinessError,
    ExecutionReadinessPolicy,
    ExecutionReadinessRepository,
    GovernedExecutionReadinessEngine,
)
from learning.execution_readiness.identity import canonical_bytes, digest, execution_readiness_uuid
from test_pr185_decision_recommendation import setup_engine as setup_recommendation_engine


def setup_engine(root):
    intelligence_report, _, recommendation_engine = setup_recommendation_engine(root)
    recommendation_report = recommendation_engine.run(intelligence_report)
    engine = GovernedExecutionReadinessEngine(
        recommendation_engine.repository,
        ExecutionReadinessRepository(root / "execution_readiness"),
    )
    return recommendation_report, recommendation_engine.repository, engine


def test_record_report_and_snapshot_inputs_are_advisory_only(tmp_path):
    report, repository, engine = setup_engine(tmp_path)
    for source in (report.recommendations[0], report, repository.latest_snapshot()):
        result = engine.run(source)
        record = result.execution_readiness_records[0]
        assert record.readiness_state == "EXECUTION_READY_FOR_ENVIRONMENT_CHECK"
        assert record.advisory_only is result.advisory_only is True
        assert record.authority_scope == "ADVISORY_EXECUTION_READINESS_ONLY"
    for invalid in (None, {}, [], report.recommendations):
        with pytest.raises(ExecutionReadinessError, match="INVALID_RECOMMENDATION"):
            engine.run(invalid)
    assert not any(hasattr(engine, name) for name in ("trade", "execute", "activate", "publish_decision", "order_send"))


def test_replay_uuid_canonical_storage_and_duplicates(tmp_path):
    report, _, engine = setup_engine(tmp_path)
    first = engine.run(report)
    record = first.execution_readiness_records[0]
    path = engine.repository.root / f"{record.execution_readiness_uuid}.json"
    paths = tuple(engine.repository.root.glob("*.json"))
    second = engine.run(report)
    assert second.duplicate_count == 1
    assert second.execution_readiness_records == first.execution_readiness_records
    assert tuple(engine.repository.root.glob("*.json")) == paths
    assert execution_readiness_uuid(record.identity_payload()) == record.execution_readiness_uuid
    assert digest(record.digest_payload()) == record.execution_readiness_digest
    assert path.read_bytes() == canonical_bytes(record.to_dict())
    with pytest.raises(FrozenInstanceError):
        record.readiness_state = "REJECTED"


def test_broken_provenance_snapshot_repository_and_policy_fail_closed(tmp_path):
    report, source_repository, engine = setup_engine(tmp_path)
    source = report.recommendations[0]
    object.__setattr__(source, "recommendation_digest", "0" * 64)
    with pytest.raises(ExecutionReadinessError, match="BROKEN_PROVENANCE"):
        engine.run(source)
    object.__setattr__(source, "recommendation_digest", source_repository.records()[0].recommendation_digest)
    bad_report = report.identity_payload()
    bad_report["recommendations"] = report.recommendations
    bad_report["repository_digest"] = "0" * 64
    from learning.decision_recommendation import DecisionRecommendationReport
    # Recomputed identity makes this a structurally valid report with the wrong repository binding.
    mismatched = DecisionRecommendationReport.create(**bad_report)
    with pytest.raises(ExecutionReadinessError, match="REPOSITORY_MISMATCH"):
        engine.run(mismatched)
    with pytest.raises(ValueError, match="INVALID_EXECUTION_READINESS_POLICY"):
        ExecutionReadinessPolicy(readiness_engine_version="PR999")


def test_repository_tampering_snapshot_chain_and_collision_fail_closed(tmp_path):
    report, _, engine = setup_engine(tmp_path)
    result = engine.run(report)
    record = result.execution_readiness_records[0]
    path = engine.repository.root / f"{record.execution_readiness_uuid}.json"
    path.write_text(json.dumps(record.to_dict(), indent=2))
    with pytest.raises(ExecutionReadinessError, match="NONCANONICAL_EXECUTION_READINESS_JSON"):
        engine.repository.records()
    path.write_bytes(canonical_bytes(record.to_dict()))
    snapshot = engine.repository.latest_snapshot()
    snapshot_path = engine.repository.snapshot_root / f"{snapshot.snapshot_uuid}.json"
    snapshot_path.write_text("{}")
    with pytest.raises(ExecutionReadinessError, match="CORRUPT_EXECUTION_READINESS_SNAPSHOT_REPOSITORY"):
        engine.repository.latest_snapshot()
    collision = {**record.to_dict(), "readiness_reason": "tampered"}
    path.write_bytes(canonical_bytes(collision))
    with pytest.raises(ExecutionReadinessError):
        engine.repository.records()
