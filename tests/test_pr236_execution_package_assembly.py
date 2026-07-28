import json

import pytest

from execution_package_assembly import ExecutionPackageAssembler, ExecutionPackageError, PACKAGE_FIELDS


NOW = 1_785_283_200
DECISION_UUID = "00000000-0000-4000-8000-000000000236"
SOURCE_UUID = "dc3777c6-cf0d-5a7b-bd58-8a5c44568475"


def decision(**changes):
    value = {"decision_uuid": DECISION_UUID, "market_state_sequence_id": 42,
             "heartbeat_unix": NOW, "producer": "RP_AI_RUNTIME", "producer_version": "27.5",
             "schema_version": "2.0", "market_state_source_uuid": SOURCE_UUID,
             "symbol": "XAUUSD", "direction": "BUY", "confidence": 81.5,
             "active_profile": "Balanced", "volume": 0.1, "entry_price": 2400.5,
             "stop_loss": 2395.0, "take_profit": 2411.5,
             "management_profile": "STANDARD", "decision_timestamp": "2026-07-28T14:00:00Z"}
    value.update(changes)
    return value


def assembler(tmp_path, **decision_changes):
    path = tmp_path / "decision.json"
    path.write_text(json.dumps(decision(**decision_changes)), encoding="utf-8")
    return ExecutionPackageAssembler(path, tmp_path / "execution_package.json",
        clock=lambda: NOW, uuid_factory=lambda: "00000000-0000-4000-8000-000000000001")


def test_verified_decision_is_copied_and_atomically_published(tmp_path):
    package = assembler(tmp_path).assemble()
    assert tuple(package) == PACKAGE_FIELDS
    assert package["decision_uuid"] == DECISION_UUID and package["source_uuid"] == SOURCE_UUID
    assert package["market_sequence"] == 42 and package["lot_size"] == 0.1
    assert json.loads((tmp_path / "execution_package.json").read_text()) == package
    health = json.loads((tmp_path / "execution_package_health.json").read_text())
    assert health["status"] == "VERIFIED" and health["executor_ready"] is True
    assert {json.loads(line)["event"] for line in (tmp_path / "execution_package_trace.log").read_text().splitlines()} == {"ACCEPTED", "ASSEMBLED", "VALID", "PUBLISHED"}
    assert not tuple(tmp_path.glob("*.tmp"))


@pytest.mark.parametrize(("changes", "reason"), [
    ({"producer": ""}, "MISSING_OR_INVALID_PRODUCER"),
    ({"decision_uuid": "bad"}, "INVALID_DECISION_UUID"),
    ({"schema_version": "3.0"}, "INVALID_DECISION_SCHEMA"),
    ({"heartbeat_unix": NOW - 121}, "STALE_HEARTBEAT"),
    ({"market_state_source_uuid": "bad"}, "INVALID_SOURCE_UUID"),
    ({"volume": 0}, "INVALID_EXECUTION_FIELDS"),
])
def test_invalid_decision_fails_closed_with_health_and_trace(tmp_path, changes, reason):
    with pytest.raises(ExecutionPackageError) as raised:
        assembler(tmp_path, **changes).assemble()
    assert raised.value.owner == "VALIDATION" and raised.value.reason == reason
    assert not (tmp_path / "execution_package.json").exists()
    health = json.loads((tmp_path / "execution_package_health.json").read_text())
    assert health["failure_owner"] == "VALIDATION" and health["failure_reason"] == reason


def test_existing_sequence_must_increase_and_package_is_not_replaced(tmp_path):
    value = assembler(tmp_path)
    value.assemble()
    original = (tmp_path / "execution_package.json").read_bytes()
    with pytest.raises(ExecutionPackageError, match="NON_MONOTONIC_SEQUENCE"):
        value.assemble()
    assert (tmp_path / "execution_package.json").read_bytes() == original
