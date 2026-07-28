import hashlib
import json
import os
from datetime import datetime, timedelta, timezone

import pytest

import analysis.production_demo_certification as module
from analysis.production_demo_certification import generate_certification


def dump(path, value):
    path.parent.mkdir(parents=True, exist_ok=True); path.write_text(json.dumps(value), encoding="utf-8")


def fixture(tmp_path, *, policy_values=None, missing_day=False, execution=(990, 10),
            trading_execution=None, pipeline_success=99, pipeline_missing=False,
            duplicates=0, items=None, drawdown_unit="percent", report_batch="BATCH-1"):
    start = datetime(2026, 7, 21, tzinfo=timezone.utc); end = start + timedelta(days=7)
    policy = tmp_path / "certification_policy.json"
    values = {"required_trade_sample": {"value": 300, "unit": "completed_trades"},
              "minimum_profit_factor": {"value": 1.2, "unit": "ratio"},
              "maximum_equity_drawdown_percent": {"value": 20, "unit": "percent"}}
    values.update(policy_values or {})
    dump(policy, {"schema_version": module.POLICY_SCHEMA, "policy_id": "PROD-DEMO", "policy_version": "1",
        "owner": "Risk Committee", "approver": "Chief Risk Officer", "effective_at_utc": "2026-07-01T00:00:00Z",
        "approved_thresholds": values})
    runtime = tmp_path / "runtime_metrics.json"; accepted, rejected = execution
    dump(runtime, {"schema_version": module.SCHEMAS[runtime.name], "runtime_started_at_utc": "2026-07-20T00:00:00Z",
        "updated_at_utc": "2026-07-28T00:00:00Z", "execution_accept_count": accepted,
        "execution_rejection_count": rejected, "duplicate_decision_count": duplicates})
    daily = []
    for offset in range(7):
        if missing_day and offset == 3: continue
        path = tmp_path / f"day-{offset}" / "runtime_daily_summary.json"
        stamp = start + timedelta(days=offset + 1)
        dump(path, {"schema_version": module.SCHEMAS[path.name], "summary_date_utc": (start + timedelta(days=offset)).date().isoformat(),
            "generated_at_utc": stamp.isoformat().replace("+00:00", "Z"), "runtime_restart_count": 0,
            "runtime_exception_count": 0, "execution_accept_count": accepted if offset == 0 else 0,
            "execution_rejection_count": rejected if offset == 0 else 0})
        daily.append(path)
    trades = tmp_path / "trade_statistics.csv"; trades.write_text("trade_uuid,profit\n", encoding="utf-8")
    history = tmp_path / "ReportHistory.csv"; history.write_text("MT5\n", encoding="utf-8")
    texec = trading_execution or execution
    trading = tmp_path / "production_trading_report.json"
    raw_desc = [{"basename": x.name, "sha256": hashlib.sha256(x.read_bytes()).hexdigest()} for x in (trades, history)]
    cohort = {"evidence_batch_id": report_batch, "observation_window_start_utc": "2026-07-21T00:00:00Z",
              "observation_window_end_utc": "2026-07-28T00:00:00Z", "generated_at_utc": "2026-07-28T01:00:00Z"}
    dump(trading, {"schema_version": module.SCHEMAS[trading.name], **cohort, "source_evidence": raw_desc,
        "execution": {"order_accept_count": texec[0], "order_rejection_count": texec[1]},
        "trading": {"total_trades": 300, "expectancy": 1, "profit_factor": 1.3,
                    "maximum_equity_drawdown_percent": 10, "drawdown_unit": drawdown_unit,
                    "drawdown_basis": "equity_peak_to_trough"}})
    pipeline = tmp_path / "pipeline_validation_report.json"
    lifecycles = [{"complete": i < pipeline_success, "missing_stages": (["ANALYTICS"] if pipeline_missing and i == 99 else [])} for i in range(100)]
    successful = sum(x["complete"] for x in lifecycles); missing = sum(len(x["missing_stages"]) for x in lifecycles)
    dump(pipeline, {"schema_version": module.SCHEMAS[pipeline.name], **cohort, "metrics": {
        "total_lifecycles": 100, "successful_lifecycles": successful,
        "pipeline_success_rate": round(successful / 100, 6), "missing_stage_count": missing}, "lifecycles": lifecycles})
    backlog = tmp_path / "production_improvement_backlog.json"
    dump(backlog, {"schema_version": module.SCHEMAS[backlog.name], **cohort, "items": items or []})
    manifest = tmp_path / "evidence_manifest.json"
    evidence = [runtime, *daily, trading, pipeline, backlog, trades, history]
    dump(manifest, {"schema_version": module.MANIFEST_SCHEMA, "evidence_batch_id": "BATCH-1",
        "observation_window_start_utc": "2026-07-21T00:00:00Z", "observation_window_end_utc": "2026-07-28T00:00:00Z",
        "maximum_snapshot_age_seconds": 7200, "snapshots": [{"basename": x.name, "sha256": hashlib.sha256(x.read_bytes()).hexdigest()} for x in evidence]})
    return {"policy": policy, "evidence_manifest": manifest, "runtime_metrics": runtime,
        "runtime_daily_summaries": daily, "production_trading_report": trading,
        "pipeline_validation_report": pipeline, "production_improvement_backlog": backlog,
        "trade_statistics": trades, "mt5_report_history": [history], "output_directory": tmp_path / "out",
        "generated_at_utc": "2026-07-28T02:00:00Z"}


