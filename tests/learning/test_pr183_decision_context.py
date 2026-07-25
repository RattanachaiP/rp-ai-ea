"""PR183 advisory Decision Context boundary and persistence tests."""
import json
from pathlib import Path
import sys

import pytest

sys.path.insert(0, str(Path(__file__).parents[2]))
sys.path.insert(1, str(Path(__file__).parent))

from learning.decision_context import (DecisionContextError,
    DecisionContextPolicy, DecisionContextRepository, GovernedDecisionContextEngine)
from learning.decision_context.identity import canonical_bytes
from learning.runtime_confidence import RuntimeConfidenceRepository
from test_pr182_runtime_confidence import governed_artifacts


def setup_engine(root):
    eligibility_report, _, evaluator = governed_artifacts(root)
    confidence_report = evaluator.evaluate_confidence(eligibility_report)
    confidence_repository = evaluator.repository
    engine = GovernedDecisionContextEngine(confidence_repository,
        DecisionContextRepository(root / "decision_context"))
    return confidence_report, confidence_repository, engine


def test_accepts_only_three_exact_confidence_artifacts_and_is_advisory(tmp_path):
    report, repository, engine = setup_engine(tmp_path)
    for source in (report.confidence_records[0], report, repository.latest_snapshot()):
        output = engine.construct_context(source)
        assert output.advisory_only is True
        assert output.decision_contexts[0].authority_scope == "ADVISORY_DECISION_CONTEXT_ONLY"
    for invalid in (None, {}, [], report.confidence_records):
        with pytest.raises(DecisionContextError, match="INVALID_CONFIDENCE"):
            engine.construct_context(invalid)
    assert not any(hasattr(engine, name) for name in ("trade", "activate", "publish_decision", "execute"))


def test_replay_duplicate_determinism_canonical_json_and_append_only(tmp_path):
    report, _, engine = setup_engine(tmp_path)
    first = engine.construct_context(report)
    before = tuple(engine.repository.root.glob("*.json"))
    second = engine.construct_context(report)
    assert second.duplicate_count == 1
    assert first.decision_contexts == second.decision_contexts
    assert tuple(engine.repository.root.glob("*.json")) == before
    context = first.decision_contexts[0]
    path = engine.repository.root / f"{context.context_uuid}.json"
    assert path.read_bytes() == canonical_bytes(context.to_dict())
    assert json.loads(path.read_text())["context_state"] == "CONTEXT_PREPARED"


def test_broken_provenance_snapshot_and_repository_mismatches_fail_closed(tmp_path):
    report, repository, engine = setup_engine(tmp_path)
    bad_record = report.confidence_records[0]
    object.__setattr__(bad_record, "confidence_digest", "0" * 64)
    with pytest.raises(DecisionContextError, match="BROKEN_PROVENANCE"):
        engine.construct_context(bad_record)
    bad_snapshot = repository.latest_snapshot()
    object.__setattr__(bad_snapshot, "snapshot_digest", "0" * 64)
    with pytest.raises(DecisionContextError, match="SNAPSHOT_MISMATCH"):
        engine.construct_context(bad_snapshot)
    object.__setattr__(bad_snapshot, "snapshot_digest", report.snapshot_digest)
    bad_report = report
    object.__setattr__(bad_report, "repository_digest", "0" * 64)
    with pytest.raises(DecisionContextError, match="REPOSITORY_MISMATCH"):
        engine.construct_context(bad_report)


def test_policy_and_engine_versions_fail_closed(tmp_path):
    _, repository, _ = setup_engine(tmp_path)
    with pytest.raises(ValueError, match="INVALID_CONTEXT_POLICY"):
        DecisionContextPolicy(context_engine_version="PR999")
    with pytest.raises(DecisionContextError, match="POLICY_MISMATCH"):
        GovernedDecisionContextEngine(repository, policy=object())


def test_snapshot_chain_and_context_replay(tmp_path):
    report, _, engine = setup_engine(tmp_path)
    first = engine.construct_context(report)
    assert engine.repository.latest_snapshot().snapshot_uuid == first.snapshot_uuid
    replay = GovernedDecisionContextEngine(engine.confidence_repository,
        DecisionContextRepository(engine.repository.root)).construct_context(report)
    assert replay.snapshot_uuid == first.snapshot_uuid
    assert replay.repository_digest == first.repository_digest

from uuid import uuid4

from learning.decision_context.identity import digest, report_uuid
from learning.decision_context.models import (
    DecisionContext,
    DecisionContextReport,
    DecisionContextSnapshot,
)
from learning.runtime_confidence.identity import digest as confidence_digest
from learning.runtime_confidence.identity import report_uuid as confidence_report_uuid


