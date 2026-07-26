"""PR196 production startup wiring integration tests."""
from pathlib import Path
from uuid import uuid4

import pytest

from runtime.executor_activation import RuntimeActivationState
from runtime.production_wiring import (
    ProductionExecutionWiring,
    ProductionPathConfiguration,
    ProductionWiringError,
)


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
    terminal = tmp_path / "terminal64.exe"
    terminal.touch()
    return ProductionPathConfiguration(common, terminal)


def test_environment_configuration_owns_production_paths(tmp_path: Path) -> None:
    config = ProductionPathConfiguration.from_environment({
        "RP_MT5_COMMON_FILES": str(tmp_path / "Common" / "Files"),
        "RP_MT5_TERMINAL": str(tmp_path / "terminal64.exe"),
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


def test_missing_mt5_fails_before_publication_or_executor_start(tmp_path: Path) -> None:
    common = tmp_path / "Common" / "Files"
    common.mkdir(parents=True)
    config = ProductionPathConfiguration(common, tmp_path / "missing-terminal64.exe")
    replay = str(uuid4())
    calls: list[str] = []
    wiring = ProductionExecutionWiring(
        config, engine_version="V26.6.2A", replay_uuid=replay,
        runtime_state=lambda: RuntimeActivationState.READY,
        executor_start=lambda: calls.append("MT5_STARTED"),
    )
    with pytest.raises(ProductionWiringError, match="MT5_TERMINAL_NOT_FOUND"):
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