def test_ready_is_policy_governed_temporally_coherent_and_advisory(tmp_path):
    report = generate_certification(**fixture(tmp_path))
    assert report["certification_result"] == "READY FOR LIVE REVIEW"
    assert report["policy_authority"]["sha256"]
    assert report["advisory_only"] is report["human_approval_required_before_live_trading"] is True
    assert report["raw_trade_evidence_role"].startswith("provenance_only")
    assert [x["basename"] for x in report["source_evidence"]] == sorted(x["basename"] for x in report["source_evidence"])


@pytest.mark.parametrize("values", [
    {"minimum_profit_factor": {"value": 0, "unit": "ratio"}},
    {"maximum_equity_drawdown_percent": {"value": 1000, "unit": "percent"}},
    {"required_trade_sample": {"value": 300.5, "unit": "completed_trades"}},
    {"minimum_profit_factor": {"value": float("nan"), "unit": "ratio"}},
    {"minimum_profit_factor": {"value": True, "unit": "ratio"}},
])
def test_lenient_or_invalid_policy_threshold_is_rejected(tmp_path, values):
    with pytest.raises(ValueError): generate_certification(**fixture(tmp_path, policy_values=values))


def test_policy_provenance_and_manifest_binding_reject_tampering(tmp_path):
    args = fixture(tmp_path); args["runtime_metrics"].write_text("changed")
    with pytest.raises(ValueError, match="EVIDENCE_MANIFEST_MISMATCH"): generate_certification(**args)


def test_seven_day_continuity_and_missing_daily_summary(tmp_path):
    with pytest.raises(ValueError, match="INSUFFICIENT_DAILY_SUMMARIES"): generate_certification(**fixture(tmp_path, missing_day=True))


def test_temporal_mismatch_across_reports(tmp_path):
    with pytest.raises(ValueError, match="TEMPORAL_COHORT_MISMATCH"): generate_certification(**fixture(tmp_path, report_batch="OTHER"))


def test_execution_reports_must_reconcile(tmp_path):
    with pytest.raises(ValueError, match="EXECUTION_METRIC_INCONSISTENCY"): generate_certification(**fixture(tmp_path, trading_execution=(989, 11)))