def _invalid_context(context, **changes):
    values = context.identity_payload()
    values.update(changes)
    with pytest.raises(ValueError, match="INVALID_DECISION_CONTEXT"):
        DecisionContext.create(**values)


def _invalid_snapshot(snapshot, **changes):
    values = snapshot.identity_payload()
    values.update(changes)
    with pytest.raises(ValueError, match="INVALID_CONTEXT_SNAPSHOT"):
        DecisionContextSnapshot.create(**values)


def test_context_model_independently_enforces_policy_mapping_and_band(tmp_path):
    report, _, engine = setup_engine(tmp_path)
    context = engine.construct_context(report).decision_contexts[0]
    for changes in (
        {"context_policy_uuid": "not-a-uuid"},
        {"context_policy_digest": "not-a-digest"},
        {"context_policy_version": ""},
        {"context_engine_version": "PR183.9.9"},
        {"context_state": "REJECTED"},
        {"context_reason": "ARBITRARY_REASON"},
        {"confidence_state": "UNKNOWN_CONFIDENCE"},
        {"confidence_band": "EXTREME"},
    ):
        _invalid_context(context, **changes)


def test_snapshot_model_enforces_all_governance_policy_fields(tmp_path):
    report, _, engine = setup_engine(tmp_path)
    engine.construct_context(report)
    snapshot = engine.repository.latest_snapshot()
    for changes in (
        {"context_policy_uuid": "not-a-uuid"},
        {"context_policy_digest": "not-a-digest"},
        {"context_policy_version": ""},
        {"context_engine_version": "PR183.9.9"},
        {"confidence_policy_uuid": "not-a-uuid"},
        {"confidence_policy_digest": "not-a-digest"},
        {"confidence_policy_version": ""},
        {"confidence_engine_version": ""},
    ):
        _invalid_snapshot(snapshot, **changes)


def test_canonical_artifact_reconstruction_from_dict(tmp_path):
    report, _, engine = setup_engine(tmp_path)
    context_report = engine.construct_context(report)
    context = context_report.decision_contexts[0]
    snapshot = engine.repository.latest_snapshot()
    assert DecisionContext(**context.to_dict()) == context
    assert DecisionContextSnapshot(**snapshot.to_dict()) == snapshot
    assert DecisionContextReport(**context_report.to_dict()) == context_report


def test_repository_filename_noncanonical_json_and_save_taxonomy(tmp_path):
    report, _, engine = setup_engine(tmp_path)
    context = engine.construct_context(report).decision_contexts[0]
    repository = engine.repository
    with pytest.raises(DecisionContextError, match="INVALID_DECISION_CONTEXT"):
        repository.save(object())

    original = repository.root / f"{context.context_uuid}.json"
    mismatch = repository.root / f"{uuid4()}.json"
    mismatch.write_bytes(original.read_bytes())
    with pytest.raises(DecisionContextError, match="FILENAME_IDENTITY_MISMATCH"):
        repository.records()
    mismatch.unlink()

    original.write_text(json.dumps(context.to_dict(), indent=2))
    with pytest.raises(DecisionContextError, match="NONCANONICAL_DECISION_CONTEXT_JSON"):
        repository.records()


def test_same_identity_different_content_collision_and_mixed_policy(tmp_path):
    report, _, engine = setup_engine(tmp_path)
    context = engine.construct_context(report).decision_contexts[0]
    path = engine.repository.root / f"{context.context_uuid}.json"
    path.write_bytes(b"{}")
    with pytest.raises(DecisionContextError, match="REPLAY_COLLISION"):
        engine.repository.save(context)

    clean_report, _, clean_engine = setup_engine(tmp_path / "mixed")
    clean_engine.construct_context(clean_report)
    stored = clean_engine.repository.records()[0]
    object.__setattr__(stored, "context_policy_version", "FOREIGN_POLICY")
    clean_engine.repository.records = lambda: (stored,)
    with pytest.raises(DecisionContextError, match="POLICY_MISMATCH"):
        clean_engine.construct_context(clean_report)


def _chain_repository(tmp_path):
    report, _, engine = setup_engine(tmp_path)
    engine.construct_context(report)
    return engine.repository, engine.repository.latest_snapshot()


