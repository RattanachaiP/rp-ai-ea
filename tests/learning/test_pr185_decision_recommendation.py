"""PR185 governed advisory Decision Recommendation tests."""

import json
import pytest
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).parents[2]))
sys.path.insert(1, str(Path(__file__).parent))
from learning.decision_recommendation import (
    DecisionRecommendationError,
    DecisionRecommendationPolicy,
    DecisionRecommendationRepository,
    GovernedDecisionRecommendationEngine,
)
from learning.decision_recommendation.identity import canonical_bytes
from test_pr184_decision_intelligence import setup_engine as setup_intelligence_engine


def setup_engine(root):
    context_report, _, intelligence_engine = setup_intelligence_engine(root)
    intelligence_report = intelligence_engine.construct_intelligence(context_report)
    engine = GovernedDecisionRecommendationEngine(
        intelligence_engine.repository,
        DecisionRecommendationRepository(root / "decision_recommendation"),
    )
    return intelligence_report, intelligence_engine.repository, engine


def test_supported_inputs_produce_immutable_advisory_recommendation(tmp_path):
    report, repo, engine = setup_engine(tmp_path)
    for source in (report.decision_intelligences[0], report, repo.latest_snapshot()):
        result = engine.construct_recommendation(source)
        item = result.recommendations[0]
        assert item.recommendation_state == "RECOMMENDATION_READY"
        assert item.recommendation_classification in {
            "READY_FOR_DECISION",
            "MANUAL_REVIEW",
            "NOT_READY",
        }
        assert item.advisory_only is result.advisory_only is True
        assert item.authority_scope == "ADVISORY_DECISION_RECOMMENDATION_ONLY"
    for invalid in (None, {}, [], report.decision_intelligences):
        with pytest.raises(
            DecisionRecommendationError, match="INVALID_DECISION_INTELLIGENCE"
        ):
            engine.recommend(invalid)
    assert not any(
        hasattr(engine, n) for n in ("trade", "execute", "activate", "publish_decision")
    )


def test_replay_is_canonical_append_only_and_policy_governed(tmp_path):
    report, _, engine = setup_engine(tmp_path)
    first = engine.run(report)
    paths = tuple(engine.repository.root.glob("*.json"))
    second = engine.run(report)
    assert (
        second.duplicate_count == 1
        and second.recommendations == first.recommendations
        and tuple(engine.repository.root.glob("*.json")) == paths
    )
    item = first.recommendations[0]
    path = engine.repository.root / f"{item.recommendation_uuid}.json"
    assert path.read_bytes() == canonical_bytes(item.to_dict())
    assert json.loads(path.read_text())["recommendation_classification"] not in {
        "BUY",
        "SELL",
        "HOLD",
    }
    with pytest.raises(ValueError, match="INVALID_RECOMMENDATION_POLICY"):
        DecisionRecommendationPolicy(recommendation_engine_version="PR999")


def test_provenance_and_repository_tampering_fail_closed(tmp_path):
    report, repo, engine = setup_engine(tmp_path)
    item = report.decision_intelligences[0]
    object.__setattr__(item, "intelligence_digest", "0" * 64)
    with pytest.raises(DecisionRecommendationError, match="BROKEN_PROVENANCE"):
        engine.run(item)
    object.__setattr__(
        item, "intelligence_digest", repo.records()[0].intelligence_digest
    )
    produced = engine.run(report).recommendations[0]
    path = engine.repository.root / f"{produced.recommendation_uuid}.json"
    path.write_text(json.dumps(produced.to_dict(), indent=2))
    with pytest.raises(
        DecisionRecommendationError, match="NONCANONICAL_DECISION_RECOMMENDATION_JSON"
    ):
        engine.repository.records()


@pytest.mark.parametrize(
    "changes",
    [
        {"recommendation_policy_version": ""},
        {"recommendation_policy_version": "   "},
        {"recommendation_policy_version": "PR185-RECOMMENDATION-POLICY.2.0"},
        {"recommendation_engine_version": "PR185.2.0"},
        {"ready_quality_threshold": 1},
        {"manual_review_quality_threshold": "0.5"},
        {"ready_quality_threshold": -0.01},
        {"ready_quality_threshold": 1.01},
        {"manual_review_quality_threshold": -0.01},
        {"manual_review_quality_threshold": 1.01},
        {"ready_quality_threshold": 0.4, "manual_review_quality_threshold": 0.5},
    ],
)
def test_policy_rejects_every_unsupported_version_and_threshold(changes):
    with pytest.raises(ValueError, match="INVALID_RECOMMENDATION_POLICY"):
        DecisionRecommendationPolicy(**changes)