def test_pipeline_internal_inconsistency_fails_closed(tmp_path):
    args = fixture(tmp_path); value = json.loads(args["pipeline_validation_report"].read_text()); value["metrics"]["pipeline_success_rate"] = .5
    dump(args["pipeline_validation_report"], value)
    # Refresh only the manifest: this proves the internal check, not manifest tamper detection.
    manifest = json.loads(args["evidence_manifest"].read_text());
    for entry in manifest["snapshots"]:
        if entry["basename"] == "pipeline_validation_report.json": entry["sha256"] = hashlib.sha256(args["pipeline_validation_report"].read_bytes()).hexdigest()
    dump(args["evidence_manifest"], manifest)
    with pytest.raises(ValueError, match="PIPELINE_METRIC_INCONSISTENCY"): generate_certification(**args)


def test_duplicate_semantics_names_decision_publication_not_lifecycle(tmp_path):
    report = generate_certification(**fixture(tmp_path, duplicates=1))
    failed = [x["id"] for x in report["criteria"] if x["status"] == "FAIL"]
    assert failed == ["no_duplicate_decision_publication"] and report["certification_result"] == "NOT READY"


@pytest.mark.parametrize("item,error", [
    ({"status": "MAGIC", "category": "RUNTIME_STABILITY", "priority": "P1"}, "INVALID_BACKLOG_STATUS"),
    ({"status": "RESOLVED", "category": "RUNTIME_STABILITY", "priority": "P1"}, "INCOMPLETE_BACKLOG_RESOLUTION"),
])
def test_backlog_status_and_resolution_are_governed(tmp_path, item, error):
    with pytest.raises(ValueError, match=error): generate_certification(**fixture(tmp_path, items=[item]))


@pytest.mark.parametrize("category", ["RUNTIME_STABILITY", "PIPELINE_COMPLETENESS", "DECISION_DELIVERY"])
def test_unresolved_non_execution_operational_backlog_blocks(tmp_path, category):
    report = generate_certification(**fixture(tmp_path, items=[{"status": "PENDING_HUMAN_REVIEW", "category": category, "priority": "P1"}]))
    assert report["certification_result"] == "NOT READY"


def test_zero_execution_denominator_is_not_ready(tmp_path):
    report = generate_certification(**fixture(tmp_path, execution=(0, 0)))
    assert next(x for x in report["criteria"] if x["id"] == "order_submission_success")["status"] == "FAIL"


def test_duplicate_report_history_snapshots_are_rejected(tmp_path):
    args = fixture(tmp_path); args["mt5_report_history"] *= 2
    with pytest.raises(ValueError, match="DUPLICATE_EVIDENCE_SNAPSHOT"): generate_certification(**args)


def test_drawdown_unit_mismatch_fails(tmp_path):
    with pytest.raises(ValueError, match="DRAWDOWN_CONTRACT_MISMATCH"): generate_certification(**fixture(tmp_path, drawdown_unit="currency"))


@pytest.mark.parametrize("stamp,error", [("bad", "INVALID_TIMESTAMP"), ("2026-07-28T02:00:00", "AMBIGUOUS_TIMESTAMP")])
def test_invalid_generated_timestamp(tmp_path, stamp, error):
    args = fixture(tmp_path); args["generated_at_utc"] = stamp
    with pytest.raises(ValueError, match=error): generate_certification(**args)


def test_atomic_failure_preserves_previous_and_cleans_stale_temp(tmp_path, monkeypatch):
    args = fixture(tmp_path); out = args["output_directory"]; out.mkdir(); destination = out / "production_demo_certification.json"
    destination.write_text("previous\n"); (out / "production_demo_certification.json.tmp").write_text("stale")
    monkeypatch.setattr(module.os, "replace", lambda *_: (_ for _ in ()).throw(OSError("replace")))
    with pytest.raises(OSError): generate_certification(**args)
    assert destination.read_text() == "previous\n" and not (out / "production_demo_certification.json.tmp").exists()


def test_sources_remain_immutable(tmp_path):
    args = fixture(tmp_path); before = {p: p.read_bytes() for p in [args["runtime_metrics"], *args["runtime_daily_summaries"], args["trade_statistics"], *args["mt5_report_history"]]}
    generate_certification(**args)
    assert all(path.read_bytes() == payload for path, payload in before.items())