def test_snapshot_parent_uuid_and_digest_corruption_and_orphan(tmp_path):
    for name, changes in (
        ("uuid", {"previous_snapshot_uuid": str(uuid4()), "previous_snapshot_digest": "a" * 64}),
        ("digest", {"previous_snapshot_digest": "b" * 64}),
    ):
        repository, root = _chain_repository(tmp_path / name)
        values = root.identity_payload()
        values.update(changes)
        if name == "digest":
            values["previous_snapshot_uuid"] = root.snapshot_uuid
        child = DecisionContextSnapshot.create(**values)
        repository.save_snapshot(child)
        with pytest.raises(DecisionContextError, match="SNAPSHOT_MISMATCH"):
            repository.latest_snapshot()


def test_snapshot_cycle_multiple_heads_and_disconnected_orphan(tmp_path):
    repository, root = _chain_repository(tmp_path / "cycle")
    second_values = root.identity_payload()
    second_values.update(generated_at="2026-07-25T00:00:01Z")
    second = DecisionContextSnapshot.create(**second_values)
    repository.save_snapshot(second)
    with pytest.raises(DecisionContextError, match="SNAPSHOT_MISMATCH"):
        repository.latest_snapshot()

    cycle_repository, cycle_root = _chain_repository(tmp_path / "actual-cycle")
    cycle_values = cycle_root.identity_payload()
    cycle_values.update(
        previous_snapshot_uuid=cycle_root.snapshot_uuid,
        previous_snapshot_digest=cycle_root.snapshot_digest,
        generated_at="2026-07-25T00:00:02Z",
    )
    cycle_child = DecisionContextSnapshot.create(**cycle_values)
    object.__setattr__(cycle_root, "previous_snapshot_uuid", cycle_child.snapshot_uuid)
    object.__setattr__(cycle_root, "previous_snapshot_digest", cycle_child.snapshot_digest)
    cycle_repository.snapshots = lambda: (cycle_root, cycle_child)
    with pytest.raises(DecisionContextError, match="SNAPSHOT_MISMATCH"):
        cycle_repository.latest_snapshot()


def test_confidence_record_uses_canonical_latest_snapshot(tmp_path):
    confidence_report, confidence_repository, engine = setup_engine(tmp_path)
    record = confidence_report.confidence_records[0]
    first = confidence_repository.latest_snapshot()
    values = first.identity_payload()
    values.update(
        previous_snapshot_uuid=first.snapshot_uuid,
        previous_snapshot_digest=first.snapshot_digest,
        generated_at="2026-07-25T00:00:03Z",
    )
    latest = type(first).create(**values)
    confidence_repository.save_snapshot(latest)
    output = engine.construct_context(record)
    assert output.decision_contexts[0].confidence_snapshot_uuid == latest.snapshot_uuid


def test_confidence_report_identity_digest_and_membership_fail_closed(tmp_path):
    source_report, _, engine = setup_engine(tmp_path / "source")
    object.__setattr__(source_report, "report_uuid", str(uuid4()))
    with pytest.raises(DecisionContextError, match="BROKEN_PROVENANCE"):
        engine.construct_context(source_report)

    digest_report, _, digest_engine = setup_engine(tmp_path / "digest")
    object.__setattr__(digest_report, "report_digest", "a" * 64)
    with pytest.raises(DecisionContextError, match="BROKEN_PROVENANCE"):
        digest_engine.construct_context(digest_report)

    bound_report, repository, membership_engine = setup_engine(tmp_path / "bound")
    foreign_report, foreign_repository, _ = setup_engine(tmp_path / "foreign")
    foreign = foreign_report.confidence_records[0]
    original_records = repository.records
    canonical_latest = repository.latest_snapshot()
    repository.records = lambda: original_records() + (foreign,)
    repository.latest_snapshot = lambda: canonical_latest
    values = bound_report.identity_payload()
    values["confidence_records"] = [foreign.to_dict()]
    values["processed_record_count"] = 1
    values["new_confidence_record_count"] = 1
    values["duplicate_confidence_record_count"] = 0
    values["confidence_evaluated_count"] = int(foreign.confidence_state == "CONFIDENCE_EVALUATED")
    values["insufficient_confidence_evidence_count"] = int(foreign.confidence_state == "INSUFFICIENT_CONFIDENCE_EVIDENCE")
    values["rejected_count"] = int(foreign.confidence_state == "REJECTED")
    object.__setattr__(bound_report, "confidence_records", (foreign,))
    for name in (
        "processed_record_count", "new_confidence_record_count",
        "duplicate_confidence_record_count", "confidence_evaluated_count",
        "insufficient_confidence_evidence_count", "rejected_count",
    ):
        object.__setattr__(bound_report, name, values[name])
    identity_payload = bound_report.identity_payload()
    identity = confidence_report_uuid(identity_payload)
    object.__setattr__(bound_report, "report_uuid", identity)
    object.__setattr__(bound_report, "report_digest", confidence_digest({"report_uuid": identity, **identity_payload}))
    with pytest.raises(DecisionContextError, match="SNAPSHOT_MISMATCH"):
        membership_engine.construct_context(bound_report)


