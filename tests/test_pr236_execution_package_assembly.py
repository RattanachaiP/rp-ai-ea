import json
import os
from pathlib import Path
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from execution_package_assembly import ExecutionPackageAssembler, ExecutionPackageError
from execution_package_contract import EXECUTION_PACKAGE_FIELDS
from runtime.decision_publication import DECISION_PRODUCER, PUBLISHED_SCHEMA_VERSION, RUNTIME_VERSION
from runtime.market_state_reader import SOURCE_UUID


NOW = 1_785_283_200
DECISION_UUID = "00000000-0000-4000-8000-000000000236"


def decision(sequence=42, **changes):
    value = {
        "decision_uuid": DECISION_UUID, "market_state_sequence_id": sequence,
        "heartbeat_unix": NOW, "producer": DECISION_PRODUCER,
        "producer_version": RUNTIME_VERSION, "schema_version": PUBLISHED_SCHEMA_VERSION,
        "market_state_source_uuid": SOURCE_UUID, "symbol": "XAUUSD", "direction": "BUY",
        "confidence": 81.5, "active_profile": "Balanced", "volume": 0.1,
        "entry_price": 2400.5, "stop_loss": 2395.0, "take_profit": 2411.5,
        "management": "SCALP_TP", "decision_timestamp": "2026-07-29T00:00:00Z",
        "decision_lifecycle": "NORMAL_TRADE", "decision": "TRADE",
        "execution_state": "EXECUTE_NORMAL", "final_veto_owner": "NONE",
        "effective_veto_code": "NONE", "entry_allowed": True,
        "executor_order_send_required": True,
    }
    value.update(changes)
    return value


def assembler(tmp_path, sequence=42, **changes):
    path = tmp_path / "decision.json"
    path.write_text(json.dumps(decision(sequence, **changes)), encoding="utf-8")
    return ExecutionPackageAssembler(path, tmp_path / "execution_package.json",
        clock=lambda: NOW, uuid_factory=lambda: "00000000-0000-4000-8000-000000000001")


def rejection(tmp_path, reason, **changes):
    with pytest.raises(ExecutionPackageError) as raised:
        assembler(tmp_path, **changes).assemble()
    assert raised.value.owner == "VALIDATION" and raised.value.reason == reason
    assert not (tmp_path / "execution_package.json").exists()


def test_authorized_decision_is_copied_and_published(tmp_path):
    package = assembler(tmp_path).assemble()
    assert tuple(package) == EXECUTION_PACKAGE_FIELDS and len(package) == 18
    assert package["decision_uuid"] == DECISION_UUID and package["source_uuid"] == SOURCE_UUID
    assert package["management_profile"] == "SCALP_TP" and package["market_sequence"] == 42
    assert json.loads((tmp_path / "execution_package.json").read_text()) == package
    state = json.loads((tmp_path / "execution_package_state.json").read_text())
    assert state["last_market_sequence"] == 42 and state["last_execution_uuid"] == package["execution_uuid"]
    health = json.loads((tmp_path / "execution_package_health.json").read_text())
    assert health["status"] == "OBSERVED" and "executor_ready" not in health
    assert not tuple(tmp_path.glob("*.tmp"))


def test_invalid_producer_version_is_rejected(tmp_path):
    rejection(tmp_path, "INVALID_DECISION_PRODUCER_VERSION", producer_version="old")


@pytest.mark.parametrize("lifecycle", ["GOVERNED_NO_TRADE", "STALE_INPUT_FALLBACK", "LOGIC_ERROR_REJECTION"])
def test_non_executable_lifecycle_is_rejected(tmp_path, lifecycle):
    rejection(tmp_path, "DECISION_LIFECYCLE_NOT_EXECUTABLE", decision_lifecycle=lifecycle)


@pytest.mark.parametrize("change", [
    {"final_veto_owner": "RISK"}, {"effective_veto_code": "RISK_REJECTED"},
])
def test_runtime_veto_is_rejected(tmp_path, change):
    rejection(tmp_path, "RUNTIME_EXECUTION_VETOED", **change)


def test_execution_state_must_be_runtime_executable(tmp_path):
    rejection(tmp_path, "EXECUTION_STATE_NOT_EXECUTABLE", execution_state="WAIT")


@pytest.mark.parametrize(("changes", "reason"), [
    ({"heartbeat_unix": NOW - 31}, "STALE_HEARTBEAT"),
    ({"market_state_source_uuid": "00000000-0000-4000-8000-000000000099"}, "INVALID_LINEAGE"),
    ({"entry_allowed": False}, "RUNTIME_EXECUTION_NOT_AUTHORIZED"),
    ({"executor_order_send_required": False}, "RUNTIME_EXECUTION_NOT_AUTHORIZED"),
])
def test_freshness_lineage_and_final_authority_fail_closed(tmp_path, changes, reason):
    rejection(tmp_path, reason, **changes)


def test_deleted_package_does_not_reset_durable_monotonic_authority(tmp_path):
    assembler(tmp_path).assemble()
    (tmp_path / "execution_package.json").unlink()
    with pytest.raises(ExecutionPackageError, match="NON_MONOTONIC_SEQUENCE"):
        assembler(tmp_path).assemble()
    assert not (tmp_path / "execution_package.json").exists()


def test_rollback_attempt_below_durable_sequence_is_rejected(tmp_path):
    assembler(tmp_path, sequence=42).assemble()
    with pytest.raises(ExecutionPackageError, match="NON_MONOTONIC_SEQUENCE"):
        assembler(tmp_path, sequence=41).assemble()
    assert json.loads((tmp_path / "execution_package_state.json").read_text())["last_market_sequence"] == 42


def test_health_failure_is_observational_and_explicitly_traced(tmp_path, monkeypatch):
    value = assembler(tmp_path)
    original = value._atomic_write
    def fail_health(path, payload):
        if Path(path).name == "execution_package_health.json":
            raise OSError("health unavailable")
        return original(path, payload)
    monkeypatch.setattr(value, "_atomic_write", fail_health)
    package = value.assemble()
    assert package["market_sequence"] == 42
    assert "HEALTH_PUBLICATION_FAILED" in (tmp_path / "execution_package_trace.log").read_text()


def test_injected_clock_controls_package_trace_health_and_state(tmp_path):
    value = assembler(tmp_path)
    package = value.assemble()
    expected = "2026-07-29T00:00:00Z"
    assert package["execution_timestamp"] == expected
    assert json.loads((tmp_path / "execution_package_state.json").read_text())["last_publication_time"] == expected
    assert json.loads((tmp_path / "execution_package_health.json").read_text())["updated_at"] == expected
    assert {json.loads(line)["timestamp"] for line in (tmp_path / "execution_package_trace.log").read_text().splitlines()} == {expected}


def test_posix_atomic_replace_fsyncs_parent_directory(tmp_path, monkeypatch):
    if os.name != "posix":
        pytest.skip("directory fsync contract is POSIX-only")
    directory_fsync = []
    real_fsync = os.fsync
    def observe(fd):
        if os.path.isdir(f"/proc/self/fd/{fd}"):
            directory_fsync.append(fd)
        return real_fsync(fd)
    monkeypatch.setattr(os, "fsync", observe)
    assembler(tmp_path).assemble()
    assert directory_fsync


def test_controlled_artifacts_are_isolated_from_production_root():
    root = Path(__file__).resolve().parents[1]
    assert not (root / "execution_package.json").exists()
    assert not (root / "execution_package_health.json").exists()
    assert not (root / "execution_package_state.json").exists()
