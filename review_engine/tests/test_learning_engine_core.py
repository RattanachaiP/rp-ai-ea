import json
from datetime import datetime, timezone

import pytest

from review_engine.learning_engine import LearningEngineCoordinator, LearningEnginePolicy, LearningMaterializationEngine


def candidate(**overrides):
    value = {"candidate_id": "candidate-1", "candidate_hash": "candidate-hash", "qualification_status": "QUALIFIED",
             "qualification_report_id": "qualification-1", "validation_report_id": "validation-1", "evidence_hash": "evidence-hash",
             "lineage_hash": "lineage-hash", "policy_version": "1.0.0", "schema_version": "10.0.0"}
    value.update(overrides)
    return value


def test_materialization_is_deterministic_and_has_no_training_or_runtime_effect():
    engine = LearningMaterializationEngine()
    assert engine.materialize(candidate()) == engine.materialize(candidate())
    material = engine.materialize(candidate())
    assert material["materialization_status"] == "MATERIALIZED"
    assert material["training_performed"] is False and material["runtime_mutation_performed"] is False


def test_unqualified_or_incomplete_candidate_is_rejected():
    assert LearningMaterializationEngine().materialize(candidate(qualification_status="DEFERRED"))["materialization_status"] == "REJECTED"
    assert LearningMaterializationEngine().materialize(candidate(evidence_hash=None))["materialization_status"] == "REJECTED"
    assert LearningMaterializationEngine().materialize({"candidate_id": "incomplete"})["rejection_reasons"]


def test_policy_rejects_training_or_runtime_mutation():
    policy = dict(LearningEnginePolicy.default().document)
    policy["training_permitted"] = True
    with pytest.raises(ValueError):
        LearningEnginePolicy(policy)


def test_registry_materialization_is_immutable_and_async(tmp_path):
    registry = tmp_path / "learning_intake/candidate_registry/learning_candidate_registry.json"
    registry.parent.mkdir(parents=True)
    registry.write_text(json.dumps({"schema_version": "10.0.0", "document_type": "learning_candidate_registry", "candidates": [candidate()]}))
    fixed_time = lambda: datetime(2026, 7, 23, tzinfo=timezone.utc)
    coordinator = LearningEngineCoordinator(tmp_path, clock=fixed_time)
    paths = coordinator.materialize_registry_async().result()
    original = paths[0].read_bytes()
    assert coordinator.materialize_registry()[0] == paths[0]
    coordinator.shutdown()
    assert paths[0].read_bytes() == original and not list(tmp_path.rglob("*.tmp"))


def test_invalid_registry_fails_closed(tmp_path):
    with pytest.raises(ValueError):
        LearningEngineCoordinator(tmp_path).materialize_registry()
