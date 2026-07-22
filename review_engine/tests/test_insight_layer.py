from datetime import datetime, timezone
import json, time
from review_engine.insights import InsightCoordinator, InsightEngine, InsightRepository
from review_engine.knowledge import PatternDiscoveryEngine

def clock(): return datetime(2026, 7, 22, 12, 0, tzinfo=timezone.utc)
def evidence(identifier, pattern, session, state, confidence, profit, rr):
    return {"evidence_id": identifier, "classification": pattern, "session": session, "market_state": state, "confidence": confidence, "win_loss": "WIN" if profit > 0 else "LOSS", "rr": rr, "statistics": {"net_profit": profit, "duration_seconds": 10, "mae_points": 2}}
def knowledge():
    return PatternDiscoveryEngine(clock=clock).generate([evidence("a", "TREND", "LONDON", "TREND", .85, 4, 2), evidence("b", "RANGE", "ASIA", "RANGE", .55, -2, -1), evidence("c", "TREND", "LONDON", "TREND", .85, 2, 1)])

def test_insight_generation_ranking_session_state_and_confidence():
    report = InsightEngine(clock=clock).generate(knowledge())
    assert report["summary"]["best_performing_pattern"] == "TREND"
    assert report["summary"]["worst_performing_pattern"] == "RANGE"
    assert report["summary"]["best_session"] == "LONDON"
    assert report["summary"]["best_market_state"] == "TREND"
    confidence = report["metrics"]["confidence_intelligence"]
    assert confidence["overconfident_regions"] == ["50-60%"]
    assert confidence["underconfident_regions"] == ["80-90%"]
    assert report["summary"]["highest_confidence_zone"] == "80-90%"

def test_repository_is_immutable_atomic_and_restart_safe(tmp_path):
    report = InsightEngine(clock=clock).generate(knowledge()); repo = InsightRepository(tmp_path)
    path = repo.save(report); original = path.read_text()
    assert repo.save({**report, "summary": {}}) == path
    assert path.read_text() == original and not list(tmp_path.rglob("*.tmp"))
    (tmp_path / "knowledge" / report["knowledge_version"]).mkdir(parents=True)
    (tmp_path / "knowledge" / report["knowledge_version"] / "knowledge.json").write_text(json.dumps(knowledge()))
    first = InsightCoordinator(tmp_path, engine=InsightEngine(clock=clock)); assert first.process_async().result(timeout=2); first.shutdown()
    restarted = InsightCoordinator(tmp_path, engine=InsightEngine(clock=clock)); assert restarted.process_available(); restarted.shutdown()

def test_insight_generation_performance_benchmark():
    records = [evidence(str(n), "TREND", "LONDON", "TREND", .8, 1, 1) for n in range(1000)]
    report = PatternDiscoveryEngine(clock=clock).generate(records)
    started = time.perf_counter(); InsightEngine(clock=clock).generate(report)
    assert time.perf_counter() - started < 1.0
