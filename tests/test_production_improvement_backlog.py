import json

import pytest

import analysis.production_improvement_backlog as backlog_module
from analysis.production_improvement_backlog import SCHEMA_VERSION, generate_backlog


NOW = "2026-07-28T12:00:00Z"


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value), encoding="utf-8")


def production_value(*, rejection=2, restart=1, net=-25, observations=None):
    return {"schema_version": "PR253.PRODUCTION_TRADING_REPORT.1.0",
        "trading": {"total_trades": 4, "net_profit": net},
        "measurable_observations": observations if observations is not None else [
            {"metric": "execution_rejections", "value": rejection, "sample_size": 10},
            {"metric": "runtime_restarts", "value": restart, "sample_size": None},
            {"metric": "win_rate", "value": 0.25, "sample_size": 4},
        ]}


def run(paths, output, **kwargs):
    return generate_backlog(evidence=paths, output_directory=output,
                            generated_at_utc=kwargs.pop("generated_at_utc", NOW), **kwargs)


def test_builds_measurable_snapshot_scoped_pending_human_items(tmp_path):
    production = tmp_path / "production_trading_report.json"
    pipeline = tmp_path / "pipeline_validation_report.json"
    write(production, production_value())
    write(pipeline, {"schema_version": "PR254.PIPELINE_VALIDATION_REPORT.1.0",
        "metrics": {"total_lifecycles": 5, "missing_stage_count": 3}})
    report = run([production, pipeline], tmp_path / "out")

    assert report["schema_version"] == SCHEMA_VERSION
    assert report["human_approval_required"] is True
    assert len(report["items"]) == 4
    rejected = next(item for item in report["items"] if "EXECUTION_REJECTIONS" in item["id"])
    assert rejected["frequency"] == {"measurement": "occurrence_rate", "occurrences": 2,
                                      "sample_size": 10, "rate": 0.2}
    assert rejected["reproducibility"]["classification"] == "NOT_ESTABLISHED"
    assert rejected["priority"] == "P1"  # no occurrence-based escalation
    assert rejected["status"] == "PENDING_HUMAN_REVIEW"
    assert set(rejected["evidence"][0]) == {"source_ref", "json_pointer", "observed_value"}
    assert json.loads((tmp_path / "out" / "production_improvement_backlog.json").read_text()) == report


def test_repeated_basenames_get_unique_refs_and_snapshot_item_ids(tmp_path):
    first = tmp_path / "day1" / "production_trading_report.json"
    second = tmp_path / "day2" / "production_trading_report.json"
    write(first, production_value(rejection=1, net=10))
    write(second, production_value(rejection=3, net=10))
    report = run([first, second], tmp_path / "out")

    assert [source["source_ref"] for source in report["source_evidence"]] == ["S000001", "S000002"]
    assert [source["basename"] for source in report["source_evidence"]] == [
        "production_trading_report.json", "production_trading_report.json"]
    rejection_ids = [item["id"] for item in report["items"] if "EXECUTION_REJECTIONS" in item["id"]]
    assert len(rejection_ids) == len(set(rejection_ids)) == 2
    assert {item["evidence"][0]["source_ref"] for item in report["items"]} == {"S000001", "S000002"}


def test_output_and_source_refs_are_deterministic_regardless_of_input_order(tmp_path):
    first = tmp_path / "a" / "production_trading_report.json"
    second = tmp_path / "b" / "production_trading_report.json"
    write(first, production_value(rejection=1, net=5))
    write(second, production_value(rejection=4, net=6))
    forward = run([first, second], tmp_path / "forward")
    reverse = run([second, first], tmp_path / "reverse")
    assert forward == reverse


def test_duplicate_paths_and_identical_snapshots_fail_explicitly(tmp_path):
    source = tmp_path / "production_trading_report.json"
    write(source, production_value())
    with pytest.raises(ValueError, match="DUPLICATE_EVIDENCE_PATH"):
        run([source, source], tmp_path / "out")
    copy_path = tmp_path / "copy" / source.name
    write(copy_path, production_value())
    with pytest.raises(ValueError, match="DUPLICATE_EVIDENCE_SNAPSHOT"):
        run([source, copy_path], tmp_path / "out")


def test_unknown_governed_observation_is_explicit_and_zero_is_non_adverse(tmp_path):
    source = tmp_path / "production_trading_report.json"
    write(source, production_value(net=10, observations=[
        {"metric": "execution_rejections", "value": 0, "sample_size": 5},
        {"metric": "future_metric", "value": 7, "sample_size": 8},
    ]))
    report = run([source], tmp_path / "out")
    assert report["items"] == []
    assert report["source_evidence"][0]["processing_status"] == "NO_ADVERSE_OBSERVATION"
    assert report["unsupported_observations"] == [{
        "source_ref": "S000001", "json_pointer": "/measurable_observations/1",
        "metric": "future_metric", "processing_status": "UNSUPPORTED_GOVERNED_OBSERVATION"}]


