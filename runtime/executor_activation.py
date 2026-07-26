"""PR195 fail-closed activation boundary for the existing MT5 Executor."""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Callable

from runtime.execution_context_consumer import ExecutionContextConsumer, ExecutionContextConsumptionError
from runtime.execution_contract import ExecutionContext, ExecutionContractError, serialize_execution_context


class RuntimeActivationState(str, Enum):
    """Runtime states visible to the activation boundary."""

    READY = "READY"
    NOT_READY = "NOT_READY"
    STOPPED = "STOPPED"


class ExecutorActivationState(str, Enum):
    """Complete lifecycle of one activator instance."""

    INACTIVE = "INACTIVE"
    ACTIVE = "ACTIVE"
    REJECTED = "REJECTED"


@dataclass(frozen=True, slots=True)
class ActivationResult:
    """Immutable, non-execution outcome of an activation attempt."""

    state: ExecutorActivationState
    authorized: bool
    execution_uuid: str | None
    reason: str | None


class GovernedExecutorActivator:
    """Authorize a one-shot start of an unchanged Executor implementation."""

    def __init__(self, activate_executor: Callable[[], None], *,
                 runtime_state: Callable[[], RuntimeActivationState]) -> None:
        if not callable(activate_executor) or not callable(runtime_state):
            raise ValueError("INVALID_ACTIVATION_CONFIGURATION")
        self._activate_executor = activate_executor
        self._runtime_state = runtime_state
        self._state = ExecutorActivationState.INACTIVE
        self._accepted_context: ExecutionContext | None = None

    @property
    def state(self) -> ExecutorActivationState:
        return self._state

    @property
    def accepted_context(self) -> ExecutionContext | None:
        """Expose only the exact immutable context accepted for activation."""
        return self._accepted_context

    def activate_from(self, consumer: ExecutionContextConsumer) -> ActivationResult:
        """Use the PR194 consumer as the sole production activation trigger."""
        if type(consumer) is not ExecutionContextConsumer:
            return self._reject("CONSUMER_VERIFICATION_FAILED")
        try:
            context = consumer.load()
        except ExecutionContextConsumptionError:
            return self._reject("CONSUMER_VERIFICATION_FAILED")
        return self.activate(context)

    def activate(self, context: ExecutionContext) -> ActivationResult:
        """Authorize activation only for a valid immutable accepted context."""
        if self._state is not ExecutorActivationState.INACTIVE:
            return ActivationResult(self._state, False, self._execution_uuid(), "ACTIVATION_ALREADY_DECIDED")
        if type(context) is not ExecutionContext:
            return self._reject("INVALID_EXECUTION_CONTEXT")
        try:
            # Revalidation prevents forged or mutated objects from becoming authority.
            serialize_execution_context(context)
        except ExecutionContractError:
            return self._reject("CONTRACT_VALIDATION_FAILED")
        try:
            runtime_state = self._runtime_state()
        except Exception:
            return self._reject("INVALID_RUNTIME_STATE")
        if runtime_state is not RuntimeActivationState.READY:
            return self._reject("INVALID_RUNTIME_STATE")

        self._accepted_context = context
        try:
            self._activate_executor()
        except Exception:
            self._accepted_context = None
            return self._reject("EXECUTOR_ACTIVATION_FAILED")
        self._state = ExecutorActivationState.ACTIVE
        return ActivationResult(self._state, True, context.execution_uuid, None)

    def _execution_uuid(self) -> str | None:
        return self._accepted_context.execution_uuid if self._accepted_context else None

    def _reject(self, reason: str) -> ActivationResult:
        self._state = ExecutorActivationState.REJECTED
        self._accepted_context = None
        return ActivationResult(self._state, False, None, reason)
