import json

import pytest

from bridge import ai_decision_engine_xauusd_v26_execution_confidence_engine as engine
from runtime.runtime_observability import PublicationOutcome, RuntimeObservability


def health(root):
    return json.loads((root / "runtime_health.json").read_text())


def reach_publication(observer):
    for stage in (
        "CONFIGURATION", "PATH RESOLUTION", "ENVIRONMENT OBSERVATION",
        "MARKET STATE READER",
    ):
        observer.stage(stage)
    observer.market_state({"sequence_id": 41, "heartbeat_unix": 1_900_000_000,
                           "source_uuid": "market-source"})
    for stage in ("DECISION CONTEXT", "DECISION INTELLIGENCE", "RISK",
                  "DECISION PUBLISHER"):
        observer.stage(stage)


def decision(sequence=9):
    return {"sequence_id": sequence, "heartbeat_unix": 1_900_000_001,
            "decision_uuid": "00000000-0000-4000-8000-000000000234"}


def test_not_running_until_first_atomic_publication_and_real_stage_order(tmp_path):
    observer = RuntimeObservability(tmp_path)
    reach_publication(observer)
    assert health(tmp_path)["status"] == "STARTING"
    assert health(tmp_path)["current_stage"] == "DECISION PUBLISHER"

    observer.publication(decision(), 12.3456, PublicationOutcome.NORMAL)
    state = health(tmp_path)
    assert state["status"] == "RUNNING"
    assert state["health_state"] == "HEALTHY"
    assert state["current_stage"] == "RUNTIME LOOP"
    expected = (
        "BOOT", "CONFIGURATION", "PATH RESOLUTION", "ENVIRONMENT OBSERVATION",
        "MARKET STATE READER", "MARKET STATE ACCEPTED", "DECISION CONTEXT",
        "DECISION INTELLIGENCE", "RISK", "DECISION PUBLISHER",
        "FIRST NORMAL DECISION PERSISTED", "RUNTIME LOOP",
    )
    log = (tmp_path / "runtime_startup.log").read_text()
    positions = tuple(log.index(stage) for stage in expected)
    assert positions == tuple(sorted(positions))
    assert json.loads((tmp_path / "first_decision.json").read_text()) == decision()
    assert not tuple(tmp_path.glob("*.tmp"))


def test_degraded_fallback_is_preserved_until_normal_recovery(tmp_path):
    observer = RuntimeObservability(tmp_path)
    observer.stage("CONFIGURATION")
    observer.stage("PATH RESOLUTION")
    observer.stage("ENVIRONMENT OBSERVATION")
    observer.stage("MARKET STATE READER")
    observer.failure("READER", RuntimeError("MARKET_STATE_READ_REJECTED"))
    observer.stage("RISK")
    observer.stage("DECISION PUBLISHER")
    observer.publication(decision(), 2.0, PublicationOutcome.STALE_INPUT_FALLBACK)
    degraded = health(tmp_path)
    assert degraded["status"] == "STARTING"
    assert degraded["health_state"] == "DEGRADED"
    assert degraded["runtime_started"] is False
    assert degraded["current_stage"] == "NO_MARKET_STATE"
    assert degraded["failure_owner"] == "NO_MARKET_STATE"
    assert degraded["failure_reason"] == "NO_MARKET_STATE"
    assert not (tmp_path / "first_decision.json").exists()
    assert "RUNTIME LOOP" not in (tmp_path / "runtime_startup.log").read_text()

    reach_publication(observer)
    observer.publication(decision(10), 1.0, PublicationOutcome.NORMAL)
    recovered = health(tmp_path)
    assert recovered["health_state"] == "HEALTHY"
    assert recovered["status"] == "RUNNING"
    assert recovered["runtime_started"] is True
    assert recovered["first_publication_at"] is not None
    assert recovered["first_normal_decision_at"] is not None
    assert recovered["fallback_count"] == 1
    assert recovered["failure_owner"] is None
    assert recovered["failure_reason"] is None


def test_publication_metrics_are_separate(tmp_path):
    observer = RuntimeObservability(tmp_path)
    observer.publication(decision(1), 1, PublicationOutcome.STALE_INPUT_FALLBACK)
    observer.failure("ANALYSIS", RuntimeError("BUILD_DECISION_FAILED"))
    observer.publication(decision(2), 1, PublicationOutcome.LOGIC_ERROR_REJECTION)
    before_start = health(tmp_path)
    assert before_start["status"] == "STARTING"
    assert before_start["health_state"] == "DEGRADED"
    assert before_start["runtime_started"] is False
    assert before_start["current_stage"] == "ANALYSIS_FAILED"
    assert before_start["failure_owner"] == "ANALYSIS_FAILED"
    assert before_start["rejected_loop_count"] == 1
    observer.publication(decision(3), 1, PublicationOutcome.NORMAL)
    state = health(tmp_path)
    assert state["publication_count"] == 3
    assert state["loop_count"] == 3
    assert state["successful_loop_count"] == 1
    assert state["fallback_count"] == 1
    assert state["rejected_loop_count"] == 1
    assert len((tmp_path / "decision.log").read_text().splitlines()) == 3


def test_repeated_fallbacks_never_activate_runtime(tmp_path):
    observer = RuntimeObservability(tmp_path)
    observer.failure("READER", RuntimeError("MARKET_STATE_READ_REJECTED"))
    observer.publication(decision(1), 1, PublicationOutcome.STALE_INPUT_FALLBACK)
    observer.failure("READER", RuntimeError("MARKET_STATE_READ_REJECTED"))
    observer.publication(decision(2), 1, PublicationOutcome.STALE_INPUT_FALLBACK)
    state = health(tmp_path)
    assert state["status"] == "STARTING"
    assert state["health_state"] == "DEGRADED"
    assert state["runtime_started"] is False
    assert state["publication_count"] == state["fallback_count"] == 2
    assert state["successful_loop_count"] == 0
    assert "RUNTIME LOOP" not in (tmp_path / "runtime_startup.log").read_text()
    assert not tuple(tmp_path.glob("*.tmp"))


