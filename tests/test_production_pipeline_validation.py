import json

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
        "total_signals": 1, "valid_decisions": 1, "packages_created": 1,
        "executor_acceptances": 1, "orders_sent": 1, "orders_filled": 1,
        "orders_closed": 1, "pipeline_success_rate": 1.0,
        "failure_rate_by_stage": {name: 0.0 for name in FAILURE_CLASSES},
        "average_end_to_end_latency_ms": 8000.0, "missing_stage_count": 0}
    assert report["exit_criteria"]["passed"] is True
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
    assert report["metrics"]["failure_rate_by_stage"]["AI_ENGINE"] == 1.0
    assert report["metrics"]["failure_rate_by_stage"]["PACKAGE"] == 1.0
    assert report["exit_criteria"]["passed"] is False


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
