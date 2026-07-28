import json
import subprocess
import sys
from pathlib import Path

from bridge.ai_decision_engine_xauusd_v28 import V28DecisionEngine
from bridge.v28.market_reader import PRODUCER, PRODUCER_VERSION, SCHEMA_VERSION, SOURCE_UUID
from bridge.v28.publisher import PublicationError


def market(sequence=7, heartbeat=100.0):
    return {"producer": PRODUCER, "producer_version": PRODUCER_VERSION, "schema_version": SCHEMA_VERSION,
            "source_uuid": SOURCE_UUID, "symbol": "XAUUSD", "timeframe": "M1", "heartbeat_unix": heartbeat,
            "sequence_id": sequence, "bid": 2300.0, "ask": 2300.2, "nested": {"ticks": [1]}}


def paths(tmp_path):
    source = tmp_path / "market_state.json"; output = tmp_path / "decision.json"
    source.write_text(json.dumps(market())); return source, output


def test_cycle_uses_one_clock_snapshot_and_preserves_source_heartbeat(tmp_path):
    source, output = paths(tmp_path); calls = []
    def clock():
        calls.append(101.0); return 101.0
    engine = V28DecisionEngine(source, output, clock=clock)
    value = engine.cycle()
    assert len(calls) == 1
    assert value["heartbeat_unix"] == 100.0
    assert value["published_at"] == "1970-01-01T00:01:41Z"
    assert engine.health.heartbeat_age == 1.0


def test_duplicate_is_suppressed_and_regression_fails_closed(tmp_path):
    source, output = paths(tmp_path); engine = V28DecisionEngine(source, output, clock=lambda: 101)
    assert engine.cycle() is not None; first = output.read_bytes()
    assert engine.cycle() is None and engine.health.cycle_state == "DUPLICATE_SUPPRESSED"
    assert output.read_bytes() == first
    source.write_text(json.dumps(market(sequence=6)))
    assert engine.cycle() is None and engine.health.last_error == "SEQUENCE_REGRESSION"
    assert output.read_bytes() == first


def test_publication_failure_updates_current_health_and_preserves_sequence(tmp_path, monkeypatch):
    source, output = paths(tmp_path); engine = V28DecisionEngine(source, output, clock=lambda: 101)
    def fail(_): raise PublicationError("ATOMIC_PUBLICATION_FAILED")
    monkeypatch.setattr(engine.publisher, "publish", fail)
    assert engine.cycle() is None
    assert engine.health.cycle_state == "FAILED" and engine.health.last_error == "ATOMIC_PUBLICATION_FAILED"
    assert engine.health.heartbeat_age == 1.0 and engine.last_published_sequence is None and not output.exists()


def test_restart_recovers_sequence_from_existing_decision(tmp_path):
    source, output = paths(tmp_path); first = V28DecisionEngine(source, output, clock=lambda: 101)
    first.run(iterations=1, interval_seconds=0)
    second = V28DecisionEngine(source, output, clock=lambda: 101)
    second.run(iterations=1, interval_seconds=0)
    assert second.health.cycle_state == "DUPLICATE_SUPPRESSED"


def test_direct_start_invalid_configuration_is_fatal(tmp_path):
    result = subprocess.run([sys.executable, "bridge/ai_decision_engine_xauusd_v28.py",
        "--market", str(tmp_path / "wrong.json"), "--decision", str(tmp_path / "decision.json"),
        "--iterations", "1"], cwd=Path(__file__).parents[1], capture_output=True, text=True)
    assert result.returncode == 2 and "fatal_startup" in result.stderr
