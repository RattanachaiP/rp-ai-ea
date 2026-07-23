import json

from review_engine.learning_intake import (DuplicatePreventionEngine, LearningIntakeCoordinator,
                                           LineageVerificationEngine, QualificationEngine)


def candidate(**overrides):
    value = {
        "governance": {"schema_version": "6.0.0", "overall_status": "HEALTHY", "report_id": "g1"},
        "executive_package": {"schema_version": "7.0.0", "decision_id": "d1", "executive_finalized": True},
        "simulation_report": {"schema_version": "9.0.0", "completed": True, "validation_successful": True},
        "lineage": {"evidence_ids": ["e2", "e1"], "knowledge_ids": ["k1"], "insight_ids": ["i1"],
                    "recommendation_ids": ["r1"], "governance_report_ids": ["g1"],
                    "executive_package_ids": ["d1"], "simulation_report_ids": ["s1"]},
    }
    value.update(overrides)
    return value


def test_qualification_is_deterministic_and_requires_rule_024_checks():
    engine = QualificationEngine()
    assert engine.qualify(candidate()) == engine.qualify(candidate())
    report = engine.qualify(candidate())
    assert report["qualification_state"] == "Qualified" and all(report["checks"].values())
    waiting = engine.qualify(candidate(executive_package={"schema_version": "7.0.0", "decision_id": "d1"}))
    assert waiting["qualification_state"] == "Waiting"


def test_lineage_verification_rejects_each_missing_required_reference():
    report = LineageVerificationEngine().verify(candidate()["lineage"] | {"insight_ids": []})
    assert not report["complete"] and report["status"] == "REJECTED"
    assert report["missing_lineage"] == ["insight_ids"]


def test_duplicate_identity_uses_lineage_hash_and_schema_version():
    verification = LineageVerificationEngine().verify(candidate()["lineage"])
    duplicate = DuplicatePreventionEngine()
    assert duplicate.identity(verification["lineage_hash"]) == duplicate.identity(verification["lineage_hash"])
    assert duplicate.identity(verification["lineage_hash"], "10.0.1") != duplicate.identity(verification["lineage_hash"])


def test_queue_is_append_only_and_preserves_all_queue_states(tmp_path):
    coordinator = LearningIntakeCoordinator(tmp_path)
    coordinator.intake(candidate())
    coordinator.intake(candidate(lineage=candidate()["lineage"] | {"knowledge_ids": []}))
    coordinator.intake(candidate(simulation_report={"schema_version": "10.0.0", "completed": True, "validation_successful": True}, lineage=candidate()["lineage"] | {"simulation_report_ids": ["s2"]}))
    coordinator.intake(candidate(executive_package={"schema_version": "7.0.0", "decision_id": "other"}, lineage=candidate()["lineage"] | {"executive_package_ids": ["other"]}))
    coordinator.shutdown()
    queue = json.loads((tmp_path / "learning_intake/candidate_queue/learning_candidate_queue.json").read_text())
    assert queue["append_only"] and {row["state"] for row in queue["candidates"]} == {"Qualified", "Rejected", "Deferred", "Waiting"}


def test_restart_recovery_does_not_duplicate_or_replace_candidate(tmp_path):
    first = LearningIntakeCoordinator(tmp_path); path = first.intake(candidate()); first.shutdown()
    original = path.read_bytes()
    second = LearningIntakeCoordinator(tmp_path); repeated = second.intake_async(candidate()).result(); second.shutdown()
    queue = json.loads((tmp_path / "learning_intake/candidate_queue/learning_candidate_queue.json").read_text())
    assert path == repeated and path.read_bytes() == original and queue["candidate_count"] == 1
    assert not list(tmp_path.rglob("*.tmp"))


def test_regression_does_not_write_outside_learning_intake(tmp_path):
    coordinator = LearningIntakeCoordinator(tmp_path)
    coordinator.intake(candidate())
    coordinator.shutdown()
    assert {path.name for path in tmp_path.iterdir()} == {"learning_intake"}
