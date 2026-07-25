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

@pytest.mark.parametrize(
    ("state", "expected"),
    [
        ("REJECTED", ("REJECTED", "REJECTED", "RECOMMENDATION_REJECTED")),
        ("INSUFFICIENT_RECOMMENDATION_EVIDENCE", ("INSUFFICIENT_EXECUTION_READINESS", "INSUFFICIENT_EXECUTION_READINESS", "RECOMMENDATION_EVIDENCE_INSUFFICIENT")),
        ("RECOMMENDATION_READY", ("EXECUTION_READY_FOR_ENVIRONMENT_CHECK", "READY_FOR_ENVIRONMENT_CHECK", "ADVISORY_PIPELINE_COMPLETE")),
        ("RECOMMENDATION_MANUAL_REVIEW", ("INSUFFICIENT_EXECUTION_READINESS", "INSUFFICIENT_EXECUTION_READINESS", "RECOMMENDATION_REQUIRES_MANUAL_REVIEW")),
        ("RECOMMENDATION_NOT_READY", ("INSUFFICIENT_EXECUTION_READINESS", "INSUFFICIENT_EXECUTION_READINESS", "RECOMMENDATION_NOT_READY")),
    ],
)
def test_every_recommendation_state_has_one_readiness_mapping(tmp_path, state, expected):
    from types import SimpleNamespace
    _, _, engine = setup_engine(tmp_path)
    assert engine._classify(SimpleNamespace(recommendation_state=state)) == expected


def test_nondefault_canonical_pr185_partition_is_accepted_and_preserved(tmp_path):
    from learning.decision_recommendation import (
        DecisionRecommendationPolicy,
        DecisionRecommendationRepository,
        GovernedDecisionRecommendationEngine,
    )
    intelligence_report, intelligence_repository, _ = setup_recommendation_engine(tmp_path)
    upstream_policy = DecisionRecommendationPolicy(
        ready_quality_threshold=0.80,
        manual_review_quality_threshold=0.60,
    )
    upstream = GovernedDecisionRecommendationEngine(
        intelligence_repository,
        DecisionRecommendationRepository(tmp_path / "alternate_recommendations"),
        upstream_policy,
    )
    report = upstream.run(intelligence_report)
    engine = GovernedExecutionReadinessEngine(
        upstream.repository,
        ExecutionReadinessRepository(tmp_path / "readiness"),
    )
    for source in (report, upstream.repository.latest_snapshot()):
        result = engine.run(source)
        snapshot = engine.repository.latest_snapshot()
        assert snapshot.recommendation_policy_uuid == upstream_policy.recommendation_policy_uuid
        assert snapshot.recommendation_policy_digest == upstream_policy.recommendation_policy_digest
        assert snapshot.recommendation_policy_version == upstream_policy.recommendation_policy_version
        assert snapshot.recommendation_engine_version == upstream_policy.recommendation_engine_version
        assert result.execution_readiness_records


@pytest.mark.parametrize(
    "field,value,error",
    [
        ("readiness_policy_uuid", "00000000-0000-4000-8000-000000000000", "INVALID_EXECUTION_READINESS"),
        ("readiness_policy_digest", "0" * 64, "INVALID_EXECUTION_READINESS"),
        ("readiness_policy_version", "PR186-EXECUTION_READINESS-POLICY.2.0", "INVALID_EXECUTION_READINESS"),
        ("readiness_engine_version", "PR186.2.0", "INVALID_EXECUTION_READINESS"),
        ("recommendation_state", "UNKNOWN", "INVALID_EXECUTION_READINESS"),
        ("readiness_state", "REJECTED", "INVALID_EXECUTION_READINESS"),
        ("readiness_classification", "REJECTED", "INVALID_EXECUTION_READINESS"),
        ("readiness_reason", "RECOMMENDATION_REJECTED", "INVALID_EXECUTION_READINESS"),
        ("advisory_only", False, "INVALID_EXECUTION_READINESS"),
        ("authority_scope", "EXECUTION", "INVALID_EXECUTION_READINESS"),
    ],
)
def test_record_rejects_invalid_governance_fields(tmp_path, field, value, error):
    from learning.execution_readiness.models import ExecutionReadiness
    report, _, engine = setup_engine(tmp_path)
    values = engine.run(report).execution_readiness_records[0].identity_payload()
    values[field] = value
    with pytest.raises(ValueError, match=error):
        ExecutionReadiness.create(**values)


