from datetime import datetime, timezone
import json
from review_engine.executive import (ConflictAnalysisEngine, DecisionCandidateAggregator, DecisionPrioritizationEngine,
                                     ExecutiveCoordinator, ExecutiveRepository)


def clock(): return datetime(2026, 7, 23, 12, 0, tzinfo=timezone.utc)
def recommendation(identifier, category="ENTRY_QUALITY", priority="HIGH", summary="Reduce entry risk"):
    return {"recommendation_id": identifier, "category": category, "priority": priority, "summary": summary,
            "validation_status": "VALID", "supporting_insights": ["i1"], "supporting_knowledge": ["k1"],
            "supporting_evidence": ["e1", "e2"], "supporting_snapshots": ["s1"],
            "estimated_impact": {"scope": "HISTORICAL_ANALYTICAL_ESTIMATE_ONLY"}}
def write(path, value): path.parent.mkdir(parents=True, exist_ok=True); path.write_text(json.dumps(value))
def setup(root, rows):
    write(root / "recommendations" / "r" / "recommendation_repository.json", {"recommendations": rows})
    write(root / "governance" / "health" / "governance_report.json", {"overall_status": "HEALTHY", "report_id": "g1"})


def test_decision_aggregation_produces_one_candidate_per_business_issue():
    rows = [recommendation("a" * 64), recommendation("b" * 64)]
    candidates = DecisionCandidateAggregator().aggregate(rows)
    assert len(candidates) == 1 and len(candidates[0]["recommendations"]) == 2 and len(candidates[0]["decision_id"]) == 64


def test_conflict_detection_reports_without_resolving():
    candidate = DecisionCandidateAggregator().aggregate([recommendation("a" * 64, summary="Increase coverage"), recommendation("b" * 64, summary="Reduce coverage")])[0]
    report = ConflictAnalysisEngine().analyse(candidate)
    assert report["status"] == "CONFLICT" and report["conflicts"][0]["reason"] == "OPPOSING_ADVISORY_ACTION"


def test_priority_ranking_is_deterministic_and_governance_aware():
    candidate = DecisionCandidateAggregator().aggregate([recommendation("a" * 64, priority="HIGH")])[0]
    engine = DecisionPrioritizationEngine()
    assert engine.rank(candidate, True)["score"] == engine.rank(candidate, True)["score"]
    assert engine.rank(candidate, True)["score"] > engine.rank(candidate, False)["score"]


def test_repository_is_immutable_and_atomic(tmp_path):
    package = {"decision_id": "a" * 64, "created_at": "2026-07-23T12:00:00.000Z", "schema_version": "7.0.0"}
    repository = ExecutiveRepository(tmp_path); path = repository.save(package)
    repository.save(package | {"schema_version": "changed"})
    assert json.loads(path.read_text())["schema_version"] == "7.0.0" and not list(tmp_path.rglob("*.tmp"))


def test_readiness_package_lineage_and_restart_recovery(tmp_path):
    setup(tmp_path, [recommendation("a" * 64, priority="CRITICAL")])
    coordinator = ExecutiveCoordinator(tmp_path, clock=clock)
    first = coordinator.process_available(); second = coordinator.process_available(); coordinator.shutdown()
    decision_id = json.loads(first[0].read_text())["decision_id"]
    package = json.loads((tmp_path / "executive" / "decision_packages" / decision_id / "executive_decision_package.json").read_text())
    readiness = json.loads((tmp_path / "executive" / "readiness" / "executive_readiness.json").read_text())
    assert first == second and package["governance_status"]["approved"] and package["evidence_lineage"]["evidence_ids"] == ["e1", "e2"]
    assert readiness["pending_decisions"] == 1 and readiness["high_priority_decisions"] == 1 and not list(tmp_path.rglob("*.tmp"))


def test_governance_failure_blocks_but_does_not_modify_recommendations(tmp_path):
    rows = [recommendation("a" * 64)]; setup(tmp_path, rows)
    write(tmp_path / "governance" / "health" / "governance_report.json", {"overall_status": "UNHEALTHY"})
    coordinator = ExecutiveCoordinator(tmp_path, clock=clock); paths = coordinator.process_available(); coordinator.shutdown()
    package = json.loads(paths[0].read_text())
    assert package["risk_summary"]["blocked"] and json.loads((tmp_path / "recommendations" / "r" / "recommendation_repository.json").read_text())["recommendations"] == rows
