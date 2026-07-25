"""Comprehensive PR182 governed advisory confidence architecture tests."""

import json
from dataclasses import replace
from math import inf, nan
from pathlib import Path
import sys
from uuid import uuid4

import pytest

sys.path.insert(0, str(Path(__file__).parents[2]))
sys.path.insert(1, str(Path(__file__).parent))

from learning.runtime_confidence import (
    ConfidenceDimensionResult,
    RuntimeConfidenceError,
    RuntimeConfidenceEvaluator,
    RuntimeConfidencePolicy,
    RuntimeConfidenceRepository,
)
from learning.runtime_confidence.models import ConfidenceRecord
from learning.runtime_selection import (
    KnowledgeEligibilityRecord,
    RuntimeKnowledgeSelectionRepository,
    RuntimeKnowledgeSelector,
)
from learning.runtime_selection.models import RuntimeKnowledgeSelectionSnapshot
from test_pr181_runtime_selection import artifacts


def governed_artifacts(root):
    packaged, runtime_repository = artifacts(root)
    eligibility_repository = RuntimeKnowledgeSelectionRepository(
        root / "runtime_selection"
    )
    report = RuntimeKnowledgeSelector(
        runtime_repository, eligibility_repository
    ).evaluate_eligibility(packaged)
    evaluator = RuntimeConfidenceEvaluator(
        eligibility_repository,
        RuntimeConfidenceRepository(root / "runtime_confidence"),
    )
    return report, eligibility_repository, evaluator


def alternate_eligibility(root, state):
    report, original_repository, _ = governed_artifacts(root / "source")
    original = report.runtime_selections[0]
    values = original.identity_payload()
    if state == "INSUFFICIENT_SELECTION_EVIDENCE":
        values.update(
            source_validation_state="INSUFFICIENT_EVIDENCE",
            selection_state=state,
            selection_reasons=("VALIDATION_STATE_INSUFFICIENT",),
        )
    else:
        values.update(
            source_runtime_package_state="INVALID",
            selection_state="REJECTED",
            selection_reasons=("RUNTIME_PACKAGE_STATE_NOT_ELIGIBLE",),
        )
    record = KnowledgeEligibilityRecord.create(**values)
    repository = RuntimeKnowledgeSelectionRepository(root / "eligibility")
    repository.save(record)
    source_snapshot = original_repository.latest_snapshot()
    snapshot_values = source_snapshot.identity_payload()
    snapshot_values.update(
        selection_identities=((record.selection_uuid, record.selection_digest),),
        selection_count=1,
        repository_digest=repository.digest(),
        previous_snapshot_uuid=None,
        previous_snapshot_digest=None,
    )
    snapshot = RuntimeKnowledgeSelectionSnapshot.create(**snapshot_values)
    repository.save_snapshot(snapshot)
    evaluator = RuntimeConfidenceEvaluator(
        repository, RuntimeConfidenceRepository(root / "confidence")
    )
    return record, repository, evaluator


def test_canonical_api_exact_types_and_authority_boundary(tmp_path):
    report, repository, evaluator = governed_artifacts(tmp_path)
    assert evaluator.run.__func__ is evaluator.evaluate_confidence.__func__
    for source in (report.runtime_selections[0], report, repository.latest_snapshot()):
        assert evaluator.evaluate_confidence(source).advisory_only is True

    class EligibilitySubclass(KnowledgeEligibilityRecord):
        pass

    subclass = EligibilitySubclass(**report.runtime_selections[0].to_dict())
    for invalid in (None, {}, [], (), object(), subclass, report.runtime_selections):
        with pytest.raises(RuntimeConfidenceError, match="INVALID_ELIGIBILITY"):
            evaluator.evaluate_confidence(invalid)
    forbidden = ("activate", "apply", "authorize", "execute", "rank_for_runtime")
    assert not any(hasattr(evaluator, name) for name in forbidden)
    source = Path("learning/runtime_confidence/engine.py").read_text().lower()
    assert not any(
        token in source
        for token in ("ordersend", "mt5", "bridge.", "position_management")
    )