def test_record_report_and_snapshot_identity_recomputation(tmp_path):
    from learning.execution_readiness.identity import report_uuid, snapshot_uuid
    report, _, engine = setup_engine(tmp_path)
    result = engine.run(report)
    snapshot = engine.repository.latest_snapshot()
    record = result.execution_readiness_records[0]
    assert execution_readiness_uuid(record.identity_payload()) == record.execution_readiness_uuid
    assert digest(record.digest_payload()) == record.execution_readiness_digest
    assert report_uuid(result.identity_payload()) == result.report_uuid
    assert digest(result.digest_payload()) == result.report_digest
    assert snapshot_uuid(snapshot.identity_payload()) == snapshot.snapshot_uuid
    assert digest(snapshot.identity_payload()) == snapshot.snapshot_digest


@pytest.mark.parametrize(
    "field,value",
    [
        ("processed_count", 2), ("ready_count", 0), ("insufficient_count", 1),
        ("rejected_count", 1), ("duplicate_count", -1), ("duplicate_count", 2),
        ("repository_digest", "0" * 64),
        ("snapshot_uuid", "00000000-0000-4000-8000-000000000000"),
        ("snapshot_digest", "0" * 64),
    ],
)
def test_report_rejects_counter_and_binding_tampering(tmp_path, field, value):
    from learning.execution_readiness.models import ExecutionReadinessReport
    report, _, engine = setup_engine(tmp_path)
    result = engine.run(report)
    values = result.to_dict()
    values[field] = value
    with pytest.raises(ValueError, match="INVALID_EXECUTION_READINESS_REPORT"):
        ExecutionReadinessReport(**values)


def test_report_rejects_duplicate_record_uuids(tmp_path):
    from learning.execution_readiness.models import ExecutionReadinessReport
    report, _, engine = setup_engine(tmp_path)
    result = engine.run(report)
    values = result.identity_payload()
    values.update(execution_readiness_records=(result.execution_readiness_records[0],) * 2, processed_count=2, ready_count=2)
    with pytest.raises(ValueError, match="INVALID_EXECUTION_READINESS_REPORT"):
        ExecutionReadinessReport.create(**values)

@pytest.mark.parametrize(
    "field,value",
    [
        ("readiness_policy_uuid", "00000000-0000-4000-8000-000000000000"),
        ("readiness_policy_digest", "0" * 64),
        ("readiness_policy_version", "PR186-EXECUTION_READINESS-POLICY.2.0"),
        ("readiness_engine_version", "PR186.2.0"),
        ("recommendation_policy_uuid", "bad"),
        ("recommendation_policy_digest", "bad"),
        ("recommendation_policy_version", "PR185-RECOMMENDATION-POLICY.2.0"),
        ("recommendation_engine_version", "PR185.2.0"),
        ("record_count", 2),
        ("previous_snapshot_uuid", "bad"),
        ("previous_snapshot_digest", "0" * 64),
        ("advisory_only", False),
        ("authority_scope", "EXECUTION"),
    ],
)
def test_snapshot_rejects_invalid_partitions_counts_chain_and_authority(tmp_path, field, value):
    from learning.execution_readiness.models import ExecutionReadinessSnapshot
    report, _, engine = setup_engine(tmp_path)
    engine.run(report)
    values = engine.repository.latest_snapshot().identity_payload()
    values[field] = value
    with pytest.raises(ValueError, match="INVALID_EXECUTION_READINESS_SNAPSHOT"):
        ExecutionReadinessSnapshot.create(**values)


