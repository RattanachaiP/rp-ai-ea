import hashlib
import json

import pytest

from analysis.production_demo_certification import generate_certification


def write_json(path, value):
    path.write_text(json.dumps(value), encoding="utf-8")


def evidence(tmp_path, *, uptime=604800, accepted=990, rejected=10, duplicates=0,
             pipeline_rate=.99, missing=0, trades=300, expectancy=1, pf=1.5,
             drawdown=10, backlog_items=None):
    runtime = tmp_path / "runtime_metrics.json"
    daily = tmp_path / "runtime_daily_summary.json"
    trade_csv = tmp_path / "trade_statistics.csv"
    history = tmp_path / "ReportHistory.csv"
    trading_path = tmp_path / "production_trading_report.json"
    pipeline = tmp_path / "pipeline_validation_report.json"
    backlog = tmp_path / "production_improvement_backlog.json"
    write_json(runtime, {"schema_version": "PR252.RUNTIME_METRICS.1.0",
        "runtime_uptime_seconds": uptime, "runtime_restart_count": 0,
        "runtime_exception_count": 0, "execution_accept_count": accepted,
        "execution_rejection_count": rejected, "duplicate_decision_count": duplicates})
    write_json(daily, {"schema_version": "PR252.RUNTIME_DAILY_SUMMARY.1.0"})
    trade_csv.write_text("trade_uuid,profit\n", encoding="utf-8")
    history.write_text("MT5 export\n", encoding="utf-8")
    descriptors = [{"basename": path.name, "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}
                   for path in (runtime, daily, trade_csv, history)]
    write_json(trading_path, {"schema_version": "PR253.PRODUCTION_TRADING_REPORT.1.0",
        "source_evidence": descriptors,
        "trading": {"total_trades": trades, "expectancy": expectancy,
                    "profit_factor": pf, "max_drawdown": drawdown}, "execution": {}})
    write_json(pipeline, {"schema_version": "PR254.PIPELINE_VALIDATION_REPORT.1.0",
        "metrics": {"total_lifecycles": 1000, "pipeline_success_rate": pipeline_rate,
                    "missing_stage_count": missing}})
    write_json(backlog, {"schema_version": "PR255.PRODUCTION_IMPROVEMENT_BACKLOG.1.1",
        "items": backlog_items or []})
    return dict(runtime_metrics=runtime, runtime_daily_summary=daily,
        production_trading_report=trading_path, pipeline_validation_report=pipeline,
        production_improvement_backlog=backlog, trade_statistics=trade_csv,
        mt5_report_history=[history], output_directory=tmp_path / "out",
        profit_factor_threshold=1.4, maximum_drawdown_limit=20,
        generated_at_utc="2026-07-28T12:00:00Z")


def test_live_review_requires_every_objective_gate_and_is_advisory(tmp_path):
    report = generate_certification(**evidence(tmp_path))
    assert report["certification_result"] == "READY FOR LIVE REVIEW"
    assert {item["status"] for item in report["criteria"]} == {"PASS"}
    assert report["advisory_only"] is True
    assert report["human_approval_required_before_live_trading"] is True
    assert json.loads((tmp_path / "out" / "production_demo_certification.json").read_text()) == report


def test_safe_runtime_with_insufficient_trading_evidence_is_extended_demo(tmp_path):
    report = generate_certification(**evidence(tmp_path, trades=299, expectancy=-1, pf=.5, drawdown=30))
    assert report["certification_result"] == "READY FOR EXTENDED DEMO"
    assert {item["id"] for item in report["criteria"] if item["status"] == "FAIL"} == {
        "completed_trade_sample", "positive_expectancy", "profit_factor", "maximum_drawdown"}


@pytest.mark.parametrize("change", [
    {"uptime": 604799}, {"accepted": 989, "rejected": 11},
    {"missing": 1}, {"pipeline_rate": .989999}, {"duplicates": 1},
])
def test_operational_failure_is_not_ready(tmp_path, change):
    report = generate_certification(**evidence(tmp_path, **change))
    assert report["certification_result"] == "NOT READY"


def test_unresolved_execution_backlog_item_is_not_ready(tmp_path):
    item = {"category": "EXECUTION_RELIABILITY", "status": "PENDING_HUMAN_REVIEW"}
    report = generate_certification(**evidence(tmp_path, backlog_items=[item]))
    assert report["certification_result"] == "NOT READY"


def test_thresholds_are_human_supplied_and_sample_cannot_drop_below_300(tmp_path):
    arguments = evidence(tmp_path)
    arguments["required_trade_sample"] = 299
    with pytest.raises(ValueError, match="REQUIRED_TRADE_SAMPLE_BELOW_300"):
        generate_certification(**arguments)


def test_raw_evidence_must_match_trading_report_provenance(tmp_path):
    arguments = evidence(tmp_path)
    arguments["trade_statistics"].write_text("changed", encoding="utf-8")
    with pytest.raises(ValueError, match="TRADING_SOURCE_PROVENANCE_MISMATCH:trade_statistics.csv"):
        generate_certification(**arguments)


def test_only_authoritative_evidence_names_are_accepted(tmp_path):
    arguments = evidence(tmp_path)
    renamed = tmp_path / "trades.csv"
    renamed.write_bytes(arguments["trade_statistics"].read_bytes())
    arguments["trade_statistics"] = renamed
    with pytest.raises(ValueError, match="NON_AUTHORITATIVE_SOURCE"):
        generate_certification(**arguments)
