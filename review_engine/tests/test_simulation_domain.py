import json
from review_engine.simulation import (CounterfactualAnalyzer, HistoricalReplayEngine,
                                      ScenarioGenerator, SimulationCoordinator,
                                      ValidationReportBuilder, ValidationRepository)


def package():
    return {"schema_version": "7.0.0", "decision_id": "a" * 64, "evidence_lineage": {"evidence_ids": ["e2", "e1"]},
            "supporting_recommendations": [{"estimated_impact": {"historical_net_profit_delta": 3.0}}]}


def snapshots():
    return [{"snapshot_id": "b", "market_context": {"regime": "RANGE", "liquidity": "LOW_LIQUIDITY"}, "data_quality": {"completeness_ratio": 1.0}, "outcome": {"net_profit": -2, "profit_points": -4, "r_multiple": -1}},
            {"snapshot_id": "a", "market_context": {"market_mode": "TREND", "session": "VOLATILE"}, "data_quality": {"completeness_ratio": 1.0}, "outcome": {"net_profit": 5, "profit_points": 10, "r_multiple": 2}}]


def test_replay_is_deterministic_and_preserves_evidence_lineage():
    engine = HistoricalReplayEngine()
    assert engine.replay(package(), snapshots()) == engine.replay(package(), list(reversed(snapshots())))
    assert engine.replay(package(), snapshots())["evidence_lineage"]["evidence_ids"] == ["e1", "e2"]


def test_scenarios_cover_declared_historical_market_conditions():
    replay = HistoricalReplayEngine().replay(package(), snapshots())
    summary = ScenarioGenerator().generate(replay)
    assert {item["scenario_type"] for item in summary["scenarios"]} == {"TRENDING_MARKET", "RANGE_MARKET", "VOLATILE_SESSION", "LOW_LIQUIDITY"}
    assert summary["scenario_coverage"]["covered_observations"] == 2


def test_counterfactual_is_historical_and_consistent():
    replay = HistoricalReplayEngine().replay(package(), snapshots())
    analysis = CounterfactualAnalyzer().analyze(package(), replay, ScenarioGenerator().generate(replay))
    assert analysis["simulated_outcome"]["historical_net_profit"] == 6.0
    assert analysis["simulated_outcome"]["historical_net_profit_delta"] == 3.0
    assert "No live-market data" in analysis["assumptions"][-1]


def test_repository_is_immutable(tmp_path):
    report = {"decision_id": "a" * 64, "recommendation_quality": {"status": "SUPPORTED"}}
    repository = ValidationRepository(tmp_path)
    path = repository.save(report)
    repository.save(report | {"recommendation_quality": {"status": "CHANGED"}})
    assert json.loads(path.read_text())["validation_report"]["recommendation_quality"]["status"] == "SUPPORTED"


def test_validation_report_has_required_explainable_sections():
    replay = HistoricalReplayEngine().replay(package(), snapshots())
    scenarios = ScenarioGenerator().generate(replay)
    report = ValidationReportBuilder().build(replay, scenarios, CounterfactualAnalyzer().analyze(package(), replay, scenarios))
    assert {"scenario_coverage", "replay_consistency", "expected_impact", "observed_historical_outcome", "variance_summary", "recommendation_quality"} <= set(report)


def test_coordinator_outputs_all_v9_documents_and_async_regression(tmp_path):
    coordinator = SimulationCoordinator(tmp_path)
    path = coordinator.validate_async(package(), snapshots()).result()
    coordinator.shutdown()
    assert path.name == "validation_repository.json"
    assert len(list((tmp_path / "simulation" / "historical_replay").rglob("historical_replay.json"))) == 1
    assert len(list((tmp_path / "simulation" / "historical_replay").rglob("replay_summary.json"))) == 1
    assert len(list((tmp_path / "simulation" / "validation").rglob("scenario_summary.json"))) == 1
    assert len(list((tmp_path / "simulation" / "validation").rglob("validation_report.json"))) == 1