def test_snapshot_rejects_unsorted_and_duplicate_identities(tmp_path):
    from learning.execution_readiness.models import ExecutionReadinessSnapshot
    report, _, engine = setup_engine(tmp_path)
    engine.run(report)
    values = engine.repository.latest_snapshot().identity_payload()
    original = values["readiness_identities"][0]
    second = ("00000000-0000-4000-8000-000000000000", "0" * 64)
    for identities in ((original, original), (original, second)):
        changed = {**values, "readiness_identities": identities, "record_count": 2}
        with pytest.raises(ValueError, match="INVALID_EXECUTION_READINESS_SNAPSHOT"):
            ExecutionReadinessSnapshot.create(**changed)


@pytest.mark.parametrize("kind", ["record", "snapshot"])
def test_repository_rejects_malformed_noncanonical_invalid_and_mismatched_files(tmp_path, kind):
    report, _, engine = setup_engine(tmp_path)
    result = engine.run(report)
    record = result.execution_readiness_records[0]
    snapshot = engine.repository.latest_snapshot()
    root, item, label, identity = (
        (engine.repository.root, record, "EXECUTION_READINESS", record.execution_readiness_uuid)
        if kind == "record" else
        (engine.repository.snapshot_root, snapshot, "EXECUTION_READINESS_SNAPSHOT", snapshot.snapshot_uuid)
    )
    path = root / f"{identity}.json"
    path.write_text("{")
    loader = engine.repository.records if kind == "record" else engine.repository.snapshots
    with pytest.raises(ExecutionReadinessError, match=f"CORRUPT_{label}_REPOSITORY"):
        loader()
    path.write_text(json.dumps(item.to_dict(), indent=2))
    with pytest.raises(ExecutionReadinessError, match=f"NONCANONICAL_{label}_JSON"):
        loader()
    path.write_bytes(canonical_bytes(item.to_dict()))
    invalid = root / "not-a-uuid.json"
    invalid.write_text("{}")
    with pytest.raises(ExecutionReadinessError, match=f"INVALID_{label}_FILENAME"):
        loader()
    invalid.unlink()
    mismatch = root / "00000000-0000-4000-8000-000000000000.json"
    mismatch.write_bytes(canonical_bytes(item.to_dict()))
    with pytest.raises(ExecutionReadinessError, match=f"{label}_FILENAME_IDENTITY_MISMATCH"):
        loader()

@pytest.mark.parametrize(
    "field,value,error",
    [
        ("recommendation_policy_uuid", "00000000-0000-4000-8000-000000000000", "POLICY_MISMATCH"),
        ("recommendation_policy_digest", "0" * 64, "POLICY_MISMATCH"),
        ("recommendation_policy_version", "PR185-RECOMMENDATION-POLICY.0.9", "POLICY_MISMATCH"),
        ("recommendation_engine_version", "PR185.0.9", "ENGINE_VERSION_MISMATCH"),
    ],
)
def test_mixed_upstream_record_and_snapshot_partitions_fail_closed(tmp_path, field, value, error):
    from types import SimpleNamespace
    report, repository, engine = setup_engine(tmp_path)
    record = report.recommendations[0]
    snapshot = repository.latest_snapshot()
    fields = {
        "recommendation_policy_uuid": record.recommendation_policy_uuid,
        "recommendation_policy_digest": record.recommendation_policy_digest,
        "recommendation_policy_version": record.recommendation_policy_version,
        "recommendation_engine_version": record.recommendation_engine_version,
    }
    fields[field] = value
    with pytest.raises(ExecutionReadinessError, match=error):
        engine._verify_partition((SimpleNamespace(**fields),), snapshot)