def test_dimensions_weighted_score_reasons_band_and_recomputation(tmp_path):
    report, _, evaluator = governed_artifacts(tmp_path)
    record = evaluator.evaluate_confidence(report).confidence_records[0]
    assert len(record.confidence_dimension_results) == 9
    assert tuple(item.dimension for item in record.confidence_dimension_results) == (
        evaluator.policy.dimension_definitions
    )
    assert sum(item.weight for item in record.confidence_dimension_results) == 1.0
    recomputed = round(
        sum(item.weighted_contribution for item in record.confidence_dimension_results),
        evaluator.policy.score_precision,
    )
    assert record.confidence_score == recomputed
    assert record.confidence_band == "VERY_HIGH"
    assert record.confidence_reasons[-1] == "ADVISORY_CONFIDENCE_CALCULATED"
    assert len(record.confidence_reasons) == len(set(record.confidence_reasons))
    assert record.authority_scope == "ADVISORY_CONFIDENCE_ONLY"


def test_insufficient_and_rejected_are_evidence_scored_not_fixed_mapping(tmp_path):
    insufficient, _, evaluator = alternate_eligibility(
        tmp_path / "insufficient", "INSUFFICIENT_SELECTION_EVIDENCE"
    )
    insufficient_record = evaluator.evaluate_confidence(
        insufficient
    ).confidence_records[0]
    assert insufficient_record.confidence_state == "INSUFFICIENT_CONFIDENCE_EVIDENCE"
    assert 0.0 < insufficient_record.confidence_score < 1.0
    assert any(
        item.normalized_score not in (0.0, 1.0)
        for item in insufficient_record.confidence_dimension_results
    )

    rejected, _, rejected_evaluator = alternate_eligibility(
        tmp_path / "rejected", "REJECTED"
    )
    rejected_record = rejected_evaluator.evaluate_confidence(
        rejected
    ).confidence_records[0]
    assert rejected_record.confidence_state == "REJECTED"
    assert 0.0 < rejected_record.confidence_score < 1.0
    assert rejected_record.confidence_score != insufficient_record.confidence_score


def test_policy_behavior_changes_policy_and_record_identity(tmp_path):
    report, eligibility_repository, evaluator = governed_artifacts(tmp_path)
    baseline = evaluator.evaluate_confidence(report).confidence_records[0]
    weights = list(RuntimeConfidencePolicy().dimension_weights)
    weights[0] = (weights[0][0], weights[0][1] + 0.01)
    weights[1] = (weights[1][0], weights[1][1] - 0.01)
    changed_weights = RuntimeConfidencePolicy(dimension_weights=tuple(weights))
    changed_thresholds = RuntimeConfidencePolicy(
        confidence_band_thresholds=(
            ("VERY_LOW", 0.0),
            ("LOW", 0.2),
            ("MODERATE", 0.4),
            ("HIGH", 0.6),
            ("VERY_HIGH", 0.9),
        )
    )
    assert (
        changed_weights.confidence_policy_uuid
        != evaluator.policy.confidence_policy_uuid
    )
    assert (
        changed_thresholds.confidence_policy_digest
        != evaluator.policy.confidence_policy_digest
    )
    changed = (
        RuntimeConfidenceEvaluator(
            eligibility_repository,
            RuntimeConfidenceRepository(tmp_path / "changed"),
            changed_weights,
        )
        .evaluate_confidence(report)
        .confidence_records[0]
    )
    assert changed.confidence_uuid != baseline.confidence_uuid


@pytest.mark.parametrize(
    "kwargs",
    (
        {"dimension_weights": (("ELIGIBILITY_EVIDENCE_COMPLETENESS", nan),)},
        {"dimension_weights": (("ELIGIBILITY_EVIDENCE_COMPLETENESS", inf),)},
        {
            "dimension_weights": tuple(
                (name, 0.2) for name in RuntimeConfidencePolicy().dimension_definitions
            )
        },
        {"confidence_band_thresholds": (("LOW", 0.5), ("HIGH", 0.4))},
        {"confidence_band_thresholds": (("LOW", -0.1), ("HIGH", 0.4))},
        {"score_precision": 0},
    ),
)
def test_policy_numeric_safety(kwargs):
    with pytest.raises(ValueError, match="INVALID_CONFIDENCE_POLICY"):
        RuntimeConfidencePolicy(**kwargs)


@pytest.mark.parametrize("value", (nan, inf, -inf, -0.1, 1.1))
def test_dimension_numeric_safety(value):
    with pytest.raises(ValueError, match="INVALID_CONFIDENCE_EVIDENCE"):
        ConfidenceDimensionResult(
            dimension="ELIGIBILITY_EVIDENCE_COMPLETENESS",
            state="PARTIAL",
            raw_value="TEST",
            normalized_score=float(value),
            weight=0.15,
            weighted_contribution=0.0,
            reasons=("ELIGIBILITY_EVIDENCE_INSUFFICIENT",),
        )


