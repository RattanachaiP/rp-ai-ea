from datetime import datetime, timezone
import json
import time

from review_engine.knowledge import KnowledgeCoordinator, PatternDiscoveryEngine, PatternRepository


def clock():
    return datetime(2026, 7, 22, 12, 0, tzinfo=timezone.utc)


def evidence(identifier, classification, session, state, confidence, profit, rr, duration=10, drawdown=2):
    return {"schema_version": "2.0.0", "evidence_id": identifier, "classification": classification,
            "win_loss": "WIN" if profit > 0 else "LOSS", "market_state": state, "session": session,
            "confidence": confidence, "rr": rr,
            "statistics": {"net_profit": profit, "duration_seconds": duration, "mae_points": drawdown}}


def test_pattern_aggregation_is_deterministic_and_complete():
    engine = PatternDiscoveryEngine(clock=clock)
    report = engine.generate([evidence("b", "TREND", "LONDON", "TREND", .85, -2, -1), evidence("a", "TREND", "LONDON", "TREND", .75, 4, 2, 20)])
    trend = report["statistics"]["pattern_statistics"]["TREND"]
    assert trend == {"trade_count": 2, "win_rate": .5, "average_rr": .5, "loss_rate": .5, "average_profit": 4.0, "average_loss": -2.0, "average_duration": 15.0, "average_confidence": .8}
    assert set(report["statistics"]["pattern_statistics"]) == {"TREND", "RANGE", "BREAKOUT", "PULLBACK", "CONTINUATION", "REVERSAL", "NEWS", "UNKNOWN"}
    assert report["pattern_repository_version"] == engine.generate(list(reversed([evidence("b", "TREND", "LONDON", "TREND", .85, -2, -1), evidence("a", "TREND", "LONDON", "TREND", .75, 4, 2, 20)])))["pattern_repository_version"]


def test_session_and_market_state_aggregation():
    report = PatternDiscoveryEngine(clock=clock).generate([evidence("a", "TREND", "ASIA", "TREND", .8, 3, 1.5, drawdown=4), evidence("b", "RANGE", "ASIA", "TREND", .8, -1, -.5, drawdown=2)])
    assert report["statistics"]["session_statistics"]["ASIA"] == {"trade_count": 2, "win_rate": .5, "average_rr": .5, "profit_factor": 3.0, "average_duration": 10.0, "average_drawdown": 3.0}
    assert report["statistics"]["market_state_statistics"]["TREND"] == {"win_rate": .5, "average_rr": .5, "confidence_distribution": {"80-90%": 2}}


def test_confidence_calibration():
    report = PatternDiscoveryEngine(clock=clock).generate([evidence("a", "TREND", "ASIA", "TREND", .55, 1, 1), evidence("b", "TREND", "ASIA", "TREND", .65, -1, -1)])
    calibration = report["statistics"]["confidence_calibration"]
    assert calibration["50-60%"] == {"sample_size": 1, "actual_win_rate": 1.0, "average_rr": 1.0}
    assert calibration["60-70%"] == {"sample_size": 1, "actual_win_rate": 0.0, "average_rr": -1.0}


def test_repository_is_append_only_and_atomic(tmp_path):
    engine = PatternDiscoveryEngine(clock=clock)
    repository = PatternRepository(tmp_path)
    first = repository.save(engine.generate([evidence("a", "TREND", "ASIA", "TREND", .8, 1, 1)]))
    second = repository.save(engine.generate([evidence("a", "TREND", "ASIA", "TREND", .8, 1, 1), evidence("b", "RANGE", "LONDON", "RANGE", .8, -1, -1)]))
    assert first != second and first.exists() and second.exists()
    original = first.read_text()
    assert repository.save(json.loads(second.read_text()) | {"pattern_repository_version": first.parent.name}) == first
    assert first.read_text() == original and not list(tmp_path.rglob("*.tmp"))


def test_restart_recovery_and_asynchronous_processing(tmp_path):
    evidence_dir = tmp_path / "evidence"; evidence_dir.mkdir()
    (evidence_dir / "evidence_a.json").write_text(json.dumps(evidence("a", "TREND", "ASIA", "TREND", .8, 1, 1)))
    first = KnowledgeCoordinator(tmp_path, engine=PatternDiscoveryEngine(clock=clock)); path = first.process_async().result(timeout=2); first.shutdown()
    restarted = KnowledgeCoordinator(tmp_path, engine=PatternDiscoveryEngine(clock=clock)); assert restarted.process_available() == path; restarted.shutdown()


def test_pattern_generation_performance_benchmark():
    engine = PatternDiscoveryEngine(clock=clock)
    records = [evidence(str(index), "TREND", "LONDON", "TREND", .8, 1, 1) for index in range(1000)]
    started = time.perf_counter(); engine.generate(records)
    assert time.perf_counter() - started < 1.0
