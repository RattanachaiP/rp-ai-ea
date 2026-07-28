import json

import pytest

from analysis.production_improvement_backlog import SCHEMA_VERSION, generate_backlog


def write(path, value):
    path.write_text(json.dumps(value), encoding="utf-8")


def production_report(path):
    write(path, {"schema_version": "PR253.PRODUCTION_TRADING_REPORT.1.0",
        "trading": {"total_trades": 4, "net_profit": -25},
        "measurable_observations": [
            {"metric": "execution_rejections", "value": 2, "sample_size": 10},
            {"metric": "runtime_restarts", "value": 1, "sample_size": None},
            {"metric": "win_rate", "value": 0.25, "sample_size": 4},
        ]})


def test_builds_only_measurable_pending_human_items(tmp_path):
    production = tmp_path / "production_trading_report.json"
    pipeline = tmp_path / "pipeline_validation_report.json"
    production_report(production)
    write(pipeline, {"schema_version": "PR254.PIPELINE_VALIDATION_REPORT.1.0",
        "metrics": {"total_lifecycles": 5, "missing_stage_count": 3}})
    report = generate_backlog(evidence=[production, pipeline], output_directory=tmp_path / "out",
                              generated_at_utc="2026-07-28T12:00:00Z")
    assert report["schema_version"] == SCHEMA_VERSION
    assert report["human_approval_required"] is True
    assert [item["id"] for item in report["items"]] == [
        "PR255-EXECUTION_REJECTIONS", "PR255-PIPELINE_MISSING_STAGES",
        "PR255-NEGATIVE_NET_PROFIT", "PR255-RUNTIME_RESTARTS"]
    rejected = report["items"][0]
    assert rejected["frequency"] == {"occurrences": 2, "sample_size": 10, "rate": 0.2}
    assert rejected["reproducibility"]["classification"] == "REPEATED"
    assert rejected["status"] == "PENDING_HUMAN_REVIEW"
    assert rejected["recommended_component"] == "Execution"
    assert json.loads((tmp_path / "out" / "production_improvement_backlog.json").read_text()) == report
    assert not list((tmp_path / "out").glob("*.tmp"))


def test_zero_and_favorable_observations_do_not_create_speculative_items(tmp_path):
    source = tmp_path / "production_trading_report.json"
    write(source, {"schema_version": "PR253.PRODUCTION_TRADING_REPORT.1.0",
        "trading": {"total_trades": 2, "net_profit": 10},
        "measurable_observations": [{"metric": "execution_rejections", "value": 0,
                                      "sample_size": 5}]})
    report = generate_backlog(evidence=[source], output_directory=tmp_path / "out")
    assert report["items"] == []


def test_rejects_non_authoritative_or_wrong_schema_before_output(tmp_path):
    source = tmp_path / "ideas.json"
    write(source, {})
    with pytest.raises(ValueError, match="NON_AUTHORITATIVE_SOURCE"):
        generate_backlog(evidence=[source], output_directory=tmp_path / "out")
    assert not (tmp_path / "out").exists()

    source = tmp_path / "production_trading_report.json"
    write(source, {"schema_version": "OTHER"})
    with pytest.raises(ValueError, match="INVALID_SOURCE_SCHEMA"):
        generate_backlog(evidence=[source], output_directory=tmp_path / "out")


def test_raw_authoritative_evidence_is_provenanced_not_inferred(tmp_path):
    log = tmp_path / "Experts.log"
    log.write_text("maybe an error\n", encoding="utf-8")
    report = generate_backlog(evidence=[log], output_directory=tmp_path / "out")
    assert report["items"] == []
    assert report["source_evidence"][0]["basename"] == "Experts.log"