def test_fallback_after_start_degrades_and_normal_recovery_retains_history(tmp_path):
    observer = RuntimeObservability(tmp_path)
    observer.publication(decision(1), 1, PublicationOutcome.NORMAL)
    observer.failure("READER", RuntimeError("MARKET_STATE_READ_REJECTED"))
    observer.publication(decision(2), 1, PublicationOutcome.STALE_INPUT_FALLBACK)
    degraded = health(tmp_path)
    assert degraded["status"] == "RUNNING"
    assert degraded["runtime_started"] is True
    assert degraded["health_state"] == "DEGRADED"
    assert degraded["failure_owner"] == "NO_MARKET_STATE"

    observer.publication(decision(3), 1, PublicationOutcome.NORMAL)
    recovered = health(tmp_path)
    assert recovered["status"] == "RUNNING"
    assert recovered["health_state"] == "HEALTHY"
    assert recovered["failure_owner"] is None
    assert recovered["failure_reason"] is None
    assert recovered["publication_count"] == 3
    assert recovered["successful_loop_count"] == 2
    assert recovered["fallback_count"] == 1


def test_first_normal_snapshot_is_not_created_by_non_normal_outcomes(tmp_path):
    observer = RuntimeObservability(tmp_path)
    observer.failure("READER", RuntimeError("MARKET_STATE_READ_REJECTED"))
    observer.publication(decision(1), 1, PublicationOutcome.STALE_INPUT_FALLBACK)
    observer.failure("ANALYSIS", RuntimeError("BUILD_DECISION_FAILED"))
    observer.publication(decision(2), 1, PublicationOutcome.LOGIC_ERROR_REJECTION)
    assert not (tmp_path / "first_decision.json").exists()

    observer.publication(decision(3), 1, PublicationOutcome.NORMAL)
    snapshot = (tmp_path / "first_decision.json").read_bytes()
    assert json.loads(snapshot)["sequence_id"] == 3
    observer.publication(decision(4), 1, PublicationOutcome.NORMAL)
    assert (tmp_path / "first_decision.json").read_bytes() == snapshot
    assert "FIRST NORMAL DECISION PERSISTED -> RUNTIME LOOP" in (
        tmp_path / "runtime_startup.log"
    ).read_text()
    assert not tuple(tmp_path.glob("*.tmp"))


@pytest.mark.parametrize("owner", [
    "CONFIG", "READER", "DECISION_CONTEXT", "ANALYSIS", "RISK",
    "PUBLISHER", "HEALTH",
])
def test_failure_ownership_is_exact(tmp_path, owner):
    observer = RuntimeObservability(tmp_path)
    observer.failure(owner, RuntimeError(f"{owner}_FAILED"))
    state = health(tmp_path)
    expected = {
        "CONFIG": "CONTEXT_BUILD_FAILED", "READER": "NO_MARKET_STATE",
        "DECISION_CONTEXT": "CONTEXT_BUILD_FAILED", "ANALYSIS": "ANALYSIS_FAILED",
        "RISK": "RISK_REJECTED", "PUBLISHER": "PUBLICATION_FAILED",
        "HEALTH": "PUBLICATION_FAILED",
    }[owner]
    assert state["failure_owner"] == expected
    assert state["health_state"] == "DEGRADED"
    with pytest.raises(ValueError, match="INVALID_FAILURE_OWNER"):
        observer.failure("GENERIC", RuntimeError("bad"))


def engine_decision():
    return engine.build_decision({
        "bid": 0, "ma50": 2300, "bar_time": "pr234-runtime-fixture",
    })[2]


def test_canonical_write_path_attributes_risk_failure(tmp_path, monkeypatch):
    observer = RuntimeObservability(tmp_path)
    monkeypatch.setattr(engine, "BASE_PATH", tmp_path)
    monkeypatch.setattr(engine, "OUTPUT_PATH", tmp_path / "decision.json")
    monkeypatch.setattr(engine.time, "sleep", lambda _: None)
    monkeypatch.setattr(
        engine, "construct_risk_payload_before_validation",
        lambda _: (_ for _ in ()).throw(RuntimeError("RISK_CONSTRUCTION_FAILED")),
    )
    assert engine.write_decision(engine_decision(), observer=observer) is False
    observer.failure(engine._last_write_failure_owner,
                     RuntimeError("DECISION_ATOMIC_PUBLICATION_FAILED"))
    assert health(tmp_path)["failure_owner"] == "RISK_REJECTED"


def test_canonical_write_path_attributes_publisher_failure(tmp_path, monkeypatch):
    observer = RuntimeObservability(tmp_path)
    monkeypatch.setattr(engine, "BASE_PATH", tmp_path)
    monkeypatch.setattr(engine, "OUTPUT_PATH", tmp_path / "decision.json")
    monkeypatch.setattr(engine.time, "sleep", lambda _: None)
    replace = engine.os.replace
    monkeypatch.setattr(
        engine.os, "replace",
        lambda *_: (_ for _ in ()).throw(OSError("ATOMIC_REPLACE_FAILED")),
    )
    assert engine.write_decision(engine_decision(), observer=observer) is False
    monkeypatch.setattr(engine.os, "replace", replace)
    observer.failure(engine._last_write_failure_owner,
                     RuntimeError("DECISION_ATOMIC_PUBLICATION_FAILED"))
    assert health(tmp_path)["failure_owner"] == "PUBLICATION_FAILED"
