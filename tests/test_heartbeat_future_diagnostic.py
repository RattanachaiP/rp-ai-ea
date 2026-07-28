"""Regression coverage for the PR241 read-only diagnostic utility."""

import json

from analysis import heartbeat_future_diagnostic as diagnostic


def test_capture_records_clock_bounds_and_signed_delta(tmp_path, monkeypatch):
    path = tmp_path / "market_state.json"
    path.write_text(json.dumps({"sequence_id": 39690, "heartbeat_unix": 101.25}))
    clock = iter((100.0, 100.2, 101.0, 101.4))
    monkeypatch.setattr(diagnostic.time, "time", lambda: next(clock))
    monkeypatch.setattr(diagnostic.time, "sleep", lambda _: None)

    observations = diagnostic.capture(path, count=2, interval_seconds=0.25)

    assert observations[0] == {
        "sample": 1,
        "sequence_id": 39690,
        "heartbeat_unix": 101.25,
        "local_time": 100.1,
        "delta_seconds": 1.1500000000000057,
        "local_time_before_read": 100.0,
        "local_time_after_read": 100.2,
        "read_uncertainty_seconds": 0.20000000000000284,
    }
    assert observations[1]["delta_seconds"] == 0.04999999999999716


def test_capture_rejects_non_numeric_heartbeat(tmp_path):
    path = tmp_path / "market_state.json"
    path.write_text(json.dumps({"sequence_id": 1, "heartbeat_unix": True}))

    try:
        diagnostic.capture(path, count=2, interval_seconds=0.0)
    except ValueError as exc:
        assert str(exc) == "HEARTBEAT_NOT_NUMERIC"
    else:
        raise AssertionError("non-numeric heartbeat was accepted")
