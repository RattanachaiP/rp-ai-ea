"""Canonical PR184 -> PR185 -> governed Runtime startup coverage."""

import os
import json
from math import inf, nan
from pathlib import Path
import sys

import pytest

sys.path.insert(0, str(Path(__file__).parents[1]))
sys.path.insert(1, str(Path(__file__).parent / "learning"))

from learning.execution_environment.policy import ENVIRONMENT_DIMENSIONS
from runtime.production_startup import (
    GovernedProductionStartup,
    ProductionStartupConfiguration,
    ProductionStartupError,
)
from test_pr184_decision_intelligence import setup_engine


GOOD = (0.99, 0.999, 0.9, 20.0, 100.0, 10.0, 0.9, 0.9, 2.0, 0.95)


def configured(root: Path):
    context_report, _, engine = setup_engine(root)
    intelligence = engine.run(context_report).decision_intelligences[0]
    return ProductionStartupConfiguration(
        decision_intelligence_uuid=intelligence.intelligence_uuid,
        observations=tuple(zip(ENVIRONMENT_DIMENSIONS, GOOD)),
        captured_at=intelligence.created_at,
        intelligence_root=root / "decision_intelligence",
        recommendation_root=root / "decision_recommendation",
        readiness_root=root / "execution_readiness",
        environment_root=root / "execution_environment",
        feasibility_root=root / "execution_feasibility",
        package_root=root / "execution_package",
    )


def test_clean_downstream_state_creates_pr185_and_starts_runtime_once(tmp_path, monkeypatch):
    config = configured(tmp_path)
    assert not config.recommendation_root.exists()
    calls = []
    monkeypatch.delenv("RP_EXECUTION_PACKAGE_UUID", raising=False)

    result = GovernedProductionStartup(config).start(
        lambda: calls.append(os.environ["RP_EXECUTION_PACKAGE_UUID"]) or "RUNNING"
    )

    assert result == "RUNNING"
    assert len(calls) == 1
    assert calls[0] == next(config.package_root.glob("*.json")).stem
    for root in (
        config.recommendation_root,
        config.readiness_root,
        config.environment_root,
        config.feasibility_root,
        config.package_root,
    ):
        record = next(root.glob("*.json"))
        assert record.stem in record.read_text()
    assert len(tuple((config.environment_root / "evidence").glob("*.json"))) == 1


def test_missing_malformed_and_duplicate_intelligence_fail_before_runtime(tmp_path, monkeypatch):
    config = configured(tmp_path)
    calls = []
    missing = ProductionStartupConfiguration(
        **(config.__dict__ | {"decision_intelligence_uuid": "00000000-0000-0000-0000-000000000000"})
    )
    with pytest.raises(ProductionStartupError, match="DECISION_INTELLIGENCE_MISSING"):
        GovernedProductionStartup(missing).start(lambda: calls.append(True))
    with pytest.raises(ProductionStartupError, match="INVALID_DECISION_INTELLIGENCE_UUID"):
        ProductionStartupConfiguration(**(config.__dict__ | {"decision_intelligence_uuid": "BAD"}))

    from learning.decision_intelligence import DecisionIntelligenceRepository

    original = DecisionIntelligenceRepository.records
    monkeypatch.setattr(
        DecisionIntelligenceRepository,
        "records",
        lambda repository: original(repository) + original(repository),
    )
    with pytest.raises(ProductionStartupError, match="DECISION_INTELLIGENCE_MISSING"):
        GovernedProductionStartup(config).start(lambda: calls.append(True))
    assert calls == []


def test_incomplete_chain_and_unauthorized_runtime_never_start(tmp_path, monkeypatch):
    config = configured(tmp_path)
    startup = GovernedProductionStartup(config)
    with pytest.raises(ProductionStartupError, match="UNAUTHORIZED_RUNTIME_TARGET"):
        startup.start(object())

    calls = []
    monkeypatch.setattr(
        "runtime.production_startup.ProductionExecutionInitializer.start",
        lambda initializer, runtime=None: (_ for _ in ()).throw(ValueError("PR208 failed")),
    )
    with pytest.raises(ProductionStartupError, match="PRODUCTION_STARTUP_REJECTED"):
        startup.start(lambda: calls.append(True))
    assert calls == []


