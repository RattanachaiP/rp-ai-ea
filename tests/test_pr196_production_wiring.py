"""PR196 production startup wiring integration tests."""
from pathlib import Path
import stat
from uuid import uuid4

import pytest

from runtime.executor_activation import RuntimeActivationState
from runtime.production_wiring import (
    ProductionExecutionWiring,
    ProductionPathConfiguration,
    ProductionWiringError,
)
from runtime.execution_context_consumer import ExecutionContextConsumer


def values(*, replay: str, engine: str = "V26.6.2A") -> dict[str, object]:
    return {
        "execution_uuid": str(uuid4()),
        "decision_uuid": str(uuid4()),
        "package_uuid": str(uuid4()),
        "replay_uuid": replay,
        "execution_confidence": 0.8,
        "readiness_state": "EXECUTION_READY_FOR_ENVIRONMENT_CHECK",
        "environment_state": "ENVIRONMENT_READY_FOR_FEASIBILITY",
        "feasibility_state": "EXECUTION_FEASIBLE",
        "policy_version": "policy-1",
        "engine_version": engine,
        "advisory_only": True,
    }


def configuration(tmp_path: Path) -> ProductionPathConfiguration:
    common = tmp_path / "Common" / "Files"
    common.mkdir(parents=True)
    return ProductionPathConfiguration(common)


def test_environment_configuration_owns_production_paths(tmp_path: Path) -> None:
    config = ProductionPathConfiguration.from_environment({
        "RP_MT5_COMMON_FILES": str(tmp_path / "Common" / "Files"),
        "RP_MT5_SYMBOL": "XAUUSD.a",
    })
    assert config.execution_context_path == (
        tmp_path / "Common" / "Files" / "RP_AI_EA" / "shared" /
        "XAUUSD.a" / "execution_context.json"
    )


def test_production_start_publishes_consumes_then_starts_existing_mt5(tmp_path: Path) -> None:
    config = configuration(tmp_path)
    replay = str(uuid4())
    calls: list[str] = []
    wiring = ProductionExecutionWiring(
        config,
        engine_version="V26.6.2A",
        replay_uuid=replay,
        runtime_state=lambda: RuntimeActivationState.READY,
        executor_start=lambda: calls.append("MT5_STARTED"),
    )

    result = wiring.start(values(replay=replay))

    assert calls == ["MT5_STARTED"]
    assert result.activation.authorized is True
    assert result.activation.execution_uuid == result.context.execution_uuid
    assert config.execution_context_path.read_bytes()
    assert config.execution_context_path.stat().st_mode & 0o222 == 0


@pytest.mark.parametrize("runtime_state", [RuntimeActivationState.NOT_READY, RuntimeActivationState.STOPPED])
def test_non_ready_runtime_never_starts_mt5(tmp_path: Path, runtime_state: RuntimeActivationState) -> None:
    config = configuration(tmp_path)
    replay = str(uuid4())
    calls: list[str] = []
    wiring = ProductionExecutionWiring(
        config, engine_version="V26.6.2A", replay_uuid=replay,
        runtime_state=lambda: runtime_state,
        executor_start=lambda: calls.append("MT5_STARTED"),
    )
    with pytest.raises(ProductionWiringError, match="INVALID_RUNTIME_STATE"):
        wiring.start(values(replay=replay))
    assert calls == []


def test_missing_common_files_fails_before_publication_or_executor_start(tmp_path: Path) -> None:
    config = ProductionPathConfiguration(tmp_path / "missing" / "Common" / "Files")
    replay = str(uuid4())
    calls: list[str] = []
    wiring = ProductionExecutionWiring(
        config, engine_version="V26.6.2A", replay_uuid=replay,
        runtime_state=lambda: RuntimeActivationState.READY,
        executor_start=lambda: calls.append("MT5_STARTED"),
    )
    with pytest.raises(ProductionWiringError, match="MT5_COMMON_FILES_NOT_FOUND"):
        wiring.start(values(replay=replay))
    assert calls == []
    assert not config.execution_context_path.exists()


