import json
from pathlib import Path

import pytest

from analysis.production_pipeline_validation import EVENT_SCHEMA_VERSION, FAILURE_CLASSES, STAGES, generate_report


def write_trace(path, events):
    path.write_text("".join(json.dumps(item) + "\n" for item in events), encoding="utf-8")


def event(lifecycle_id, stage, second, *, status="SUCCEEDED", failure_class=None):
    value = {"schema_version": EVENT_SCHEMA_VERSION, "lifecycle_id": lifecycle_id,
             "stage": stage, "status": status,
             "timestamp_utc": f"2026-07-28T12:00:{second:02d}Z"}
    if failure_class is not None:
        value["failure_class"] = failure_class
    return value


def test_complete_lifecycle_reports_every_stage_and_latency(tmp_path):
    source = tmp_path / "trace.jsonl"
    write_trace(source, [event("trade-one", stage, index) for index, stage in enumerate(STAGES)])
    report = generate_report(trace_events=source, output_directory=tmp_path / "out",
                             generated_at_utc="2026-07-28T13:00:00Z")
    assert report["metrics"] == {
        "total_lifecycles": 1, "valid_decisions": 1, "packages_created": 1,
        "executor_acceptances": 1, "orders_sent": 1, "orders_filled": 1,
        "orders_closed": 1, "pipeline_success_rate": 1.0,
        "lifecycle_failure_rate_by_class": {name: 0.0 for name in FAILURE_CLASSES},
        "failure_events_per_lifecycle_by_class": {name: 0.0 for name in FAILURE_CLASSES},
        "average_end_to_end_latency_ms": 8000.0, "missing_stage_count": 0}
    assert "exit_criteria" not in report
    assert report["lifecycles"][0]["complete"] is True
    assert json.loads((tmp_path / "out/pipeline_validation_report.json").read_text()) == report
    assert not list((tmp_path / "out").glob("*.tmp"))


def test_missing_and_explicit_failures_are_never_silent(tmp_path):
    source = tmp_path / "trace.jsonl"
    write_trace(source, [event("trade-bad", "MARKET_STATE", 0),
                         event("trade-bad", "DECISION", 1, status="FAILED", failure_class="AI_ENGINE")])
    report = generate_report(trace_events=source, output_directory=tmp_path / "out")
    lifecycle = report["lifecycles"][0]
    assert lifecycle["missing_stages"] == list(STAGES[2:])
    assert len(lifecycle["failures"]) == 1 + len(STAGES[2:])
    assert report["metrics"]["missing_stage_count"] == len(STAGES[2:])
    assert report["metrics"]["lifecycle_failure_rate_by_class"]["AI_ENGINE"] == 1.0
    assert report["metrics"]["lifecycle_failure_rate_by_class"]["UNKNOWN"] == 1.0
    assert report["metrics"]["failure_events_per_lifecycle_by_class"]["UNKNOWN"] == len(STAGES[2:])
    assert "exit_criteria" not in report


@pytest.mark.parametrize("failure_class", [None, "NOT_A_CLASS", ["ORDER", "BROKER"]])
def test_failed_event_requires_exactly_one_canonical_classification(tmp_path, failure_class):
    source = tmp_path / "trace.jsonl"
    write_trace(source, [event("bad", "ORDER_SENT", 1, status="FAILED", failure_class=failure_class)])
    with pytest.raises(ValueError, match="FAILED_EVENT_REQUIRES_ONE_FAILURE_CLASS"):
        generate_report(trace_events=source, output_directory=tmp_path / "out")
    assert not (tmp_path / "out").exists()


def test_duplicate_stage_and_out_of_order_lifecycle_fail_closed(tmp_path):
    source = tmp_path / "trace.jsonl"
    write_trace(source, [event("duplicate", "MARKET_STATE", 0), event("duplicate", "MARKET_STATE", 1)])
    with pytest.raises(ValueError, match="DUPLICATE_LIFECYCLE_STAGE"):
        generate_report(trace_events=source, output_directory=tmp_path / "out")
    write_trace(source, [event("chronology", "MARKET_STATE", 2), event("chronology", "DECISION", 1)])
    with pytest.raises(ValueError, match="INVALID_LIFECYCLE_CHRONOLOGY"):
        generate_report(trace_events=source, output_directory=tmp_path / "out")


def test_source_trace_is_not_modified(tmp_path):
    source = tmp_path / "trace.jsonl"
    write_trace(source, [event("one", stage, index) for index, stage in enumerate(STAGES)])
    before = source.read_bytes()
    generate_report(trace_events=source, output_directory=tmp_path / "out")
    assert source.read_bytes() == before


def test_failure_is_terminal_and_cannot_continue_downstream(tmp_path):
    source = tmp_path / "trace.jsonl"
    write_trace(source, [event("terminal", "MARKET_STATE", 0),
                         event("terminal", "DECISION", 1, status="FAILED", failure_class="DECISION"),
                         event("terminal", "PACKAGE", 2)])
    with pytest.raises(ValueError, match="STAGE_AFTER_TERMINAL_FAILURE"):
        generate_report(trace_events=source, output_directory=tmp_path / "out")


