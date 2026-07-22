from datetime import datetime, timezone
import json, time
import pytest
from review_engine.insights import InsightEngine
from review_engine.knowledge import PatternDiscoveryEngine
from review_engine.recommendations import RecommendationCoordinator, RecommendationEngine, RecommendationRepository, RecommendationValidator

def clock(): return datetime(2026, 7, 22, 12, 0, tzinfo=timezone.utc)
def evidence(identifier, profit, snapshot):
    return {"evidence_id": identifier, "snapshot_id": snapshot, "classification": "TREND", "session": "LONDON", "market_state": "TREND", "confidence": .85, "win_loss": "WIN" if profit > 0 else "LOSS", "rr": 1, "statistics": {"net_profit": profit}}
def insight():
    knowledge = PatternDiscoveryEngine(clock=clock).generate([evidence("e1", 2, "s1"), evidence("e2", -1, "s2"), evidence("e3", 1, "s3")])
    return InsightEngine(clock=clock).generate(knowledge)

def test_recommendation_generation_priority_lineage_and_impact_are_deterministic():
    report = RecommendationEngine(clock=clock).generate(insight())
    again = RecommendationEngine(clock=clock).generate(insight())
    assert report == again and report["recommendations"]
    for row in report["recommendations"]:
        assert row["priority"] in {"CRITICAL", "HIGH", "MEDIUM", "LOW", "INFORMATION"}
        assert row["supporting_insights"] and row["supporting_knowledge"] and row["supporting_evidence"] and row["supporting_snapshots"]
        assert row["estimated_impact"]["not_guaranteed_future_performance"] is True

def test_generator_aggregates_multiple_insights_and_their_lineage():
    first, second = insight(), insight()
    second = {**second, "insight_version": "f" * 64}
    report = RecommendationEngine(clock=clock).generate([first, second])
    assert len(report["recommendations"][0]["supporting_insights"]) == 2

def test_validation_rejects_incomplete_lineage_and_duplicates():
    package = RecommendationEngine(clock=clock).generate(insight()); validator = RecommendationValidator()
    assert validator.validate(package)[0]
    broken = {**package, "recommendations": [{**package["recommendations"][0], "supporting_snapshots": []}]}
    assert "LINEAGE_INCOMPLETE" in validator.validate(broken)[1]
    assert "DUPLICATE_RECOMMENDATION" in validator.validate(package, {package["recommendations"][0]["recommendation_id"]})[1]

def test_repository_immutable_atomic_auditable_and_restart_safe(tmp_path):
    report = RecommendationEngine(clock=clock).generate(insight()); repo = RecommendationRepository(tmp_path); valid, errors = RecommendationValidator().validate(report)
    assert valid, errors
    path = repo.save(report, {"validation_status": "VALID", "errors": []}); original = path.read_text()
    assert repo.save(report, {"validation_status": "VALID", "errors": []}) == path
    assert path.read_text() == original and not list(tmp_path.rglob("*.tmp"))
    audit = json.loads((tmp_path / "audit" / report["recommendation_version"] / "recommendation_audit.json").read_text())
    assert [event["event"] for event in audit["events"]] == ["creation", "lineage_verification", "validation", "publication"]
    insight_path = tmp_path / "insights" / insight()["insight_version"] / "insight_repository.json"; insight_path.parent.mkdir(parents=True); insight_path.write_text(json.dumps(insight()))
    first = RecommendationCoordinator(tmp_path, engine=RecommendationEngine(clock=clock)); assert first.process_async().result(timeout=2); first.shutdown()
    restarted = RecommendationCoordinator(tmp_path, engine=RecommendationEngine(clock=clock)); assert restarted.process_available(); restarted.shutdown()

def test_recommendation_generation_performance_benchmark():
    report = insight(); started = time.perf_counter(); RecommendationEngine(clock=clock).generate(report)
    assert time.perf_counter() - started < 1.0

def test_generation_fails_safely_without_complete_evidence_chain():
    invalid = insight(); invalid["lineage"]["evidence"][0]["snapshot_id"] = ""
    with pytest.raises(ValueError, match="LINEAGE_INCOMPLETE"): RecommendationEngine(clock=clock).generate(invalid)