def test_startup_is_one_shot_without_legacy_fallback(tmp_path: Path) -> None:
    config = configuration(tmp_path)
    replay = str(uuid4())
    wiring = ProductionExecutionWiring(
        config, engine_version="V26.6.2A", replay_uuid=replay,
        runtime_state=lambda: RuntimeActivationState.READY,
        executor_start=lambda: None,
    )
    wiring.start(values(replay=replay))
    with pytest.raises(ProductionWiringError, match="PRODUCTION_STARTUP_ALREADY_DECIDED"):
        wiring.start(values(replay=replay))


@pytest.mark.parametrize("failure", ["missing", "malformed"])
def test_publication_consumer_failure_never_starts_executor(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, failure: str
) -> None:
    config = configuration(tmp_path)
    replay = str(uuid4())
    calls: list[str] = []
    wiring = ProductionExecutionWiring(
        config, engine_version="V26.6.2A", replay_uuid=replay,
        runtime_state=lambda: RuntimeActivationState.READY,
        executor_start=lambda: calls.append("MT5_STARTED"),
    )

    original_load = ExecutionContextConsumer.load

    def reject(consumer: ExecutionContextConsumer) -> object:
        if failure == "missing":
            path = config.execution_context_path
            path.chmod(stat.S_IREAD | stat.S_IWRITE)
            path.unlink()
            assert not path.exists()
        else:
            config.execution_context_path.chmod(0o600)
            config.execution_context_path.write_text("not-json", encoding="utf-8")
        return original_load(consumer)

    monkeypatch.setattr("runtime.production_wiring.ExecutionContextConsumer.load", reject)
    with pytest.raises(ProductionWiringError, match="CONSUMER_VERIFICATION_FAILED"):
        wiring.start(values(replay=replay))
    assert calls == []


@pytest.mark.parametrize("mismatch", ["engine", "replay"])
def test_identity_mismatch_never_starts_executor(tmp_path: Path, mismatch: str) -> None:
    config = configuration(tmp_path)
    expected_replay = str(uuid4())
    published_replay = str(uuid4()) if mismatch == "replay" else expected_replay
    published_engine = "WRONG" if mismatch == "engine" else "V26.6.2A"
    calls: list[str] = []
    wiring = ProductionExecutionWiring(
        config, engine_version="V26.6.2A", replay_uuid=expected_replay,
        runtime_state=lambda: RuntimeActivationState.READY,
        executor_start=lambda: calls.append("MT5_STARTED"),
    )
    with pytest.raises(ProductionWiringError):
        wiring.start(values(replay=published_replay, engine=published_engine))
    assert calls == []


def test_executor_start_failure_is_rejected_without_retry(tmp_path: Path) -> None:
    config = configuration(tmp_path)
    replay = str(uuid4())
    attempts = 0

    def fail() -> None:
        nonlocal attempts
        attempts += 1
        raise RuntimeError("MT5 start failed")

    wiring = ProductionExecutionWiring(
        config, engine_version="V26.6.2A", replay_uuid=replay,
        runtime_state=lambda: RuntimeActivationState.READY, executor_start=fail,
    )
    with pytest.raises(ProductionWiringError, match="EXECUTOR_ACTIVATION_FAILED"):
        wiring.start(values(replay=replay))
    assert attempts == 1


def test_wiring_has_no_public_direct_executor_start_or_context_activation() -> None:
    public = {name for name in dir(ProductionExecutionWiring) if not name.startswith("_")}
    assert public == {"start"}
    assert "ExistingMt5Executor" not in __import__(
        "runtime.production_wiring", fromlist=["ExistingMt5Executor"]
    ).__dict__


def test_wiring_contains_no_legacy_or_execution_authority_dependency() -> None:
    source = (Path(__file__).parents[1] / "runtime" / "production_wiring.py").read_text(
        encoding="utf-8"
    ).lower()
    for forbidden in (
        "decision.json", "executionpackage", "ordersend", "broker_safety",
        "position_management", "take_profit", "trailing", "partial_close",
    ):
        assert forbidden not in source
