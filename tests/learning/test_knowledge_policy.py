from dataclasses import replace
import json
from pathlib import Path
from uuid import UUID

import pytest

from learning.knowledge import Knowledge
from learning.policy import KnowledgePolicyEngine, PolicyConfig, PolicyEvaluationRepository

BASELINE = "7873fd52266e72e2bf849126359989ff45df76aa"


def knowledge(**values):
    base = Knowledge("k1", 1, "p", "v", "2026-07-24T00:00:00Z", ("X",), ("S",), ("M",), 40, .6, 1.5, None, schema_version="1.0")
    return replace(base, **values)


def inputs(**analytics):
    return dict(
        governance={"production_eligible": True, "current_lifecycle_state": "VERIFIED"},
        lifecycle_state="VERIFIED",
        analytics={"significance": .96, "stability_classification": "STABLE", "conflict_severity": "LOW", "timestamp": "2026-07-24T00:00:00Z", **analytics},
        evaluation_timestamp="2026-07-24T01:00:00Z",
    )


def engine(config=None):
    return KnowledgePolicyEngine(config, source_baseline=BASELINE)


def test_thresholds_and_deterministic_replay():
    evaluator = engine()
    first = evaluator.evaluate(knowledge(), **inputs())
    second = evaluator.evaluate(knowledge(), **inputs())
    assert first.eligible
    assert first.to_dict() == second.to_dict()
    UUID(first.evaluation_uuid)
    assert not evaluator.evaluate(knowledge(sample_count=29), **inputs()).eligible
    assert not evaluator.evaluate(knowledge(average_rr=.9), **inputs()).eligible
    assert not evaluator.evaluate(knowledge(verified_win_rate=.4), **inputs()).eligible


def test_fail_closed_evidence_lifecycle_schema_and_freshness():
    evaluator = engine()
    assert not evaluator.evaluate(knowledge(), **{**inputs(), "lifecycle_state": "ACTIVE"}).eligible
    assert not evaluator.evaluate(knowledge(), **inputs(conflict_severity="HIGH")).eligible
    assert not evaluator.evaluate(knowledge(schema_version="2.0"), **inputs()).eligible
    stale = evaluator.evaluate(knowledge(), **inputs(timestamp="2026-07-22T00:00:00Z"))
    assert not stale.eligible
    assert not stale.warnings
    assert not evaluator.evaluate(knowledge(), **inputs(timestamp="2026-07-24T02:00:00Z")).eligible
    missing_conflict = inputs()
    del missing_conflict["analytics"]["conflict_severity"]
    assert not evaluator.evaluate(knowledge(), **missing_conflict).eligible
    missing_governance = inputs()
    missing_governance["governance"] = {"current_lifecycle_state": "VERIFIED"}
    assert not evaluator.evaluate(knowledge(), **missing_governance).eligible


def test_baseline_and_timestamp_validation():
    for invalid in (None, "", "UNKNOWN", "base"):
        with pytest.raises(ValueError, match="INVALID_SOURCE_BASELINE"):
            KnowledgePolicyEngine(source_baseline=invalid)
    with pytest.raises(ValueError, match="INVALID_EVALUATION_TIMESTAMP"):
        engine().evaluate(knowledge(), **{**inputs(), "evaluation_timestamp": "2026-07-24T01:00:00"})
    bad_analytics = inputs(timestamp="not-a-time")
    with pytest.raises(ValueError, match="INVALID_ANALYTICS_TIMESTAMP"):
        engine().evaluate(knowledge(), **bad_analytics)


def test_immutable_repository_and_integrity_validation(tmp_path):
    first = engine().evaluate(knowledge(), **inputs())
    repo = PolicyEvaluationRepository(tmp_path)
    assert repo.save(first) == repo.save(first)
    with pytest.raises(FileExistsError):
        repo.storage.write(replace(first, score=0))
    assert repo.history("k1") == (first,)
    path = repo.storage.path_for(first.evaluation_uuid)
    payload = json.loads(path.read_text(encoding="utf-8"))
    payload["evaluation_uuid"] = "00000000-0000-4000-8000-000000000001"
    path.write_text(json.dumps(payload), encoding="utf-8")
    with pytest.raises(ValueError, match="INVALID_POLICY_EVALUATION_RECORD"):
        repo.history()


def test_versioned_configuration():
    report = engine(PolicyConfig(version="2.0", minimum_sample_count=50)).evaluate(knowledge(sample_count=50), **inputs())
    assert report.policy_version == "2.0"


def test_policy_layer_has_no_runtime_authority_dependencies():
    source = "\n".join(path.read_text(encoding="utf-8") for path in Path("learning/policy").glob("*.py"))
    for forbidden in ("runtime", "bridge", "broker", "decision_engine", "executor"):
        assert forbidden not in source.lower()