@pytest.mark.parametrize("stages", [
    ("MARKET_STATE", "DECISION", "PACKAGE", "ORDER_SENT"),
    ("MARKET_STATE", "DECISION", "PACKAGE", "EXECUTOR_ACCEPTED", "ORDER_SENT", "POSITION_CLOSED"),
])
def test_downstream_stage_with_missing_upstream_fails_closed(tmp_path, stages):
    source = tmp_path / "trace.jsonl"
    write_trace(source, [event("gap", stage, index) for index, stage in enumerate(stages)])
    with pytest.raises(ValueError, match="DOWNSTREAM_STAGE_WITH_MISSING_UPSTREAM"):
        generate_report(trace_events=source, output_directory=tmp_path / "out")


@pytest.mark.parametrize(("stage", "failure_class"), [
    ("MARKET_STATE", "BROKER"), ("ORDER_SENT", "WRITER"), ("ANALYTICS", "POSITION"),
])
def test_failure_class_must_match_its_stage(tmp_path, stage, failure_class):
    source = tmp_path / "trace.jsonl"
    write_trace(source, [event("mismatch", stage, 0, status="FAILED", failure_class=failure_class)])
    with pytest.raises(ValueError, match="FAILURE_CLASS_NOT_ALLOWED_FOR_STAGE"):
        generate_report(trace_events=source, output_directory=tmp_path / "out")


def test_multiple_missing_stages_are_one_affected_lifecycle_but_multiple_events(tmp_path):
    source = tmp_path / "trace.jsonl"
    write_trace(source, [event("incomplete", "MARKET_STATE", 0)])
    report = generate_report(trace_events=source, output_directory=tmp_path / "out")
    missing = len(STAGES) - 1
    assert report["metrics"]["lifecycle_failure_rate_by_class"]["UNKNOWN"] == 1.0
    assert report["metrics"]["failure_events_per_lifecycle_by_class"]["UNKNOWN"] == missing


def test_report_uses_local_refs_and_never_exports_raw_identifiers(tmp_path):
    raw = "trade=98765|decision=secret-decision|deal=24680"
    source = tmp_path / "trace.jsonl"
    write_trace(source, [event(raw, stage, index) for index, stage in enumerate(STAGES)])
    report = generate_report(trace_events=source, output_directory=tmp_path / "out")
    payload = json.dumps(report)
    assert report["lifecycles"][0]["lifecycle_ref"] == "L000001"
    assert raw not in payload
    assert "98765" not in payload and "secret-decision" not in payload and "24680" not in payload
    assert "lifecycle_id" not in payload

    failed = [event(raw, "MARKET_STATE", 0, status="FAILED", failure_class="WRITER")]
    failed[0]["failure_reason"] = "deal=24680 decision=secret-decision"
    write_trace(source, failed)
    failed_report = generate_report(trace_events=source, output_directory=tmp_path / "failed")
    assert "24680" not in json.dumps(failed_report)
    assert "secret-decision" not in json.dumps(failed_report)


def test_empty_trace_fails_closed_without_output(tmp_path):
    source = tmp_path / "trace.jsonl"
    source.write_text("\n", encoding="utf-8")
    with pytest.raises(ValueError, match="EMPTY_PIPELINE_TRACE"):
        generate_report(trace_events=source, output_directory=tmp_path / "out")
    assert not (tmp_path / "out").exists()


@pytest.mark.parametrize("failure", ["write", "fsync", "replace"])
def test_atomic_failure_cleans_temp_and_preserves_previous_report(tmp_path, monkeypatch, failure):
    import analysis.production_pipeline_validation as module

    source = tmp_path / "trace.jsonl"
    write_trace(source, [event("one", stage, index) for index, stage in enumerate(STAGES)])
    output = tmp_path / "out"
    output.mkdir()
    destination = output / "pipeline_validation_report.json"
    destination.write_bytes(b"previous-valid-report\n")

    if failure == "write":
        original_open = Path.open

        class FailingStream:
            def __enter__(self):
                return self
            def __exit__(self, *_):
                return False
            def write(self, _payload):
                raise OSError("injected write failure")

        def failing_open(path, *args, **kwargs):
            if path.name.endswith(".tmp"):
                return FailingStream()
            return original_open(path, *args, **kwargs)
        monkeypatch.setattr(Path, "open", failing_open)
    elif failure == "fsync":
        monkeypatch.setattr(module.os, "fsync", lambda _fd: (_ for _ in ()).throw(OSError("injected fsync failure")))
    else:
        monkeypatch.setattr(module.os, "replace", lambda *_: (_ for _ in ()).throw(OSError("injected replace failure")))

    with pytest.raises(OSError, match="injected"):
        generate_report(trace_events=source, output_directory=output)
    assert destination.read_bytes() == b"previous-valid-report\n"
    assert not (output / "pipeline_validation_report.json.tmp").exists()
