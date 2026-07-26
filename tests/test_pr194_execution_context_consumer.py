"""PR194 executor-side ExecutionContext consumption tests."""
from dataclasses import FrozenInstanceError
import json
from pathlib import Path
from uuid import uuid4

import pytest

from runtime.execution_context_consumer import ExecutionContextConsumer, ExecutionContextConsumptionError
from runtime.execution_contract import CONTRACT_VERSION, ExecutionContext, serialize_execution_context

ENGINE = "V26.6.2A"
REPLAY = "44444444-4444-4444-8444-444444444444"


def make_context() -> ExecutionContext:
    return ExecutionContext.create(
        execution_uuid="11111111-1111-4111-8111-111111111111",
        decision_uuid="22222222-2222-4222-8222-222222222222",
        package_uuid="33333333-3333-4333-8333-333333333333",
        replay_uuid=REPLAY, execution_confidence=0.75,
        readiness_state="EXECUTION_READY_FOR_ENVIRONMENT_CHECK",
        environment_state="ENVIRONMENT_READY_FOR_FEASIBILITY",
        feasibility_state="EXECUTION_FEASIBLE", policy_version="PR194-POLICY.1",
        engine_version=ENGINE, advisory_only=True,
        timestamp="2026-07-26T12:00:00.000000Z", contract_version=CONTRACT_VERSION,
    )


def loader(path: Path, engine: str = ENGINE, replay: str = REPLAY) -> ExecutionContextConsumer:
    return ExecutionContextConsumer(path, expected_engine_version=engine, expected_replay_uuid=replay)


def write(path: Path) -> bytes:
    payload = serialize_execution_context(make_context())
    path.write_bytes(payload)
    return payload


def reject(path: Path) -> ExecutionContextConsumptionError:
    with pytest.raises(ExecutionContextConsumptionError) as caught:
        loader(path).load()
    return caught.value


def test_successful_loading_and_immutable_object(tmp_path: Path) -> None:
    path = tmp_path / "execution_context.json"
    write(path)
    accepted = loader(path).load()
    assert accepted == make_context()
    with pytest.raises(FrozenInstanceError):
        accepted.engine_version = "changed"  # type: ignore[misc]


@pytest.mark.parametrize("payload", [b"{", b"\xff", b"", b"[]"])
def test_invalid_input_fails_closed(tmp_path: Path, payload: bytes) -> None:
    path = tmp_path / "execution_context.json"
    path.write_bytes(payload)
    reject(path)


def test_missing_publication_fails_closed(tmp_path: Path) -> None:
    assert str(reject(tmp_path / "execution_context.json")) == "PUBLICATION_UNAVAILABLE"


@pytest.mark.parametrize("change,reason", [
    ({"payload_digest": "0" * 64}, "CORRUPTED_PAYLOAD"),
    ({"execution_uuid": "invalid"}, "INVALID_UUID"),
    ({"contract_version": "old"}, "CONTRACT_VERSION_MISMATCH"),
    ({"advisory_only": False}, "INVALID_ADVISORY_STATE"),
    ({"timestamp": "invalid"}, "INVALID_TIMESTAMP"),
    ({"unknown": True}, "INVALID_FIELD_SET"),
])
def test_contract_violations_are_rejected(tmp_path: Path, change: dict[str, object], reason: str) -> None:
    path = tmp_path / "execution_context.json"
    value = json.loads(write(path))
    value.update(change)
    path.write_text(json.dumps(value, sort_keys=True, separators=(",", ":")), encoding="utf-8")
    assert str(reject(path).__cause__) == reason


def test_missing_field_is_rejected(tmp_path: Path) -> None:
    path = tmp_path / "execution_context.json"
    value = json.loads(write(path)); value.pop("policy_version")
    path.write_text(json.dumps(value, sort_keys=True, separators=(",", ":")), encoding="utf-8")
    assert str(reject(path).__cause__) == "INVALID_FIELD_SET"


def test_replay_engine_and_canonical_compatibility(tmp_path: Path) -> None:
    path = tmp_path / "execution_context.json"; write(path)
    with pytest.raises(ExecutionContextConsumptionError) as error:
        loader(path, replay=str(uuid4())).load()
    assert str(error.value.__cause__) == "REPLAY_MISMATCH"
    with pytest.raises(ExecutionContextConsumptionError) as error:
        loader(path, engine="V27").load()
    assert str(error.value.__cause__) == "ENGINE_VERSION_MISMATCH"
    value = json.loads(path.read_bytes()); path.write_text(json.dumps(value, indent=2), encoding="utf-8")
    assert str(reject(path).__cause__) == "NON_CANONICAL_PAYLOAD"


def test_only_named_publication_is_allowed(tmp_path: Path) -> None:
    with pytest.raises(ExecutionContextConsumptionError, match="INVALID_PUBLICATION_PATH"):
        loader(tmp_path / "execution_package.json")