def test_source_record_uuid_digest_membership_and_exact_type_fail_closed(tmp_path):
    from learning.decision_recommendation import DecisionRecommendation
    report, _, engine = setup_engine(tmp_path)
    original = report.recommendations[0]

    class RecommendationSubclass(DecisionRecommendation):
        pass

    with pytest.raises(ExecutionReadinessError, match="INVALID_RECOMMENDATION"):
        engine.run(RecommendationSubclass(**original.to_dict()))
    for field, value in (
        ("recommendation_uuid", "00000000-0000-4000-8000-000000000000"),
        ("recommendation_digest", "0" * 64),
    ):
        changed = DecisionRecommendation.__new__(DecisionRecommendation)
        for name, current in original.__dict__.items():
            object.__setattr__(changed, name, value if name == field else current)
        with pytest.raises(ExecutionReadinessError, match="BROKEN_PROVENANCE"):
            engine.run(changed)


def test_report_identity_and_snapshot_bindings_fail_closed(tmp_path):
    from learning.decision_recommendation import DecisionRecommendationReport
    report, _, engine = setup_engine(tmp_path)
    cases = (
        ("report_uuid", "00000000-0000-4000-8000-000000000000", "BROKEN_PROVENANCE"),
        ("report_digest", "0" * 64, "BROKEN_PROVENANCE"),
        ("repository_digest", "0" * 64, "REPOSITORY_MISMATCH"),
        ("snapshot_uuid", "00000000-0000-4000-8000-000000000000", "SNAPSHOT_MISMATCH"),
        ("snapshot_digest", "0" * 64, "SNAPSHOT_MISMATCH"),
    )
    for field, value, error in cases:
        changed = DecisionRecommendationReport.__new__(DecisionRecommendationReport)
        for name, current in report.__dict__.items():
            object.__setattr__(changed, name, value if name == field else current)
        with pytest.raises(ExecutionReadinessError, match=error):
            engine.run(changed)


def test_record_absent_from_repository_or_snapshot_fails_closed(tmp_path):
    report, repository, engine = setup_engine(tmp_path)
    record = report.recommendations[0]
    path = repository.root / f"{record.recommendation_uuid}.json"
    path.unlink()
    with pytest.raises(ExecutionReadinessError, match="BROKEN_PROVENANCE"):
        engine.run(record)


def test_authority_boundary_has_no_runtime_or_execution_surface(tmp_path):
    _, _, engine = setup_engine(tmp_path)
    forbidden = (
        "buy", "sell", "approve_trade", "publish_decision", "write_decision_json",
        "activate_runtime", "measure_spread", "measure_latency", "measure_slippage",
        "broker", "mt5", "order_send", "modify_order", "modify_position", "manage_exit",
    )
    assert not any(hasattr(engine, name) for name in forbidden)


def test_empty_recommendation_report_and_snapshot_fail_closed(tmp_path):
    from learning.decision_recommendation import (
        DecisionRecommendationReport,
        DecisionRecommendationRepository,
        DecisionRecommendationSnapshot,
    )
    from learning.decision_recommendation.identity import digest as recommendation_digest
    _, populated, _ = setup_engine(tmp_path)
    template = populated.latest_snapshot()
    empty_repository = DecisionRecommendationRepository(tmp_path / "empty_recommendations")
    values = template.identity_payload()
    values.update(
        recommendation_identities=(), record_count=0,
        repository_digest=recommendation_digest([]),
        previous_snapshot_uuid=None, previous_snapshot_digest=None,
    )
    empty_snapshot = DecisionRecommendationSnapshot.create(**values)
    empty_repository.save_snapshot(empty_snapshot)
    engine = GovernedExecutionReadinessEngine(
        empty_repository,
        ExecutionReadinessRepository(tmp_path / "empty_readiness"),
    )
    with pytest.raises(ExecutionReadinessError, match="INVALID_RECOMMENDATION"):
        engine.run(empty_snapshot)
    empty_report = DecisionRecommendationReport.create(
        recommendations=(), processed_count=0, ready_count=0,
        insufficient_count=0, rejected_count=0, duplicate_count=0,
        repository_digest=empty_snapshot.repository_digest,
        snapshot_uuid=empty_snapshot.snapshot_uuid,
        snapshot_digest=empty_snapshot.snapshot_digest,
        generated_at=empty_snapshot.generated_at, advisory_only=True,
    )
    with pytest.raises(ExecutionReadinessError, match="INVALID_RECOMMENDATION"):
        engine.run(empty_report)


