"""PR196 production wiring for the approved Runtime-to-MT5 lifecycle.

This module composes PR193 publication, PR194 consumption, and PR195
activation.  It deliberately contains no trading or Executor behaviour.
"""
from __future__ import annotations

from dataclasses import dataclass
import os
from pathlib import Path
import subprocess
from typing import Any, Callable, Mapping, Protocol

from runtime.execution_context_consumer import ExecutionContextConsumer
from runtime.execution_context_publication import ExecutionContextPublisher
from runtime.execution_contract import ExecutionContext
from runtime.executor_activation import (
    ActivationResult,
    GovernedExecutorActivator,
    RuntimeActivationState,
)


class ProductionWiringError(RuntimeError):
    """Fail-closed production configuration or startup failure."""


@dataclass(frozen=True, slots=True)
class ProductionPathConfiguration:
    """The two operator-owned paths needed by the production boundary."""

    common_files_root: Path
    terminal_executable: Path
    symbol: str = "XAUUSD"

    @classmethod
    def from_environment(cls, environment: Mapping[str, str] | None = None) -> "ProductionPathConfiguration":
        values = os.environ if environment is None else environment
        common = values.get("RP_MT5_COMMON_FILES", "").strip()
        terminal = values.get("RP_MT5_TERMINAL", "").strip()
        symbol = values.get("RP_MT5_SYMBOL", "XAUUSD").strip()
        if not common or not terminal or not symbol or Path(symbol).name != symbol:
            raise ProductionWiringError("INVALID_PRODUCTION_PATH_CONFIGURATION")
        return cls(Path(common), Path(terminal), symbol)

    @property
    def execution_context_path(self) -> Path:
        return self.common_files_root / "RP_AI_EA" / "shared" / self.symbol / "execution_context.json"

    def verify_mt5(self) -> None:
        """Detect the configured MT5 installation before contract publication."""
        if not self.common_files_root.is_dir():
            raise ProductionWiringError("MT5_COMMON_FILES_NOT_FOUND")
        if not self.terminal_executable.is_file():
            raise ProductionWiringError("MT5_TERMINAL_NOT_FOUND")


class ProcessStarter(Protocol):
    def __call__(self, command: tuple[str, ...]) -> object: ...


class ExistingMt5Executor:
    """Start the installed MT5 terminal; the installed EA remains the Executor."""

    def __init__(self, terminal_executable: Path, *, starter: ProcessStarter | None = None) -> None:
        self._terminal_executable = terminal_executable
        self._starter = starter or self._start_process

    @staticmethod
    def _start_process(command: tuple[str, ...]) -> subprocess.Popen[bytes]:
        return subprocess.Popen(command, close_fds=True)

    def start(self) -> None:
        # The terminal's production profile owns EA attachment.  No legacy
        # script, direct order call, or alternate activation flag is supplied.
        self._starter((str(self._terminal_executable),))


@dataclass(frozen=True, slots=True)
class ProductionStartupResult:
    context: ExecutionContext
    activation: ActivationResult


class ProductionExecutionWiring:
    """One production startup path through PR193 -> PR194 -> PR195."""

    def __init__(self, configuration: ProductionPathConfiguration, *,
                 engine_version: str, replay_uuid: str,
                 runtime_state: Callable[[], RuntimeActivationState],
                 executor_start: Callable[[], None] | None = None) -> None:
        self._configuration = configuration
        self._engine_version = engine_version
        self._replay_uuid = replay_uuid
        self._runtime_state = runtime_state
        self._executor_start = executor_start
        self._started = False

    def start(self, runtime_values: Mapping[str, Any]) -> ProductionStartupResult:
        """Publish once and activate only from the consumer's accepted file."""
        if self._started:
            raise ProductionWiringError("PRODUCTION_STARTUP_ALREADY_DECIDED")
        self._started = True
        self._configuration.verify_mt5()

        path = self._configuration.execution_context_path
        context = ExecutionContextPublisher(
            path, expected_engine_version=self._engine_version
        ).create_and_publish(runtime_values)
        consumer = ExecutionContextConsumer(
            path,
            expected_engine_version=self._engine_version,
            expected_replay_uuid=self._replay_uuid,
        )
        start_executor = self._executor_start or ExistingMt5Executor(
            self._configuration.terminal_executable
        ).start
        activation = GovernedExecutorActivator(
            start_executor, runtime_state=self._runtime_state
        ).activate_from(consumer)
        if not activation.authorized:
            raise ProductionWiringError(activation.reason or "EXECUTOR_ACTIVATION_REJECTED")
        if activation.execution_uuid != context.execution_uuid:
            raise ProductionWiringError("ACTIVATION_CONTEXT_MISMATCH")
        return ProductionStartupResult(context=context, activation=activation)