@pytest.mark.parametrize(
    "observations",
    [
        tuple(zip(reversed(ENVIRONMENT_DIMENSIONS), GOOD)),
        tuple(zip(ENVIRONMENT_DIMENSIONS[:-1], GOOD[:-1])),
        tuple(zip(ENVIRONMENT_DIMENSIONS, (1,) + GOOD[1:])),
        tuple(zip(ENVIRONMENT_DIMENSIONS, (nan,) + GOOD[1:])),
        tuple(zip(ENVIRONMENT_DIMENSIONS, (inf,) + GOOD[1:])),
        tuple(zip(ENVIRONMENT_DIMENSIONS, (-0.1,) + GOOD[1:])),
    ],
)
def test_configuration_rejects_invalid_observation_contract(tmp_path, observations):
    config = configured(tmp_path)
    with pytest.raises(ProductionStartupError, match="INVALID_ENVIRONMENT_OBSERVATIONS"):
        ProductionStartupConfiguration(**(config.__dict__ | {"observations": observations}))


@pytest.mark.parametrize("captured_at", [None, "", "   ", 1])
def test_configuration_rejects_invalid_capture_timestamp(tmp_path, captured_at):
    config = configured(tmp_path)
    with pytest.raises(ProductionStartupError, match="INVALID_CAPTURED_AT"):
        ProductionStartupConfiguration(**(config.__dict__ | {"captured_at": captured_at}))


@pytest.mark.parametrize("root", ["learning_data", None, 1, object()])
def test_configuration_rejects_non_path_repository_roots(tmp_path, root):
    config = configured(tmp_path)
    with pytest.raises(ProductionStartupError, match="INVALID_REPOSITORY_ROOT"):
        ProductionStartupConfiguration(**(config.__dict__ | {"intelligence_root": root}))


def test_corrupt_pr184_record_and_snapshot_lineage_never_start_runtime(tmp_path):
    for corrupt_snapshot in (False, True):
        root = tmp_path / str(corrupt_snapshot)
        config = configured(root)
        calls = []
        repository_root = config.intelligence_root
        target = next(
            (repository_root / "snapshots").glob("*.json")
            if corrupt_snapshot
            else repository_root.glob("*.json")
        )
        data = json.loads(target.read_text())
        if corrupt_snapshot:
            data["repository_digest"] = "0" * 64
        else:
            data["intelligence_digest"] = "0" * 64
        target.write_text(json.dumps(data, sort_keys=True, separators=(",", ":")))
        with pytest.raises(ProductionStartupError):
            GovernedProductionStartup(config).start(lambda: calls.append(True))
        assert calls == []


@pytest.mark.parametrize("mode", ["not_ready", "missing", "duplicate"])
def test_invalid_recommendation_owner_output_never_starts_runtime(tmp_path, monkeypatch, mode):
    config = configured(tmp_path)
    calls = []
    from learning.decision_recommendation import GovernedDecisionRecommendationEngine

    original = GovernedDecisionRecommendationEngine.run

    def invalid(engine, source):
        report = original(engine, source)
        if mode == "not_ready":
            object.__setattr__(report.recommendations[0], "recommendation_state", "RECOMMENDATION_NOT_READY")
        elif mode == "missing":
            object.__setattr__(report.recommendations[0], "decision_intelligence_uuid", "00000000-0000-0000-0000-000000000000")
        else:
            object.__setattr__(report, "recommendations", report.recommendations * 2)
        return report

    monkeypatch.setattr(GovernedDecisionRecommendationEngine, "run", invalid)
    reason = "RECOMMENDATION_NOT_READY" if mode == "not_ready" else "RECOMMENDATION_MISSING"
    with pytest.raises(ProductionStartupError, match=reason):
        GovernedProductionStartup(config).start(lambda: calls.append(True))
    assert calls == []


def test_replay_is_idempotent_and_invokes_runtime_once_per_explicit_start(tmp_path, monkeypatch):
    config = configured(tmp_path)
    startup = GovernedProductionStartup(config)
    calls = []
    monkeypatch.delenv("RP_EXECUTION_PACKAGE_UUID", raising=False)
    startup.start(lambda: calls.append(os.environ["RP_EXECUTION_PACKAGE_UUID"]))
    before = {path: path.read_bytes() for path in tmp_path.glob("**/*.json")}
    startup.start(lambda: calls.append(os.environ["RP_EXECUTION_PACKAGE_UUID"]))
    assert {path: path.read_bytes() for path in before} == before
    assert set(tmp_path.glob("**/*.json")) == set(before)
    assert len(calls) == 2 and calls[0] == calls[1]
