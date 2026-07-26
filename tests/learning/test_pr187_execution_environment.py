"""Comprehensive PR187 explicit environment-evidence tests."""

import json
from dataclasses import FrozenInstanceError, replace
from pathlib import Path
import sys
import pytest

sys.path.insert(0, str(Path(__file__).parents[2]))
sys.path.insert(1, str(Path(__file__).parent))
from learning.execution_environment import *
from learning.execution_environment.identity import (
    canonical_bytes,
    digest,
    execution_environment_uuid,
)
from learning.execution_environment.models import ExecutionEnvironmentSnapshot
from learning.execution_environment.policy import ENVIRONMENT_DIMENSIONS
from test_pr186_execution_readiness import setup_engine as setup_readiness_engine

GOOD = (0.99, 0.999, 0.9, 20.0, 100.0, 10.0, 0.9, 0.9, 2.0, 0.95)


def setup_engine(root, policy=None):
    recommendation_report, _, readiness_engine = setup_readiness_engine(root)
    report = readiness_engine.run(recommendation_report)
    evidence = ExecutionEnvironmentEvidenceRepository(
        root / "execution_environment_evidence"
    )
    engine = GovernedExecutionEnvironmentEngine(
        readiness_engine.repository,
        ExecutionEnvironmentRepository(root / "execution_environment"),
        policy,
        evidence,
    )
    return report, readiness_engine.repository, engine


def evidence_for(report, engine, values=GOOD, dimensions=ENVIRONMENT_DIMENSIONS):
    record = report.execution_readiness_records[0]
    snapshot = engine.readiness_repository.latest_snapshot()
    item = ExecutionEnvironmentEvidence.create(
        execution_readiness_uuid=record.execution_readiness_uuid,
        execution_readiness_digest=record.execution_readiness_digest,
        observations=tuple(zip(dimensions, values)),
        captured_at=record.created_at,
        readiness_snapshot_uuid=snapshot.snapshot_uuid,
        readiness_snapshot_digest=snapshot.snapshot_digest,
        readiness_repository_digest=snapshot.repository_digest,
        readiness_policy_uuid=snapshot.readiness_policy_uuid,
        readiness_policy_digest=snapshot.readiness_policy_digest,
        readiness_policy_version=snapshot.readiness_policy_version,
        readiness_engine_version=snapshot.readiness_engine_version,
        advisory_only=True,
    )
    engine.evidence_repository.save(item)
    return item


def test_missing_evidence_is_insufficient_and_only_readiness_inputs_allowed(tmp_path):
    report, repository, engine = setup_engine(tmp_path)
    for source in (
        report.execution_readiness_records[0],
        report,
        repository.latest_snapshot(),
    ):
        result = engine.run(source)
        record = result.execution_environment_records[0]
        assert (
            record.environment_state == "INSUFFICIENT_ENVIRONMENT_INFORMATION"
            and record.environment_quality == 0.0
        )
        assert all(v == "UNAVAILABLE" for _, v in record.environment_profile)
        assert (
            record.advisory_only
            and record.authority_scope == "ADVISORY_EXECUTION_ENVIRONMENT_ONLY"
        )
    for invalid in (None, {}, [], report.execution_readiness_records):
        with pytest.raises(
            ExecutionEnvironmentError, match="INVALID_EXECUTION_READINESS"
        ):
            engine.run(invalid)
    assert not any(
        hasattr(engine, n) for n in ("trade", "execute", "activate", "order_send")
    )


def test_explicit_complete_evidence_evaluates_each_dimension(tmp_path):
    report, _, engine = setup_engine(tmp_path)
    evidence_for(report, engine)
    record = engine.run(report).execution_environment_records[0]
    assert record.environment_state == "ENVIRONMENT_READY_FOR_FEASIBILITY"
    assert record.environment_quality == 1.0 and all(
        v == "AVAILABLE" for _, v in record.environment_profile
    )


