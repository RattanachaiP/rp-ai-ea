import json
import pytest
from review_engine.learning_intake import (DuplicatePreventionEngine, LearningIntakeCoordinator,
                                          LearningIntakePolicy, LineageVerificationEngine, QualificationEngine)

def candidate(**overrides):
    value = {"governance": {"schema_version": "6.0.0", "status": "PASS", "report_id": "g1"}, "executive_package": {"schema_version": "7.0.0", "decision_id": "d1", "executive_finalized": True}, "simulation_report": {"schema_version": "9.0.0", "report_id": "v1", "completed": True, "validation_successful": True}, "lineage": {"evidence_ids": ["e2", "e1"], "knowledge_ids": ["k1"], "insight_ids": ["i1"], "recommendation_ids": ["r1"], "governance_report_ids": ["g1"], "executive_package_ids": ["d1"], "simulation_report_ids": ["v1"]}}
    value.update(overrides); return value

def test_qualification_is_deterministic_and_qualified():
    engine = QualificationEngine(); assert engine.qualify(candidate()) == engine.qualify(candidate())
    report = engine.qualify(candidate()); assert report["qualification_status"] == "QUALIFIED" and not report["failed_checks"]

def test_rejection_has_explicit_missing_lineage_reason():
    report = QualificationEngine().qualify(candidate(lineage=candidate()["lineage"] | {"insight_ids": []}))
    assert report["qualification_status"] == "REJECTED" and "LINEAGE_COMPLETE" in report["failed_checks"] and "insight_ids" in report["qualification_reasons"][0]

def test_deferral_schema_and_incomplete_simulation():
    assert QualificationEngine().qualify(candidate(executive_package={"schema_version":"7.0.0", "decision_id":"d1"}))["qualification_status"] == "DEFERRED"
    assert QualificationEngine().qualify(candidate(simulation_report={"schema_version":"99.0.0", "report_id":"v1", "completed":True, "validation_successful":True}))["qualification_status"] == "DEFERRED"

def test_policy_load_and_reject_unsupported(tmp_path):
    policy = LearningIntakePolicy.default(); assert policy.document["policy_version"] == "1.0.0"
    bad = tmp_path / "bad.json"; bad.write_text('{"policy_version":"2.0.0"}')
    with pytest.raises(ValueError): LearningIntakePolicy.load(bad)

def test_lineage_and_identity_are_stable():
    verification = LineageVerificationEngine().verify(candidate()["lineage"])
    assert verification["complete"]
    duplicate = DuplicatePreventionEngine()
    assert duplicate.identity("e", "v", verification["lineage_hash"], "1.0.0", "10.0.0") == duplicate.identity("e", "v", verification["lineage_hash"], "1.0.0", "10.0.0")

def test_registry_reports_duplicate_and_is_immutable(tmp_path):
    c = LearningIntakeCoordinator(tmp_path); first = c.intake(candidate()); original = first.read_bytes(); second = c.intake(candidate()); c.shutdown()
    registry = json.loads((tmp_path / "learning_intake/candidate_registry/learning_candidate_registry.json").read_text())
    report = json.loads((tmp_path / "learning_intake/qualification" / json.loads(original)["candidate_id"] / "learning_intake_report.json").read_text())
    assert first == second and first.read_bytes() == original and registry["candidate_count"] == 1 and report["duplicate_status"] == "NOT_DUPLICATE"

def test_intake_report_complete_atomic_and_restart_recovery(tmp_path):
    c = LearningIntakeCoordinator(tmp_path); path = c.intake(candidate()); c.shutdown()
    report = json.loads((tmp_path / "learning_intake/qualification" / json.loads(path.read_text())["candidate_id"] / "learning_intake_report.json").read_text())
    required = {"report_id", "candidate_id", "qualification_status", "qualification_reasons", "failed_checks", "passed_checks", "governance_status", "validation_status", "lineage_status", "schema_compatibility", "duplicate_status", "policy_version", "created_at", "producer", "baseline_commit", "schema_version"}
    assert required <= report.keys() and not list(tmp_path.rglob("*.tmp"))
    c = LearningIntakeCoordinator(tmp_path); assert c.intake_async(candidate()).result() == path; c.shutdown()

def test_corrupted_record_is_ignored_when_rebuilding_registry(tmp_path):
    c = LearningIntakeCoordinator(tmp_path); c.intake(candidate()); c.shutdown()
    corrupt = tmp_path / "learning_intake/candidate_registry/records/bad/learning_candidate.json"; corrupt.parent.mkdir(parents=True); corrupt.write_text("{")
    c = LearningIntakeCoordinator(tmp_path); c.intake(candidate(lineage=candidate()["lineage"] | {"evidence_ids":["new"]})); c.shutdown()
    assert not list(tmp_path.rglob("*.tmp"))
