"""Production initialization coverage for PR186 -> PR208."""

import os
from pathlib import Path
import sys

import pytest

sys.path.insert(0, str(Path(__file__).parents[1]))
sys.path.insert(1, str(Path(__file__).parent / "learning"))

from learning.execution_environment.policy import ENVIRONMENT_DIMENSIONS
from runtime.production_execution_initialization import (
    ProductionExecutionInitializationConfiguration,
    ProductionExecutionInitializationError,
    ProductionExecutionInitializer,
)
from test_pr185_decision_recommendation import setup_engine


GOOD = (0.99, 0.999, 0.9, 20.0, 100.0, 10.0, 0.9, 0.9, 2.0, 0.95)


def configured(root, recommendation, values=GOOD):
    return ProductionExecutionInitializationConfiguration(
        recommendation_uuid=recommendation.recommendation_uuid,
        observations=tuple(zip(ENVIRONMENT_DIMENSIONS, values)),
        captured_at=recommendation.created_at,
        recommendation_root=root / "decision_recommendation",
        readiness_root=root / "execution_readiness",
        environment_root=root / "execution_environment",
        feasibility_root=root / "execution_feasibility",
        package_root=root / "execution_package",
    )


def recommendation_at(root):
    intelligence_report, _, engine = setup_engine(root)
    return engine.run(intelligence_report).recommendations[0]


def test_initialization_runs_owned_engines_and_pr208_with_derived_ids(
    tmp_path, monkeypatch
):
    recommendation = recommendation_at(tmp_path)
    observed = []
    monkeypatch.delenv("RP_EXECUTION_PACKAGE_UUID", raising=False)

    result = ProductionExecutionInitializer(configured(tmp_path, recommendation)).start(
        lambda: observed.append(os.environ["RP_EXECUTION_PACKAGE_UUID"]) or "started"
    )

    assert result == "started"
    assert len(observed) == 1
    for directory in (
        "execution_readiness",
        "execution_environment",
        "execution_feasibility",
        "execution_package",
    ):
        records = tuple((tmp_path / directory).glob("*.json"))
        assert len(records) == 1
    assert observed[0] == next((tmp_path / "execution_package").glob("*.json")).stem
    assert len(tuple((tmp_path / "execution_environment" / "evidence").glob("*.json"))) == 1


def test_initialization_replay_is_idempotent(tmp_path, monkeypatch):
    recommendation = recommendation_at(tmp_path)
    initializer = ProductionExecutionInitializer(configured(tmp_path, recommendation))
    monkeypatch.delenv("RP_EXECUTION_PACKAGE_UUID", raising=False)

    initializer.start(lambda: None)
    before = {
        path: path.read_bytes()
        for path in tmp_path.glob("execution_*/**/*.json")
    }
    initializer.start(lambda: None)

    assert {path: path.read_bytes() for path in before} == before
    assert set(tmp_path.glob("execution_*/**/*.json")) == set(before)


def test_missing_recommendation_and_bad_environment_fail_before_runtime(tmp_path):
    recommendation = recommendation_at(tmp_path)
    started = []
    missing = configured(tmp_path, recommendation)
    object.__setattr__(missing, "recommendation_uuid", "00000000-0000-0000-0000-000000000000")
    with pytest.raises(ProductionExecutionInitializationError, match="RECOMMENDATION_MISSING"):
        ProductionExecutionInitializer(missing).start(lambda: started.append(True))

    weak = configured(
        tmp_path,
        recommendation,
        (0.0, 0.0, 0.0, 999.0, 999.0, 999.0, 0.0, 0.0, 999.0, 0.0),
    )
    with pytest.raises(ProductionExecutionInitializationError, match="ENVIRONMENT_NOT_READY"):
        ProductionExecutionInitializer(weak).start(lambda: started.append(True))
    assert started == []


@pytest.mark.parametrize(
    "changes,reason",
    [
        ({"recommendation_uuid": "not-a-uuid"}, "INVALID_RECOMMENDATION_UUID"),
        ({"observations": (("feed_stability", 1.0),)}, "INVALID_ENVIRONMENT_OBSERVATIONS"),
        ({"captured_at": ""}, "INVALID_CAPTURED_AT"),
    ],
)
def test_configuration_rejects_invalid_external_inputs(tmp_path, changes, reason):
    recommendation = recommendation_at(tmp_path)
    values = configured(tmp_path, recommendation).__dict__ | changes
    with pytest.raises(ProductionExecutionInitializationError, match=reason):
        ProductionExecutionInitializationConfiguration(**values)
