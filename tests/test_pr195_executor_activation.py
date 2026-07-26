"""PR195 governed Executor activation tests."""
from datetime import datetime, timezone
from pathlib import Path

import pytest

from runtime.execution_context_consumer import ExecutionContextConsumer
from runtime.execution_context_publication import ExecutionContextPublisher
from runtime.execution_contract import CONTRACT_VERSION, ExecutionContext
from runtime.executor_activation import ExecutorActivationState, GovernedExecutorActivator, RuntimeActivationState

ENGINE = "V26.6.2A"
REPLAY = "44444444-4444-4444-8444-444444444444"


def values(*, engine: str = ENGINE, replay: str = REPLAY) -> dict[str, object]:
    return {
        "execution_uuid": "11111111-1111-4111-8111-111111111111",
        "decision_uuid": "22222222-2222-4222-8222-222222222222",
        "package_uuid": "33333333-3333-4333-8333-333333333333",
        "replay_uuid": replay, "execution_confidence": .75,
        "readiness_state": "EXECUTION_READY_FOR_ENVIRONMENT_CHECK",
        "environment_state": "ENVIRONMENT_READY_FOR_FEASIBILITY",
        "feasibility_state": "EXECUTION_FEASIBLE", "policy_version": "PR195-POLICY.1",
        "engine_version": engine, "advisory_only": True,
    }


def publish(path: Path, *, engine: str = ENGINE, replay: str = REPLAY) -> ExecutionContext:
    publisher = ExecutionContextPublisher(
        path, expected_engine_version=engine,
        clock=lambda: datetime(2026, 7, 26, 12, tzinfo=timezone.utc),
    )
    return publisher.create_and_publish(values(engine=engine, replay=replay))


def consumer(path: Path, *, engine: str = ENGINE, replay: str = REPLAY) -> ExecutionContextConsumer:
    return ExecutionContextConsumer(path, expected_engine_version=engine, expected_replay_uuid=replay)


def activator(starts: list[str], state: object = RuntimeActivationState.READY) -> GovernedExecutorActivator:
    return GovernedExecutorActivator(
        lambda: starts.append("started"), runtime_state=lambda: state  # type: ignore[arg-type]
    )


def test_pr193_to_pr195_end_to_end_activates_exactly_once(tmp_path: Path) -> None:
    path = tmp_path / "execution_context.json"
    published = publish(path)
    starts: list[str] = []
    instance = activator(starts)

    result = instance.activate_from(consumer(path))
    assert result.authorized and result.state is ExecutorActivationState.ACTIVE
    assert result.execution_uuid == published.execution_uuid
    assert instance.accepted_context == published and starts == ["started"]

    repeated = instance.activate_from(consumer(path))
    assert not repeated.authorized and repeated.reason == "ACTIVATION_ALREADY_DECIDED"
    assert starts == ["started"]


def test_no_public_direct_context_activation_path_exists(tmp_path: Path) -> None:
    manually_constructed = ExecutionContext.create(
        **values(), timestamp="2026-07-26T12:00:00Z", contract_version=CONTRACT_VERSION
    )
    starts: list[str] = []
    instance = activator(starts)

    assert not hasattr(instance, "activate")
    result = instance.activate_from(manually_constructed)  # type: ignore[arg-type]
    assert result.reason == "CONSUMER_VERIFICATION_FAILED"
    assert instance.state is ExecutorActivationState.REJECTED and not starts


@pytest.mark.parametrize(
    ("published_engine", "published_replay", "expected_engine", "expected_replay"),
    [
        ("OTHER-ENGINE", REPLAY, ENGINE, REPLAY),
        (ENGINE, "55555555-5555-4555-8555-555555555555", ENGINE, REPLAY),
    ],
)
def test_engine_and_replay_mismatch_cannot_activate(
    tmp_path: Path, published_engine: str, published_replay: str,
    expected_engine: str, expected_replay: str,
) -> None:
    path = tmp_path / "execution_context.json"
    publish(path, engine=published_engine, replay=published_replay)
    starts: list[str] = []
    instance = activator(starts)

    result = instance.activate_from(consumer(path, engine=expected_engine, replay=expected_replay))
    assert result.reason == "CONSUMER_VERIFICATION_FAILED"
    assert instance.state is ExecutorActivationState.REJECTED
    assert instance.accepted_context is None and not starts


@pytest.mark.parametrize("payload", [None, b"{", b"[]"])
def test_consumer_failure_permanently_rejects_without_fallback(tmp_path: Path, payload: bytes | None) -> None:
    path = tmp_path / "execution_context.json"
    if payload is not None:
        path.write_bytes(payload)
    starts: list[str] = []
    instance = activator(starts)

    assert instance.activate_from(consumer(path)).reason == "CONSUMER_VERIFICATION_FAILED"
    publish(path)
    repeated = instance.activate_from(consumer(path))
    assert not repeated.authorized and repeated.reason == "ACTIVATION_ALREADY_DECIDED"
    assert instance.state is ExecutorActivationState.REJECTED and not starts


@pytest.mark.parametrize("state", [RuntimeActivationState.NOT_READY, RuntimeActivationState.STOPPED, "READY"])
def test_invalid_runtime_state_permanently_rejects(state: object, tmp_path: Path) -> None:
    path = tmp_path / "execution_context.json"; publish(path)
    starts: list[str] = []
    instance = activator(starts, state)

    result = instance.activate_from(consumer(path))
    assert result.reason == "INVALID_RUNTIME_STATE"
    assert instance.state is ExecutorActivationState.REJECTED and instance.accepted_context is None
    assert instance.activate_from(consumer(path)).reason == "ACTIVATION_ALREADY_DECIDED"
    assert not starts


def test_executor_start_failure_clears_accepted_context(tmp_path: Path) -> None:
    path = tmp_path / "execution_context.json"; publish(path)
    def fail() -> None:
        raise RuntimeError("start failed")
    instance = GovernedExecutorActivator(fail, runtime_state=lambda: RuntimeActivationState.READY)

    result = instance.activate_from(consumer(path))
    assert result.reason == "EXECUTOR_ACTIVATION_FAILED"
    assert instance.state is ExecutorActivationState.REJECTED and instance.accepted_context is None


def test_existing_executor_engine_is_not_modified() -> None:
    source = (Path(__file__).parents[1] / "runtime/executor.py").read_text(encoding="utf-8")
    assert "ExecutionContext" not in source and "GovernedExecutorActivator" not in source