def test_rounding_is_half_even_and_deterministic():
    result = ConfidenceDimensionResult(
        dimension="ELIGIBILITY_EVIDENCE_COMPLETENESS",
        state="PARTIAL",
        raw_value="TEST",
        normalized_score=0.333333333333,
        weight=0.15,
        weighted_contribution=0.05,
        reasons=("ELIGIBILITY_EVIDENCE_INSUFFICIENT",),
    )
    assert result.weighted_contribution == 0.05


def test_complete_standalone_provenance_is_retained(tmp_path):
    report, _, evaluator = governed_artifacts(tmp_path)
    source = report.runtime_selections[0]
    record = evaluator.evaluate_confidence(source).confidence_records[0]
    pairs = (
        (record.source_eligibility_uuid, source.selection_uuid),
        (record.source_eligibility_digest, source.selection_digest),
        (record.source_runtime_package_digest, source.source_runtime_package_digest),
        (record.source_runtime_snapshot_digest, source.source_runtime_snapshot_digest),
        (
            record.source_runtime_repository_digest,
            source.source_runtime_repository_digest,
        ),
        (record.source_registry_digest, source.source_registry_digest),
        (record.source_promotion_digest, source.source_promotion_digest),
        (record.source_validation_digest, source.source_validation_digest),
        (record.source_memory_digest, source.source_memory_digest),
        (record.source_pattern_hash, source.source_pattern_hash),
        (record.source_selection_policy_digest, source.selection_policy_digest),
    )
    assert all(left == right for left, right in pairs)
    assert record.source_eligibility_reasons == source.selection_reasons
    assert record.source_promotion_reasons == source.source_promotion_reasons


@pytest.mark.parametrize(
    "field,value",
    (
        ("selection_uuid", str(uuid4())),
        ("selection_digest", "f" * 64),
        ("selection_state", "REJECTED"),
        ("selection_reasons", ("RUNTIME_PACKAGE_STATE_NOT_ELIGIBLE",)),
        ("source_runtime_package_uuid", str(uuid4())),
        ("source_runtime_package_digest", "e" * 64),
        ("source_registry_digest", "d" * 64),
        ("source_promotion_digest", "c" * 64),
        ("source_validation_digest", "b" * 64),
        ("selection_policy_uuid", str(uuid4())),
        ("selection_policy_digest", "a" * 64),
    ),
)
def test_source_tampering_fails_closed(tmp_path, field, value):
    report, _, evaluator = governed_artifacts(tmp_path)
    damaged = replace(report.runtime_selections[0])
    object.__setattr__(damaged, field, value)
    with pytest.raises(RuntimeConfidenceError, match="BROKEN_PROVENANCE"):
        evaluator.evaluate_confidence(damaged)


def test_historical_report_and_earliest_record_membership(tmp_path):
    report, repository, evaluator = governed_artifacts(tmp_path)
    first = repository.latest_snapshot()
    values = first.identity_payload()
    values.update(
        previous_snapshot_uuid=first.snapshot_uuid,
        previous_snapshot_digest=first.snapshot_digest,
        source_runtime_snapshot_uuid=str(uuid4()),
        source_runtime_snapshot_digest="a" * 64,
    )
    second = RuntimeKnowledgeSelectionSnapshot.create(**values)
    repository.save_snapshot(second)
    historical = evaluator.evaluate_confidence(report)
    record_replay = evaluator.evaluate_confidence(report.runtime_selections[0])
    assert historical.source_eligibility_snapshot_uuid == first.snapshot_uuid
    assert record_replay.source_eligibility_snapshot_uuid == first.snapshot_uuid


def test_eligibility_snapshot_chain_multiple_heads_and_missing_predecessor(tmp_path):
    report, repository, evaluator = governed_artifacts(tmp_path / "heads")
    first = repository.latest_snapshot()
    values = first.identity_payload()
    values.update(
        source_runtime_snapshot_uuid=str(uuid4()),
        source_runtime_snapshot_digest="a" * 64,
        previous_snapshot_uuid=None,
        previous_snapshot_digest=None,
    )
    repository.save_snapshot(RuntimeKnowledgeSelectionSnapshot.create(**values))
    with pytest.raises(RuntimeConfidenceError, match="BROKEN_PROVENANCE"):
        evaluator.evaluate_confidence(report.runtime_selections[0])

    report, repository, evaluator = governed_artifacts(tmp_path / "predecessor")
    first = repository.latest_snapshot()
    values = first.identity_payload()
    values.update(
        source_runtime_snapshot_uuid=str(uuid4()),
        source_runtime_snapshot_digest="b" * 64,
        previous_snapshot_uuid=str(uuid4()),
        previous_snapshot_digest="c" * 64,
    )
    repository.save_snapshot(RuntimeKnowledgeSelectionSnapshot.create(**values))
    with pytest.raises(RuntimeConfidenceError, match="BROKEN_PROVENANCE"):
        evaluator.evaluate_confidence(report.runtime_selections[0])