def test_partial_evidence_and_mixed_profile_are_not_inferred(tmp_path):
    report, _, engine = setup_engine(tmp_path)
    values = list(GOOD)
    values[3:] = [99.0, 999.0, 99.0, 0.1, 0.1, 99.0, 0.1]
    evidence_for(report, engine, tuple(values))
    record = engine.run(report).execution_environment_records[0]
    assert record.environment_state == "INSUFFICIENT_ENVIRONMENT_INFORMATION"
    assert record.environment_quality == 0.3
    assert [v for _, v in record.environment_profile] == ["AVAILABLE"] * 3 + [
        "UNAVAILABLE"
    ] * 7


@pytest.mark.parametrize("index,bad", [(3, 51.0), (4, 251.0), (5, 31.0), (8, 6.0)])
def test_stale_spread_latency_and_slippage_apply_policy(tmp_path, index, bad):
    report, _, engine = setup_engine(tmp_path)
    values = list(GOOD)
    values[index] = bad
    evidence_for(report, engine, tuple(values))
    record = engine.run(report).execution_environment_records[0]
    assert (
        record.environment_profile[index][1] == "UNAVAILABLE"
        and record.environment_quality == 0.9
    )
    assert record.environment_state == "ENVIRONMENT_READY_FOR_FEASIBILITY"


def test_minimum_quality_is_applied(tmp_path):
    policy = ExecutionEnvironmentPolicy(minimum_quality=1.0)
    report, _, engine = setup_engine(tmp_path, policy)
    values = list(GOOD)
    values[3] = 51.0
    evidence_for(report, engine, tuple(values))
    assert (
        engine.run(report).execution_environment_records[0].environment_state
        == "INSUFFICIENT_ENVIRONMENT_INFORMATION"
    )


def test_evidence_rejects_nan_infinity_duplicates_unknown_and_reordering(tmp_path):
    report, _, engine = setup_engine(tmp_path)
    record = report.execution_readiness_records[0]
    snapshot = engine.readiness_repository.latest_snapshot()
    base = dict(
        execution_readiness_uuid=record.execution_readiness_uuid,
        execution_readiness_digest=record.execution_readiness_digest,
        captured_at=record.created_at,
        readiness_snapshot_uuid=snapshot.snapshot_uuid,
        readiness_snapshot_digest=snapshot.snapshot_digest,
        readiness_repository_digest=snapshot.repository_digest,
        readiness_policy_uuid=snapshot.readiness_policy_uuid,
        readiness_policy_digest=snapshot.readiness_policy_digest,
        readiness_policy_version=snapshot.readiness_policy_version,
        readiness_engine_version=snapshot.readiness_engine_version,
        advisory_only=True,
    )
    cases = [
        tuple(zip(ENVIRONMENT_DIMENSIONS[:3], GOOD[:3])),
        ((ENVIRONMENT_DIMENSIONS[0], float("nan")),),
        ((ENVIRONMENT_DIMENSIONS[0], float("inf")),),
        ((ENVIRONMENT_DIMENSIONS[0], 0.9), (ENVIRONMENT_DIMENSIONS[0], 0.8)),
        (("unknown", 0.9),),
        tuple(zip(reversed(ENVIRONMENT_DIMENSIONS), GOOD)),
    ]
    for observations in cases:
        with pytest.raises(ValueError, match="INVALID_EXECUTION_ENVIRONMENT_EVIDENCE"):
            ExecutionEnvironmentEvidence.create(observations=observations, **base)


def test_mixed_evidence_partition_fails_closed(tmp_path):
    report, _, engine = setup_engine(tmp_path)
    item = evidence_for(report, engine)
    path = engine.evidence_repository.root / f"{item.evidence_uuid}.json"
    data = item.identity_payload()
    data["readiness_policy_uuid"] = "00000000-0000-4000-8000-000000000000"
    replacement = ExecutionEnvironmentEvidence.create(**data)
    path.unlink()
    engine.evidence_repository.save(replacement)
    with pytest.raises(ExecutionEnvironmentError, match="POLICY_MISMATCH"):
        engine.run(report)