def test_duplicate_and_malformed_governed_observations_fail_closed(tmp_path):
    source = tmp_path / "production_trading_report.json"
    duplicate = [{"metric": "runtime_restarts", "value": 1, "sample_size": None}] * 2
    write(source, production_value(observations=duplicate))
    with pytest.raises(ValueError, match="DUPLICATE_OBSERVATION"):
        run([source], tmp_path / "out")

    for bad in ("bad", 1.5, None, True):
        write(source, production_value(observations=[
            {"metric": "runtime_restarts", "value": bad, "sample_size": None}]))
        with pytest.raises(ValueError, match="INVALID_GOVERNED_OBSERVATION_VALUE"):
            run([source], tmp_path / "out")


def test_negative_net_profit_is_aggregate_not_frequency_rate(tmp_path):
    source = tmp_path / "production_trading_report.json"
    write(source, production_value(rejection=0, restart=0, net=-25))
    report = run([source], tmp_path / "out")
    item = next(item for item in report["items"] if "NEGATIVE_NET_PROFIT" in item["id"])
    assert item["evidence"][0]["observed_value"] == -25
    assert item["frequency"] == {"measurement": "not_applicable", "reason": "aggregate_outcome"}
    assert item["business_impact"]["trade_sample_size"] == 4
    assert "rate" not in item["frequency"]


def test_pipeline_uses_event_density_and_preserves_unknown_attribution(tmp_path):
    source = tmp_path / "pipeline_validation_report.json"
    write(source, {"schema_version": "PR254.PIPELINE_VALIDATION_REPORT.1.0",
        "metrics": {"total_lifecycles": 2, "missing_stage_count": 5}})
    report = run([source], tmp_path / "out")
    item = report["items"][0]
    assert item["frequency"] == {"measurement": "event_density",
        "metric": "missing_stage_events_per_lifecycle", "missing_stage_events": 5,
        "total_lifecycles": 2, "value": 2.5}
    assert item["recommended_component"] == "Human Pipeline Investigation"
    assert "unknown" in item["description"].lower()
    assert "rate" not in item["frequency"]


@pytest.mark.parametrize("timestamp, error", [
    ("not-a-time", "INVALID_GENERATED_AT_UTC"),
    ("2026-07-28T12:00:00", "AMBIGUOUS_GENERATED_AT_UTC"),
])
def test_invalid_and_ambiguous_generated_time_fail_before_output(tmp_path, timestamp, error):
    source = tmp_path / "Experts.log"
    source.write_text("unchanged", encoding="utf-8")
    with pytest.raises(ValueError, match=error):
        run([source], tmp_path / "out", generated_at_utc=timestamp)
    assert not (tmp_path / "out").exists()


def test_atomic_failure_preserves_previous_destination_and_cleans_temp(tmp_path, monkeypatch):
    source = tmp_path / "Experts.log"
    source.write_text("unchanged", encoding="utf-8")
    output = tmp_path / "out"
    output.mkdir()
    destination = output / "production_improvement_backlog.json"
    destination.write_text("previous\n", encoding="utf-8")
    (output / "production_improvement_backlog.json.tmp").write_text("stale", encoding="utf-8")

    def fail_replace(source_path, destination_path):
        raise OSError("simulated replace failure")

    monkeypatch.setattr(backlog_module.os, "replace", fail_replace)
    with pytest.raises(OSError, match="simulated"):
        run([source], output)
    assert destination.read_text(encoding="utf-8") == "previous\n"
    assert not (output / "production_improvement_backlog.json.tmp").exists()


def test_sources_are_immutable_and_provenance_only_status_is_explicit(tmp_path):
    source = tmp_path / "Experts.log"
    source.write_bytes(b"maybe an error\n")
    before = source.read_bytes()
    report = run([source], tmp_path / "out")
    assert source.read_bytes() == before
    assert report["items"] == []
    assert report["source_evidence"] == [{"source_ref": "S000001", "basename": "Experts.log",
        "sha256": backlog_module.hashlib.sha256(before).hexdigest(),
        "processing_status": "PROVENANCE_ONLY"}]


def test_rejects_non_authoritative_or_wrong_schema_before_output(tmp_path):
    source = tmp_path / "ideas.json"
    write(source, {})
    with pytest.raises(ValueError, match="NON_AUTHORITATIVE_SOURCE"):
        run([source], tmp_path / "out")
    source = tmp_path / "production_trading_report.json"
    write(source, {"schema_version": "OTHER"})
    with pytest.raises(ValueError, match="INVALID_SOURCE_SCHEMA"):
        run([source], tmp_path / "out")