def test_source_form_bindings_and_snapshot_context_isolation(tmp_path):
    report, repository, evaluator = governed_artifacts(tmp_path)
    record_report = evaluator.evaluate_confidence(report.runtime_selections[0])
    snapshot_report = evaluator.evaluate_confidence(repository.latest_snapshot())
    eligibility_report = evaluator.evaluate_confidence(report)
    assert record_report.source_artifact_type == "ELIGIBILITY_RECORD"
    assert (
        record_report.source_artifact_uuid
        == report.runtime_selections[0].selection_uuid
    )
    assert snapshot_report.source_artifact_type == "ELIGIBILITY_SNAPSHOT"
    assert (
        snapshot_report.source_artifact_uuid
        == repository.latest_snapshot().snapshot_uuid
    )
    assert eligibility_report.source_artifact_type == "ELIGIBILITY_REPORT"
    assert eligibility_report.source_artifact_uuid == report.report_uuid
    assert (
        len(
            {
                record_report.snapshot_uuid,
                snapshot_report.snapshot_uuid,
                eligibility_report.snapshot_uuid,
            }
        )
        == 3
    )


def test_report_binding_counters_snapshot_repository_and_partition(tmp_path):
    report, _, evaluator = governed_artifacts(tmp_path)
    cases = (
        ("processed_package_count", 99, "REPORT_BINDING_MISMATCH"),
        ("report_uuid", str(uuid4()), "REPORT_BINDING_MISMATCH"),
        ("report_digest", "f" * 64, "REPORT_BINDING_MISMATCH"),
        ("selection_snapshot_uuid", str(uuid4()), "SNAPSHOT_MISMATCH"),
        ("selection_snapshot_digest", "e" * 64, "SNAPSHOT_MISMATCH"),
        ("repository_digest", "d" * 64, "REPOSITORY_MISMATCH"),
        ("selection_policy_digest", "c" * 64, "UPSTREAM_PARTITION_MISMATCH"),
    )
    for field, value, code in cases:
        damaged = replace(report)
        object.__setattr__(damaged, field, value)
        with pytest.raises(RuntimeConfidenceError, match=code):
            evaluator.evaluate_confidence(damaged)


def test_append_only_replay_counters_and_canonical_serialization(tmp_path):
    report, _, evaluator = governed_artifacts(tmp_path)
    first = evaluator.evaluate_confidence(report)
    record = first.confidence_records[0]
    path = evaluator.repository.path_for(record.confidence_uuid)
    original = path.read_bytes()
    replay = evaluator.evaluate_confidence(report)
    assert first.processed_record_count == first.new_confidence_record_count == 1
    assert first.duplicate_confidence_record_count == 0
    assert (
        replay.processed_record_count == replay.duplicate_confidence_record_count == 1
    )
    assert replay.new_confidence_record_count == 0
    assert replay.confidence_evaluated_count == 1
    assert replay.insufficient_confidence_evidence_count == replay.rejected_count == 0
    assert path.read_bytes() == original
    assert (
        original
        == json.dumps(
            record.to_dict(), sort_keys=True, separators=(",", ":"), allow_nan=False
        ).encode()
    )


def test_repository_record_and_snapshot_corruption_codes(tmp_path):
    report, _, evaluator = governed_artifacts(tmp_path)
    result = evaluator.evaluate_confidence(report)
    record_path = evaluator.repository.path_for(
        result.confidence_records[0].confidence_uuid
    )
    raw = json.loads(record_path.read_text())
    raw["confidence_score"] = 0.5
    record_path.write_text(json.dumps(raw))
    with pytest.raises(RuntimeConfidenceError, match="CORRUPT_CONFIDENCE_REPOSITORY"):
        evaluator.repository.records()

    _, _, clean = governed_artifacts(tmp_path / "snapshot")
    clean_result = clean.evaluate_confidence(
        governed_artifacts(tmp_path / "snapshot")[0]
    )
    snapshot_path = (
        clean.repository.snapshot_root / f"{clean_result.snapshot_uuid}.json"
    )
    raw = json.loads(snapshot_path.read_text())
    raw["snapshot_digest"] = "f" * 64
    snapshot_path.write_text(json.dumps(raw))
    with pytest.raises(
        RuntimeConfidenceError, match="CORRUPT_CONFIDENCE_SNAPSHOT_REPOSITORY"
    ):
        clean.repository.snapshots()