def test_evidence_snapshot_lineage_mismatch_fails_closed(tmp_path):
    report, _, engine = setup_engine(tmp_path)
    item = evidence_for(report, engine)
    path = engine.evidence_repository.root / f"{item.evidence_uuid}.json"
    values = item.identity_payload()
    values["readiness_snapshot_uuid"] = "00000000-0000-4000-8000-000000000000"
    replacement = ExecutionEnvironmentEvidence.create(**values)
    path.unlink()
    engine.evidence_repository.save(replacement)
    with pytest.raises(ExecutionEnvironmentError, match="SNAPSHOT_MISMATCH"):
        engine.run(report)


def test_multiple_evidence_artifacts_for_one_readiness_are_replay_collision(tmp_path):
    report, _, engine = setup_engine(tmp_path)
    evidence_for(report, engine)
    changed = list(GOOD)
    changed[3] = 21.0
    evidence_for(report, engine, tuple(changed))
    with pytest.raises(ExecutionEnvironmentError, match="REPLAY_COLLISION"):
        engine.run(report)


def test_snapshot_accepts_declared_nondefault_upstream_partition(tmp_path):
    report, _, engine = setup_engine(tmp_path)
    evidence_for(report, engine)
    engine.run(report)
    values = engine.repository.latest_snapshot().identity_payload()
    values.update(
        readiness_policy_uuid="00000000-0000-4000-8000-000000000000",
        readiness_policy_digest="a" * 64,
        readiness_policy_version="CUSTOM.7",
        readiness_engine_version="CUSTOM.9",
    )
    snapshot = ExecutionEnvironmentSnapshot.create(**values)
    assert snapshot.readiness_policy_version == "CUSTOM.7"


def test_replay_canonical_append_only_collision_and_snapshot_lineage(tmp_path):
    report, _, engine = setup_engine(tmp_path)
    evidence_for(report, engine)
    first = engine.run(report)
    record = first.execution_environment_records[0]
    path = engine.repository.root / f"{record.execution_environment_uuid}.json"
    paths = tuple(engine.repository.root.glob("*.json"))
    second = engine.run(report)
    assert (
        second.duplicate_count == 1
        and tuple(engine.repository.root.glob("*.json")) == paths
    )
    assert (
        execution_environment_uuid(record.identity_payload())
        == record.execution_environment_uuid
        and digest(record.digest_payload()) == record.execution_environment_digest
    )
    assert path.read_bytes() == canonical_bytes(record.to_dict())
    with pytest.raises(FrozenInstanceError):
        record.environment_state = "REJECTED"
    path.write_bytes(
        canonical_bytes({**record.to_dict(), "environment_reason": "tampered"})
    )
    with pytest.raises(ExecutionEnvironmentError):
        engine.repository.records()
    path.write_bytes(canonical_bytes(record.to_dict()))
    snapshot = engine.repository.latest_snapshot()
    sp = engine.repository.snapshot_root / f"{snapshot.snapshot_uuid}.json"
    sp.write_text("{}")
    with pytest.raises(
        ExecutionEnvironmentError,
        match="CORRUPT_EXECUTION_ENVIRONMENT_SNAPSHOT_REPOSITORY",
    ):
        engine.repository.latest_snapshot()


def test_policy_artifact_not_default_policy_controls_validation(tmp_path):
    policy = ExecutionEnvironmentPolicy(
        environment_policy_version="CUSTOM.PR187",
        environment_engine_version="CUSTOM.ENGINE",
        minimum_quality=0.7,
    )
    report, _, engine = setup_engine(tmp_path, policy)
    evidence_for(report, engine)
    record = engine.run(report).execution_environment_records[0]
    assert (
        record.environment_policy == policy.to_dict()
        and record.environment_policy_uuid == policy.environment_policy_uuid
    )
    with pytest.raises(ValueError, match="INVALID_EXECUTION_ENVIRONMENT_POLICY"):
        ExecutionEnvironmentPolicy(minimum_quality=float("nan"))
