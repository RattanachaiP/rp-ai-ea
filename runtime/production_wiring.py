"""PR196 production wiring for the approved Runtime-to-MT5 lifecycle.

This module composes PR193 publication, PR194 consumption, and PR195
activation.  It deliberately contains no trading or Executor behaviour.
"""
from __future__ import annotations

from dataclasses import dataclass
import os
from pathlib import Path
from typing import Any, Callable, Mapping

from runtime.execution_context_consumer import ExecutionContextConsumer
from runtime.execution_context_publication import ExecutionContextPublisher
from runtime.execution_context_publication import ExecutionContextPublicationError
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
    symbol: str = "XAUUSD"

    @classmethod
    def from_environment(cls, environment: Mapping[str, str] | None = None) -> "ProductionPathConfiguration":
        values = os.environ if environment is None else environment
        common = values.get("RP_MT5_COMMON_FILES", "").strip()
        symbol = values.get("RP_MT5_SYMBOL", "XAUUSD").strip()
        if not common or not symbol or Path(symbol).name != symbol:
            raise ProductionWiringError("INVALID_PRODUCTION_PATH_CONFIGURATION")
        return cls(Path(common), symbol)

    @property
    def execution_context_path(self) -> Path:
        return self.common_files_root / "RP_AI_EA" / "shared" / self.symbol / "execution_context.json"

    def verify(self) -> None:
        """Verify the actual MT5 FILE_COMMON root without inventing a terminal path."""
        if not self.common_files_root.is_dir():
            raise ProductionWiringError("MT5_COMMON_FILES_NOT_FOUND")


@dataclass(frozen=True, slots=True)
class ProductionStartupResult:
    context: ExecutionContext
    activation: ActivationResult


class ProductionExecutionWiring:
    """One production startup path through PR193 -> PR194 -> PR195."""

    def __init__(self, configuration: ProductionPathConfiguration, *,
                 engine_version: str, replay_uuid: str,
                 runtime_state: Callable[[], RuntimeActivationState],
                 executor_start: Callable[[], None]) -> None:
        if not callable(executor_start):
            raise ProductionWiringError("INVALID_EXECUTOR_START_CONFIGURATION")
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
        self._configuration.verify()

        path = self._configuration.execution_context_path
        try:
            context = ExecutionContextPublisher(
                path, expected_engine_version=self._engine_version
            ).create_and_publish(runtime_values)
        except ExecutionContextPublicationError as exc:
            raise ProductionWiringError("EXECUTION_CONTEXT_PUBLICATION_FAILED") from exc
        consumer = ExecutionContextConsumer(
            path,
            expected_engine_version=self._engine_version,
            expected_replay_uuid=self._replay_uuid,
        )
        activation = GovernedExecutorActivator(
            self._executor_start, runtime_state=self._runtime_state
        ).activate_from(consumer)
        if not activation.authorized:
            raise ProductionWiringError(activation.reason or "EXECUTOR_ACTIVATION_REJECTED")
        if activation.execution_uuid != context.execution_uuid:
            raise ProductionWiringError("ACTIVATION_CONTEXT_MISMATCH")
        return ProductionStartupResult(context=context, activation=activation)
