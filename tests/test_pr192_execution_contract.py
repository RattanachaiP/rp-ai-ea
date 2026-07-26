"""PR192 immutable Runtime-to-MT5 execution contract tests."""
from dataclasses import FrozenInstanceError
import json
from pathlib import Path
import sys
from uuid import UUID

import pytest

sys.path.insert(0, str(Path(__file__).parents[1]))

from runtime.execution_contract import (CONTRACT_VERSION, ExecutionContext,
    ExecutionContractError, REQUIRED_FIELDS, deserialize_execution_context,
    serialize_execution_context)


VALUES = {
    "execution_uuid": "10000000-0000-4000-8000-000000000001",
    "decision_uuid": "20000000-0000-4000-8000-000000000002",
    "package_uuid": "30000000-0000-4000-8000-000000000003",
    "replay_uuid": "40000000-0000-4000-8000-000000000004",
    "execution_confidence": 0.75,
    "readiness_state": "EXECUTION_READY_FOR_ENVIRONMENT_CHECK",
    "environment_state": "ENVIRONMENT_READY_FOR_FEASIBILITY",
    "feasibility_state": "EXECUTION_FEASIBLE",
    "policy_version": "PR192-POLICY.1",
    "engine_version": "V26.6.2A",
    "advisory_only": True,
    "timestamp": "2026-07-26T12:00:00+00:00",
    "contract_version": CONTRACT_VERSION,
}


def context(**changes):
    return ExecutionContext.create(**{**VALUES, **changes})


def load(payload):
    return deserialize_execution_context(payload, expected_engine_version=VALUES["engine_version"],
                                         expected_replay_uuid=VALUES["replay_uuid"])


def test_valid_contract_serialization_is_canonical_and_deterministic():
    payload = serialize_execution_context(context())
    assert payload == serialize_execution_context(context())
    assert payload == json.dumps(json.loads(payload), sort_keys=True, separators=(",", ":")).encode()


def test_public_schema_matches_runtime_contract_exactly():
    schema = json.loads((Path(__file__).parents[1] / "contracts/execution_context.schema.json").read_text())
    assert set(schema["required"]) == REQUIRED_FIELDS == set(schema["properties"])
    assert schema["additionalProperties"] is False
    assert schema["properties"]["contract_version"]["const"] == CONTRACT_VERSION


def test_valid_contract_deserialization():
    expected = context()
    assert load(serialize_execution_context(expected)) == expected
    assert all(str(UUID(getattr(expected, field))) == getattr(expected, field)
               for field in ("execution_uuid", "decision_uuid", "package_uuid", "replay_uuid"))


def test_missing_field_rejected_without_partial_loading():
    raw = context().to_dict(); raw.pop("decision_uuid")
    with pytest.raises(ExecutionContractError, match="INVALID_FIELD_SET"):
        load(json.dumps(raw, sort_keys=True, separators=(",", ":")).encode())


def test_invalid_uuid_rejected():
    with pytest.raises(ExecutionContractError, match="INVALID_UUID"):
        context(execution_uuid="not-a-uuid")


def test_contract_version_mismatch_rejected():
    with pytest.raises(ExecutionContractError, match="CONTRACT_VERSION_MISMATCH"):
        context(contract_version="PR192-EXECUTION-CONTEXT.2")


def test_engine_version_mismatch_rejected():
    payload = serialize_execution_context(context())
    with pytest.raises(ExecutionContractError, match="ENGINE_VERSION_MISMATCH"):
        deserialize_execution_context(payload, expected_engine_version="V27",
                                      expected_replay_uuid=VALUES["replay_uuid"])


def test_replay_mismatch_rejected():
    with pytest.raises(ExecutionContractError, match="REPLAY_MISMATCH"):
        deserialize_execution_context(serialize_execution_context(context()),
            expected_engine_version=VALUES["engine_version"],
            expected_replay_uuid="50000000-0000-4000-8000-000000000005")


def test_payload_and_returned_mapping_are_immutable():
    value = context()
    with pytest.raises(FrozenInstanceError):
        value.policy_version = "changed"
    copied = value.to_dict(); copied["policy_version"] = "changed"
    assert value.policy_version == VALUES["policy_version"]


@pytest.mark.parametrize("mutate", [
    lambda raw: raw.update(execution_confidence=0.9),
    lambda raw: raw.update(extra="forbidden"),
])
def test_corruption_and_unknown_fields_fail_closed(mutate):
    raw = context().to_dict(); mutate(raw)
    payload = json.dumps(raw, sort_keys=True, separators=(",", ":")).encode()
    with pytest.raises(ExecutionContractError):
        load(payload)


@pytest.mark.parametrize("payload", [b"{", b"{}", b'{"x":NaN}', object()])
def test_deserialization_failures_never_fallback(payload):
    with pytest.raises(ExecutionContractError):
        load(payload)


def test_noncanonical_payload_rejected():
    payload = serialize_execution_context(context()) + b"\n"
    with pytest.raises(ExecutionContractError, match="NON_CANONICAL_PAYLOAD"):
        load(payload)