def test_snapshot_rejects_malformed_and_duplicate_context_identities(tmp_path):
    report, _, engine = setup_engine(tmp_path)
    engine.construct_context(report)
    snapshot = engine.repository.latest_snapshot()
    valid_uuid_value, valid_digest_value = snapshot.context_identities[0]
    for identities in (
        (("not-a-uuid", valid_digest_value),),
        ((valid_uuid_value, "not-a-digest"),),
        (
            (valid_uuid_value, valid_digest_value),
            (valid_uuid_value, valid_digest_value),
        ),
        (
            (valid_uuid_value, valid_digest_value),
            (valid_uuid_value, "f" * 64),
        ),
    ):
        _invalid_snapshot(
            snapshot,
            context_identities=identities,
            record_count=len(identities),
        )


def test_report_rejects_duplicate_contexts_even_with_recomputed_identity(tmp_path):
    source_report, _, engine = setup_engine(tmp_path)
    output = engine.construct_context(source_report)
    context = output.decision_contexts[0]
    values = output.identity_payload()
    values.update(
        decision_contexts=(context, context),
        processed_count=2,
        prepared_count=2,
        duplicate_count=1,
    )
    with pytest.raises(ValueError, match="INVALID_CONTEXT_REPORT"):
        DecisionContextReport.create(**values)


def test_repository_corrupt_json_and_invalid_snapshot_taxonomy(tmp_path):
    source_report, _, engine = setup_engine(tmp_path)
    output = engine.construct_context(source_report)
    context = output.decision_contexts[0]
    path = engine.repository.root / f"{context.context_uuid}.json"
    path.write_text("{broken-json")
    with pytest.raises(DecisionContextError, match="CORRUPT_DECISION_CONTEXT_REPOSITORY"):
        engine.repository.records()
    with pytest.raises(DecisionContextError, match="INVALID_CONTEXT_SNAPSHOT"):
        engine.repository.save_snapshot(object())


def test_snapshot_head_must_match_repository_identities_and_digest(tmp_path):
    identity_repository, identity_head = _chain_repository(tmp_path / "identities")
    object.__setattr__(identity_head, "context_identities", ())
    object.__setattr__(identity_head, "record_count", 0)
    identity_repository.snapshots = lambda: (identity_head,)
    with pytest.raises(DecisionContextError, match="SNAPSHOT_MISMATCH"):
        identity_repository.latest_snapshot()

    digest_repository, digest_head = _chain_repository(tmp_path / "digest")
    object.__setattr__(digest_head, "repository_digest", "f" * 64)
    digest_repository.snapshots = lambda: (digest_head,)
    with pytest.raises(DecisionContextError, match="REPOSITORY_MISMATCH"):
        digest_repository.latest_snapshot()


def test_upstream_confidence_partition_mismatch_fails_closed(tmp_path):
    source_report, repository, engine = setup_engine(tmp_path)
    record = source_report.confidence_records[0]
    snapshot = repository.latest_snapshot()
    object.__setattr__(record, "confidence_engine_version", "PR182.FOREIGN")
    with pytest.raises(DecisionContextError, match="POLICY_MISMATCH"):
        engine._verify_confidence_partition((record,), snapshot)


def test_record_absent_from_latest_and_stored_confidence_corruption(tmp_path):
    source_report, repository, engine = setup_engine(tmp_path / "absent")
    foreign_report, _, _ = setup_engine(tmp_path / "foreign-record")
    foreign = foreign_report.confidence_records[0]
    original_records = repository.records
    canonical_latest = repository.latest_snapshot()
    repository.records = lambda: original_records() + (foreign,)
    repository.latest_snapshot = lambda: canonical_latest
    with pytest.raises(DecisionContextError, match="SNAPSHOT_MISMATCH"):
        engine.construct_context(foreign)

    corrupt_report, corrupt_repository, corrupt_engine = setup_engine(
        tmp_path / "corrupt"
    )
    stored = corrupt_report.confidence_records[0]
    stored_path = corrupt_repository.path_for(stored.confidence_uuid)
    stored_path.write_text("{}")
    with pytest.raises(DecisionContextError, match="BROKEN_PROVENANCE"):
        corrupt_engine.construct_context(stored)
