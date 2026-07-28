import json

import pytest

from runtime.runtime_observability import RuntimeObservability


def test_runtime_observability_atomically_exposes_continuous_health(tmp_path):
    observer = RuntimeObservability(tmp_path)
    observer.transition("BOOT", "CONFIGURATION", startup=True)
    observer.transition("CONFIGURATION", "RUNTIME LOOP", startup=True)
    observer.running()
    observer.market_state({
        "sequence_id": 41, "heartbeat_unix": 1_900_000_000,
        "source_uuid": "dc3777c6-cf0d-5a7b-bd58-8a5c44568475",
    })
    decision = {
        "sequence_id": 9, "heartbeat_unix": 1_900_000_001,
        "decision_uuid": "00000000-0000-4000-8000-000000000234",
    }
    observer.decision(decision, 12.3456)
    observer.decision(decision | {"sequence_id": 10}, 8.0)

    health = json.loads((tmp_path / "runtime_health.json").read_text())
    assert health["status"] == "RUNNING"
    assert health["loop_count"] == 2
    assert health["last_market_state"]["sequence_id"] == 41
    assert health["last_decision"]["sequence_id"] == 10
    assert health["loop_latency_ms"] == 8.0
    assert health["exception_count"] == 0
    assert health["current_stage"] == "RUNTIME LOOP"
    assert json.loads((tmp_path / "first_decision.json").read_text()) == decision
    assert "BOOT -> CONFIGURATION" in (tmp_path / "runtime_startup.log").read_text()
    assert len((tmp_path / "decision.log").read_text().splitlines()) == 2
    assert not tuple(tmp_path.glob("*.tmp"))


def test_runtime_failure_requires_an_exact_owner(tmp_path):
    observer = RuntimeObservability(tmp_path)
    observer.failure("READER", RuntimeError("STALE_HEARTBEAT"))
    health = json.loads((tmp_path / "runtime_health.json").read_text())
    assert health["status"] == "RUNNING"
    assert health["failure_owner"] == "READER"
    assert health["exception_count"] == 1
    with pytest.raises(ValueError, match="INVALID_FAILURE_OWNER"):
        observer.failure("GENERIC", RuntimeError("bad"))