def test_repository_filename_collision_and_mixed_policy_partition(tmp_path):
    report, repository, evaluator = governed_artifacts(tmp_path)
    result = evaluator.evaluate_confidence(report)
    record = result.confidence_records[0]
    wrong = evaluator.repository.root / f"{uuid4()}.json"
    wrong.write_bytes(
        evaluator.repository.path_for(record.confidence_uuid).read_bytes()
    )
    with pytest.raises(
        RuntimeConfidenceError, match="CONFIDENCE_FILENAME_IDENTITY_MISMATCH"
    ):
        evaluator.repository.records()
    wrong.unlink()

    changed = RuntimeConfidencePolicy(
        confidence_policy_version="PR182-CONFIDENCE-POLICY.2.1"
    )
    with pytest.raises(RuntimeConfidenceError, match="POLICY_MISMATCH"):
        RuntimeConfidenceEvaluator(
            repository, evaluator.repository, changed
        ).evaluate_confidence(report)


def test_mixed_pr181_and_upstream_partition_is_rejected(tmp_path):
    report, _, evaluator = governed_artifacts(tmp_path)
    evaluator.evaluate_confidence(report)
    record, repository, _ = alternate_eligibility(
        tmp_path / "alternate", "INSUFFICIENT_SELECTION_EVIDENCE"
    )
    changed_values = record.identity_payload()
    changed_values.update(
        selector_version="PR181.changed",
        selection_policy_version="PR181-SELECTION-POLICY.changed",
        selection_policy_uuid=str(uuid4()),
        selection_policy_digest="a" * 64,
    )
    changed = KnowledgeEligibilityRecord.create(**changed_values)
    changed_repository = RuntimeKnowledgeSelectionRepository(
        tmp_path / "changed-selection"
    )
    changed_repository.save(changed)
    source_snapshot = repository.latest_snapshot()
    snapshot_values = source_snapshot.identity_payload()
    snapshot_values.update(
        selector_version=changed.selector_version,
        selection_policy_version=changed.selection_policy_version,
        selection_policy_uuid=changed.selection_policy_uuid,
        selection_policy_digest=changed.selection_policy_digest,
        selection_identities=((changed.selection_uuid, changed.selection_digest),),
        selection_count=1,
        repository_digest=changed_repository.digest(),
        previous_snapshot_uuid=None,
        previous_snapshot_digest=None,
    )
    changed_repository.save_snapshot(
        RuntimeKnowledgeSelectionSnapshot.create(**snapshot_values)
    )
    with pytest.raises(RuntimeConfidenceError, match="UPSTREAM_PARTITION_MISMATCH"):
        RuntimeConfidenceEvaluator(
            changed_repository, evaluator.repository
        ).evaluate_confidence(changed)


def test_replay_collision_is_rejected(tmp_path):
    report, _, evaluator = governed_artifacts(tmp_path)
    result = evaluator.evaluate_confidence(report)
    record = result.confidence_records[0]
    path = evaluator.repository.path_for(record.confidence_uuid)
    original = path.read_bytes()
    path.write_bytes(original + b" ")
    with pytest.raises(RuntimeConfidenceError, match="CORRUPT_CONFIDENCE_REPOSITORY"):
        evaluator.evaluate_confidence(report)

    path.write_bytes(original)
    damaged = replace(record)
    object.__setattr__(damaged, "confidence_score", 0.5)
    with pytest.raises(RuntimeConfidenceError, match="REPLAY_COLLISION"):
        evaluator.repository.save(damaged)


def test_model_rejects_score_contribution_band_and_authority_tampering(tmp_path):
    report, _, evaluator = governed_artifacts(tmp_path)
    record = evaluator.evaluate_confidence(report).confidence_records[0]
    values = record.to_dict()
    values["confidence_dimension_results"] = tuple(
        ConfidenceDimensionResult(**item)
        for item in values["confidence_dimension_results"]
    )
    for field, value in (
        ("confidence_score", -0.1),
        ("confidence_score", 1.1),
        ("confidence_band", "LOW"),
        ("authority_scope", "TRADING"),
        ("advisory_only", False),
    ):
        damaged = dict(values)
        damaged[field] = value
        with pytest.raises(ValueError, match="INVALID_CONFIDENCE_RECORD"):
            ConfidenceRecord(**damaged)
