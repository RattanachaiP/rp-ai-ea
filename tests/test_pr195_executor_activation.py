"""PR195 governed Executor activation tests."""
from pathlib import Path

import pytest

from runtime.execution_context_consumer import ExecutionContextConsumer
from runtime.execution_contract import CONTRACT_VERSION, ExecutionContext, serialize_execution_context
from runtime.executor_activation import ExecutorActivationState, GovernedExecutorActivator, RuntimeActivationState

ENGINE = "V26.6.2A"
REPLAY = "44444444-4444-4444-8444-444444444444"


def context() -> ExecutionContext:
    return ExecutionContext.create(
        execution_uuid="11111111-1111-4111-8111-111111111111",
        decision_uuid="22222222-2222-4222-8222-222222222222",
        package_uuid="33333333-3333-4333-8333-333333333333",
        replay_uuid=REPLAY, execution_confidence=.75,
        readiness_state="EXECUTION_READY_FOR_ENVIRONMENT_CHECK",
        environment_state="ENVIRONMENT_READY_FOR_FEASIBILITY",
        feasibility_state="EXECUTION_FEASIBLE", policy_version="PR195-POLICY.1",
        engine_version=ENGINE, advisory_only=True,
        timestamp="2026-07-26T12:00:00Z", contract_version=CONTRACT_VERSION,
    )


def consumer(path: Path) -> ExecutionContextConsumer:
    return ExecutionContextConsumer(path, expected_engine_version=ENGINE, expected_replay_uuid=REPLAY)


def test_verified_context_is_the_only_activation_trigger(tmp_path: Path) -> None:
    path = tmp_path / "execution_context.json"; path.write_bytes(serialize_execution_context(context()))
    starts: list[str] = []
    activator = GovernedExecutorActivator(lambda: starts.append("started"), runtime_state=lambda: RuntimeActivationState.READY)
    result = activator.activate_from(consumer(path))
    assert result.authorized and result.state is ExecutorActivationState.ACTIVE
    assert result.execution_uuid == context().execution_uuid
    assert activator.accepted_context == context() and starts == ["started"]


@pytest.mark.parametrize("state", [RuntimeActivationState.NOT_READY, RuntimeActivationState.STOPPED, "READY"])
def test_invalid_runtime_state_fails_closed(state: object) -> None:
    starts: list[str] = []
    activator = GovernedExecutorActivator(lambda: starts.append("started"), runtime_state=lambda: state)  # type: ignore[arg-type]
    result = activator.activate(context())
    assert result.reason == "INVALID_RUNTIME_STATE" and result.state is ExecutorActivationState.REJECTED
    assert activator.accepted_context is None and not starts


def test_consumer_failure_and_unverified_input_fail_closed(tmp_path: Path) -> None:
    starts: list[str] = []
    activator = GovernedExecutorActivator(lambda: starts.append("started"), runtime_state=lambda: RuntimeActivationState.READY)
    assert activator.activate_from(consumer(tmp_path / "execution_context.json")).reason == "CONSUMER_VERIFICATION_FAILED"
    assert activator.state is ExecutorActivationState.REJECTED and not starts
    other = GovernedExecutorActivator(lambda: starts.append("started"), runtime_state=lambda: RuntimeActivationState.READY)
    assert other.activate(object()).reason == "INVALID_EXECUTION_CONTEXT"  # type: ignore[arg-type]
    assert not starts


def test_activation_is_one_shot_with_no_legacy_fallback() -> None:
    starts: list[str] = []
    activator = GovernedExecutorActivator(lambda: starts.append("started"), runtime_state=lambda: RuntimeActivationState.READY)
    assert activator.activate(context()).authorized
    second = activator.activate(context())
    assert not second.authorized and second.reason == "ACTIVATION_ALREADY_DECIDED" and starts == ["started"]


def test_executor_start_failure_rejects_and_clears_acceptance() -> None:
    def fail() -> None:
        raise RuntimeError("start failed")
    activator = GovernedExecutorActivator(fail, runtime_state=lambda: RuntimeActivationState.READY)
    result = activator.activate(context())
    assert result.reason == "EXECUTOR_ACTIVATION_FAILED"
    assert activator.state is ExecutorActivationState.REJECTED and activator.accepted_context is None


def test_existing_executor_engine_is_not_modified() -> None:
    source = (Path(__file__).parents[1] / "runtime/executor.py").read_text(encoding="utf-8")
    assert "ExecutionContext" not in source and "GovernedExecutorActivator" not in source
