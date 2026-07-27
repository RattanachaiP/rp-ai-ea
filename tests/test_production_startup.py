"""Canonical PR184 -> PR185 -> governed Runtime startup coverage."""

import os
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