def test_state_mapping_boundaries_are_unambiguous(tmp_path):
    from types import SimpleNamespace

    _, _, engine = setup_engine(tmp_path)

    def intelligence(state="DECISION_INTELLIGENCE_READY", quality=0.0, reliability=0.0):
        return SimpleNamespace(
            intelligence_state=state,
            decision_quality=quality,
            decision_reliability=reliability,
        )

    assert engine._classify(intelligence("REJECTED"))[:2] == ("REJECTED", "REJECTED")
    assert engine._classify(intelligence("INSUFFICIENT_DECISION_INTELLIGENCE"))[:2] == (
        "INSUFFICIENT_RECOMMENDATION_EVIDENCE",
        "INSUFFICIENT_EVIDENCE",
    )
    assert engine._classify(intelligence(quality=0.9, reliability=0.9))[:2] == (
        "RECOMMENDATION_READY",
        "READY_FOR_DECISION",
    )
    assert engine._classify(intelligence(quality=0.75, reliability=0.75))[:2] == (
        "RECOMMENDATION_READY",
        "READY_FOR_DECISION",
    )
    assert engine._classify(intelligence(quality=0.74, reliability=0.74))[:2] == (
        "RECOMMENDATION_MANUAL_REVIEW",
        "MANUAL_REVIEW",
    )
    assert engine._classify(intelligence(quality=0.50, reliability=0.0))[:2] == (
        "RECOMMENDATION_MANUAL_REVIEW",
        "MANUAL_REVIEW",
    )
    assert engine._classify(intelligence(quality=0.49, reliability=1.0))[:2] == (
        "RECOMMENDATION_NOT_READY",
        "NOT_READY",
    )


def test_exact_type_boundary_rejects_subclasses_and_empty_sources(tmp_path):
    from learning.decision_intelligence import DecisionIntelligence

    report, _, engine = setup_engine(tmp_path)

    class IntelligenceSubclass(DecisionIntelligence):
        pass

    with pytest.raises(
        DecisionRecommendationError, match="INVALID_DECISION_INTELLIGENCE"
    ):
        engine.run(IntelligenceSubclass(**report.decision_intelligences[0].to_dict()))
    with pytest.raises(
        DecisionRecommendationError, match="INVALID_DECISION_INTELLIGENCE"
    ):
        engine._verify_partition((), engine.intelligence_repository.latest_snapshot())


def test_artifacts_are_frozen_and_recompute_their_identities(tmp_path):
    from dataclasses import FrozenInstanceError
    from learning.decision_recommendation.identity import (
        digest,
        recommendation_uuid,
        report_uuid,
        snapshot_uuid,
    )

    report, _, engine = setup_engine(tmp_path)
    result = engine.run(report)
    item = result.recommendations[0]
    snapshot = engine.repository.latest_snapshot()
    assert recommendation_uuid(item.identity_payload()) == item.recommendation_uuid
    assert digest(item.digest_payload()) == item.recommendation_digest
    assert snapshot_uuid(snapshot.identity_payload()) == snapshot.snapshot_uuid
    assert digest(snapshot.identity_payload()) == snapshot.snapshot_digest
    assert report_uuid(result.identity_payload()) == result.report_uuid
    assert digest(result.digest_payload()) == result.report_digest
    with pytest.raises(FrozenInstanceError):
        item.recommendation_state = "REJECTED"
    with pytest.raises(FrozenInstanceError):
        snapshot.record_count = 0
    with pytest.raises(FrozenInstanceError):
        result.processed_count = 0


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("recommendation_policy_version", ""),
        ("recommendation_policy_version", "PR185-RECOMMENDATION-POLICY.2.0"),
        ("recommendation_engine_version", "PR185.2.0"),
        ("intelligence_policy_version", " PR184-INTELLIGENCE-POLICY.1.0"),
        ("intelligence_policy_version", "PR184-INTELLIGENCE-POLICY.2.0"),
        ("intelligence_engine_version", "PR184.2.0"),
        ("intelligence_policy_uuid", "00000000-0000-4000-8000-000000000000"),
        ("intelligence_policy_digest", "0" * 64),
    ],
)
def test_snapshot_rejects_unsupported_partition_metadata(tmp_path, field, value):
    from learning.decision_recommendation.models import DecisionRecommendationSnapshot

    report, _, engine = setup_engine(tmp_path)
    engine.run(report)
    values = engine.repository.latest_snapshot().to_dict()
    values.pop("snapshot_uuid")
    values.pop("snapshot_digest")
    values[field] = value
    with pytest.raises(ValueError, match="INVALID_RECOMMENDATION_SNAPSHOT"):
        DecisionRecommendationSnapshot.create(**values)