def _snapshot_variant(template, **changes):
    from learning.execution_readiness.models import ExecutionReadinessSnapshot
    values = template.identity_payload()
    values.update(changes)
    return ExecutionReadinessSnapshot.create(**values)


def test_repository_rejects_multiple_snapshot_heads_and_orphans(tmp_path):
    report, _, engine = setup_engine(tmp_path)
    result = engine.run(report)
    head = engine.repository.latest_snapshot()
    repo = ExecutionReadinessRepository(tmp_path / "chain")
    repo.save(result.execution_readiness_records[0])
    repo.save_snapshot(head)
    second_root = _snapshot_variant(head, generated_at="2026-07-25T00:00:01Z")
    repo.save_snapshot(second_root)
    with pytest.raises(ExecutionReadinessError, match="SNAPSHOT_MISMATCH"):
        repo.latest_snapshot()

    orphan_repo = ExecutionReadinessRepository(tmp_path / "orphan")
    orphan = _snapshot_variant(
        head,
        previous_snapshot_uuid="00000000-0000-4000-8000-000000000000",
        previous_snapshot_digest="0" * 64,
    )
    orphan_repo.save_snapshot(orphan)
    with pytest.raises(ExecutionReadinessError, match="SNAPSHOT_MISMATCH"):
        orphan_repo.latest_snapshot()


def test_repository_rejects_broken_previous_digest_and_mixed_partition(tmp_path):
    report, _, engine = setup_engine(tmp_path)
    engine.run(report)
    head = engine.repository.latest_snapshot()
    for name, changes, error in (
        ("digest", {"previous_snapshot_uuid": head.snapshot_uuid, "previous_snapshot_digest": "0" * 64}, "SNAPSHOT_MISMATCH"),
        ("partition", {"previous_snapshot_uuid": head.snapshot_uuid, "previous_snapshot_digest": head.snapshot_digest, "recommendation_policy_uuid": "00000000-0000-4000-8000-000000000000"}, "POLICY_MISMATCH"),
    ):
        repo = ExecutionReadinessRepository(tmp_path / name)
        repo.save_snapshot(head)
        repo.save_snapshot(_snapshot_variant(head, **changes))
        with pytest.raises(ExecutionReadinessError, match=error):
            repo.latest_snapshot()


def test_repository_rejects_head_identity_and_digest_mismatch(tmp_path):
    report, _, engine = setup_engine(tmp_path)
    result = engine.run(report)
    head = engine.repository.latest_snapshot()
    for name, changes, error in (
        ("identities", {"readiness_identities": (), "record_count": 0, "repository_digest": digest([])}, "SNAPSHOT_MISMATCH"),
        ("repository", {"repository_digest": "0" * 64}, "REPOSITORY_MISMATCH"),
    ):
        repo = ExecutionReadinessRepository(tmp_path / name)
        repo.save(result.execution_readiness_records[0])
        repo.save_snapshot(_snapshot_variant(head, **changes))
        with pytest.raises(ExecutionReadinessError, match=error):
            repo.latest_snapshot()


def test_repository_rejects_snapshot_cycle(tmp_path, monkeypatch):
    report, _, engine = setup_engine(tmp_path)
    engine.run(report)
    first = engine.repository.latest_snapshot()
    second = _snapshot_variant(
        first,
        previous_snapshot_uuid=first.snapshot_uuid,
        previous_snapshot_digest=first.snapshot_digest,
    )
    object.__setattr__(first, "previous_snapshot_uuid", second.snapshot_uuid)
    object.__setattr__(first, "previous_snapshot_digest", second.snapshot_digest)
    monkeypatch.setattr(engine.repository, "snapshots", lambda: (first, second))
    with pytest.raises(ExecutionReadinessError, match="SNAPSHOT_MISMATCH"):
        engine.repository.latest_snapshot()