def test_repository_rejects_malformed_invalid_and_mismatched_files(tmp_path):
    report, _, engine = setup_engine(tmp_path)
    result = engine.run(report)
    item = result.recommendations[0]
    path = engine.repository.root / f"{item.recommendation_uuid}.json"
    path.write_text("{")
    with pytest.raises(
        DecisionRecommendationError, match="CORRUPT_DECISION_RECOMMENDATION_REPOSITORY"
    ):
        engine.repository.records()
    path.write_bytes(canonical_bytes(item.to_dict()))
    invalid = engine.repository.root / "not-a-uuid.json"
    invalid.write_text("{}")
    with pytest.raises(
        DecisionRecommendationError, match="INVALID_DECISION_RECOMMENDATION_FILENAME"
    ):
        engine.repository.records()
    invalid.unlink()
    mismatch = engine.repository.root / "00000000-0000-4000-8000-000000000000.json"
    mismatch.write_bytes(canonical_bytes(item.to_dict()))
    with pytest.raises(
        DecisionRecommendationError,
        match="DECISION_RECOMMENDATION_FILENAME_IDENTITY_MISMATCH",
    ):
        engine.repository.records()


def test_report_and_artifact_counter_tampering_is_rejected(tmp_path):
    from learning.decision_recommendation.models import (
        DecisionRecommendation,
        DecisionRecommendationReport,
    )

    report, _, engine = setup_engine(tmp_path)
    result = engine.run(report)
    item_values = result.recommendations[0].to_dict()
    item_values["recommendation_policy_digest"] = "0" * 64
    with pytest.raises(ValueError, match="INVALID_DECISION_RECOMMENDATION"):
        DecisionRecommendation(**item_values)
    values = result.identity_payload()
    values["recommendations"] = result.recommendations
    values["processed_count"] = 2
    with pytest.raises(ValueError, match="INVALID_RECOMMENDATION_REPORT"):
        DecisionRecommendationReport.create(**values)


def test_exact_empty_report_and_snapshot_fail_closed(tmp_path):
    from learning.decision_intelligence import (
        DecisionIntelligenceReport,
        DecisionIntelligenceRepository,
        DecisionIntelligenceSnapshot,
    )
    from learning.decision_intelligence.identity import digest as intelligence_digest

    _, populated, _ = setup_engine(tmp_path)
    template = populated.latest_snapshot()
    empty_repository = DecisionIntelligenceRepository(tmp_path / "empty_intelligence")
    values = template.identity_payload()
    values.update(
        intelligence_identities=(),
        record_count=0,
        repository_digest=intelligence_digest([]),
        previous_snapshot_uuid=None,
        previous_snapshot_digest=None,
    )
    empty_snapshot = DecisionIntelligenceSnapshot.create(**values)
    empty_repository.save_snapshot(empty_snapshot)
    engine = GovernedDecisionRecommendationEngine(
        empty_repository,
        DecisionRecommendationRepository(tmp_path / "empty_recommendations"),
    )
    with pytest.raises(
        DecisionRecommendationError, match="INVALID_DECISION_INTELLIGENCE"
    ):
        engine.run(empty_snapshot)
    empty_report = DecisionIntelligenceReport.create(
        decision_intelligences=(),
        processed_count=0,
        prepared_count=0,
        insufficient_count=0,
        rejected_count=0,
        duplicate_count=0,
        repository_digest=empty_snapshot.repository_digest,
        snapshot_uuid=empty_snapshot.snapshot_uuid,
        snapshot_digest=empty_snapshot.snapshot_digest,
        generated_at=empty_snapshot.generated_at,
        advisory_only=True,
    )
    with pytest.raises(
        DecisionRecommendationError, match="INVALID_DECISION_INTELLIGENCE"
    ):
        engine.run(empty_report)


def test_mixed_stored_recommendation_policy_partition_fails_closed(tmp_path):
    report, intelligence_repository, engine = setup_engine(tmp_path)
    engine.run(report)
    alternate = DecisionRecommendationPolicy(
        ready_quality_threshold=0.8,
        manual_review_quality_threshold=0.6,
    )
    second = GovernedDecisionRecommendationEngine(
        intelligence_repository,
        engine.repository,
        alternate,
    )
    with pytest.raises(DecisionRecommendationError, match="POLICY_MISMATCH"):
        second.run(report)


def test_artifact_rejects_policy_uuid_and_digest_tampering(tmp_path):
    from learning.decision_recommendation.models import DecisionRecommendation

    report, _, engine = setup_engine(tmp_path)
    values = engine.run(report).recommendations[0].to_dict()
    for field, invalid in (
        ("recommendation_policy_uuid", "00000000-0000-4000-8000-000000000000"),
        ("recommendation_policy_digest", "0" * 64),
        ("recommendation_policy_version", "PR185-RECOMMENDATION-POLICY.2.0"),
        ("recommendation_engine_version", "PR185.2.0"),
    ):
        changed = {**values, field: invalid}
        with pytest.raises(ValueError, match="INVALID_DECISION_RECOMMENDATION"):
            DecisionRecommendation(**changed)
