"""Governed, offline and advisory-only Production Demo certification (PR256)."""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Mapping, Sequence

SCHEMA_VERSION = "PR256.PRODUCTION_DEMO_CERTIFICATION.2.0"
POLICY_SCHEMA = "PR256.PRODUCTION_DEMO_CERTIFICATION_POLICY.1.0"
MANIFEST_SCHEMA = "PR256.CERTIFICATION_EVIDENCE_MANIFEST.1.0"
SCHEMAS = {"runtime_metrics.json": "PR252.RUNTIME_METRICS.1.0",
           "runtime_daily_summary.json": "PR252.RUNTIME_DAILY_SUMMARY.1.0",
           "production_trading_report.json": "PR253.PRODUCTION_TRADING_REPORT.1.0",
           "pipeline_validation_report.json": "PR254.PIPELINE_VALIDATION_REPORT.1.0",
           "production_improvement_backlog.json": "PR255.PRODUCTION_IMPROVEMENT_BACKLOG.1.1"}
MIN_WINDOW_SECONDS = 604800
MIN_RATE = .99
ARCH_MIN_PROFIT_FACTOR = 1.1
ARCH_MAX_DRAWDOWN_PERCENT = 25.0
BLOCKING_CATEGORIES = frozenset({"RUNTIME_STABILITY", "PIPELINE_COMPLETENESS",
                                 "EXECUTION_RELIABILITY", "DECISION_DELIVERY"})
ALLOWED_BACKLOG_STATUSES = frozenset({"PENDING_HUMAN_REVIEW", "IN_PROGRESS", "RESOLVED"})


def _json(path: Path, schema: str) -> dict[str, object]:
    try: value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc: raise ValueError(f"INVALID_JSON_SOURCE:{path.name}") from exc
    if not isinstance(value, dict) or value.get("schema_version") != schema:
        raise ValueError(f"INVALID_SOURCE_SCHEMA:{path.name}")
    return value


def _sha(path: Path) -> str:
    try: return hashlib.sha256(path.read_bytes()).hexdigest()
    except OSError as exc: raise ValueError(f"UNREADABLE_EVIDENCE:{path.name}") from exc


def _time(value: object, name: str) -> datetime:
    if not isinstance(value, str) or not value: raise ValueError(f"INVALID_TIMESTAMP:{name}")
    try: result = datetime.fromisoformat(value[:-1] + "+00:00" if value.endswith(("Z", "z")) else value)
    except ValueError as exc: raise ValueError(f"INVALID_TIMESTAMP:{name}") from exc
    if result.tzinfo is None or result.utcoffset() is None: raise ValueError(f"AMBIGUOUS_TIMESTAMP:{name}")
    return result.astimezone(timezone.utc)


def _num(value: object, name: str, *, integer: bool = False, nonnegative: bool = False) -> int | float:
    if isinstance(value, bool) or type(value) not in (int, float): raise ValueError(f"INVALID_NUMBER:{name}")
    result = float(value)
    if not math.isfinite(result) or nonnegative and result < 0 or integer and not result.is_integer():
        raise ValueError(f"INVALID_NUMBER:{name}")
    return int(result) if integer else result


def _threshold(policy: Mapping[str, object], name: str, unit: str) -> int | float:
    thresholds = policy.get("approved_thresholds")
    item = thresholds.get(name) if isinstance(thresholds, Mapping) else None
    if not isinstance(item, Mapping) or item.get("unit") != unit: raise ValueError(f"INVALID_POLICY_THRESHOLD:{name}")
    return _num(item.get("value"), f"policy.{name}", integer=name == "required_trade_sample", nonnegative=True)


def _criterion(identifier: str, domain: str, observed: object, threshold: object, passed: bool,
               source: str) -> dict[str, object]:
    return {"id": identifier, "domain": domain, "status": "PASS" if passed else "FAIL",
            "observed": observed, "acceptance_threshold": threshold, "evidence_source": source}


def generate_certification(*, policy: Path | str, evidence_manifest: Path | str,
        runtime_metrics: Path | str, runtime_daily_summaries: Sequence[Path | str],
        production_trading_report: Path | str, pipeline_validation_report: Path | str,
        production_improvement_backlog: Path | str, trade_statistics: Path | str,
        mt5_report_history: Sequence[Path | str], output_directory: Path | str,
        generated_at_utc: str | None = None) -> dict[str, object]:
    """Evaluate one manifest-bound cohort and atomically publish its advisory result."""
    policy_path, manifest_path = Path(policy), Path(evidence_manifest)
    policy_doc, manifest = _json(policy_path, POLICY_SCHEMA), _json(manifest_path, MANIFEST_SCHEMA)
    if not all(isinstance(policy_doc.get(x), str) and policy_doc.get(x) for x in
               ("policy_id", "policy_version", "owner", "approver", "effective_at_utc")):
        raise ValueError("INCOMPLETE_POLICY_AUTHORITY")
    effective = _time(policy_doc["effective_at_utc"], "policy.effective_at_utc")
    trades_required = _threshold(policy_doc, "required_trade_sample", "completed_trades")
    pf_limit = _threshold(policy_doc, "minimum_profit_factor", "ratio")
    dd_limit = _threshold(policy_doc, "maximum_equity_drawdown_percent", "percent")
    if trades_required < 300 or pf_limit < ARCH_MIN_PROFIT_FACTOR or dd_limit > ARCH_MAX_DRAWDOWN_PERCENT:
        raise ValueError("POLICY_OUTSIDE_ARCHITECTURE_SAFETY_BOUNDS")

    daily_paths = [Path(x) for x in runtime_daily_summaries]
    history_paths = [Path(x) for x in mt5_report_history]
    if len(daily_paths) < 7: raise ValueError("INSUFFICIENT_DAILY_SUMMARIES")
    if not history_paths: raise ValueError("MT5_REPORT_HISTORY_REQUIRED")
    named = [Path(runtime_metrics), *daily_paths, Path(production_trading_report),
             Path(pipeline_validation_report), Path(production_improvement_backlog), Path(trade_statistics), *history_paths]
    allowed = set(SCHEMAS) | {"trade_statistics.csv"}
    if any(p.name not in allowed and not p.name.startswith("ReportHistory.") and p.name != "ReportHistory" for p in named):
        raise ValueError("NON_AUTHORITATIVE_SOURCE")
    identities = [(p.name, _sha(p)) for p in named]
    if len(identities) != len(set(identities)): raise ValueError("DUPLICATE_EVIDENCE_SNAPSHOT")

    batch = manifest.get("evidence_batch_id")
    entries = manifest.get("snapshots")
    if not isinstance(batch, str) or not batch or not isinstance(entries, list): raise ValueError("INVALID_EVIDENCE_MANIFEST")
    declared = {(e.get("basename"), e.get("sha256")) for e in entries if isinstance(e, Mapping)}
    if declared != set(identities): raise ValueError("EVIDENCE_MANIFEST_MISMATCH")
    start = _time(manifest.get("observation_window_start_utc"), "manifest.window_start")
    end = _time(manifest.get("observation_window_end_utc"), "manifest.window_end")
    generated_limit = _num(manifest.get("maximum_snapshot_age_seconds"), "maximum_snapshot_age_seconds", integer=True, nonnegative=True)
    if end <= start or (end - start).total_seconds() < MIN_WINDOW_SECONDS: raise ValueError("INSUFFICIENT_OBSERVATION_WINDOW")
    if effective > start: raise ValueError("POLICY_NOT_EFFECTIVE_FOR_WINDOW")

    runtime_path = Path(runtime_metrics); trading_path = Path(production_trading_report)
    pipeline_path = Path(pipeline_validation_report); backlog_path = Path(production_improvement_backlog)
    runtime = _json(runtime_path, SCHEMAS[runtime_path.name])
    daily = [_json(p, SCHEMAS[p.name]) for p in daily_paths]
    trading_report = _json(trading_path, SCHEMAS[trading_path.name])
    pipeline = _json(pipeline_path, SCHEMAS[pipeline_path.name])
    backlog = _json(backlog_path, SCHEMAS[backlog_path.name])
    dated = sorted((date.fromisoformat(str(x.get("summary_date_utc"))), x) for x in daily)
    expected_dates = [start.date() + timedelta(days=x) for x in range((end.date() - start.date()).days)]
    if [x[0] for x in dated] != expected_dates: raise ValueError("DAILY_SUMMARY_CONTINUITY_FAILURE")
    for day, document in dated:
        stamp = _time(document.get("generated_at_utc"), f"daily.{day}.generated_at_utc")
        if not start <= stamp <= end + timedelta(seconds=generated_limit): raise ValueError("DAILY_SUMMARY_OUTSIDE_COHORT")
    if _time(runtime.get("runtime_started_at_utc"), "runtime.started") > start or _time(runtime.get("updated_at_utc"), "runtime.updated") < end:
        raise ValueError("RUNTIME_DOES_NOT_COVER_WINDOW")
    daily_restarts = sum(_num(x.get("runtime_restart_count"), "daily.restart", integer=True, nonnegative=True) for _, x in dated)
    daily_exceptions = sum(_num(x.get("runtime_exception_count"), "daily.exception", integer=True, nonnegative=True) for _, x in dated)
    daily_accepts = sum(_num(x.get("execution_accept_count"), "daily.accepted", integer=True, nonnegative=True) for _, x in dated)
    daily_rejects = sum(_num(x.get("execution_rejection_count"), "daily.rejected", integer=True, nonnegative=True) for _, x in dated)
    if daily_restarts or daily_exceptions: window_clean = False
    else: window_clean = True

    # Every aggregate report timestamp must identify this exact batch and window.
    for name, report in (("trading", trading_report), ("pipeline", pipeline), ("backlog", backlog)):
        if report.get("evidence_batch_id") != batch or report.get("observation_window_start_utc") != manifest.get("observation_window_start_utc") or report.get("observation_window_end_utc") != manifest.get("observation_window_end_utc"):
            raise ValueError(f"TEMPORAL_COHORT_MISMATCH:{name}")
        stamp = _time(report.get("generated_at_utc"), f"{name}.generated_at_utc")
        if not end <= stamp <= end + timedelta(seconds=generated_limit): raise ValueError(f"STALE_OR_PREMATURE_REPORT:{name}")

    descriptors = trading_report.get("source_evidence")
    declared_trading = {(x.get("basename"), x.get("sha256")) for x in descriptors if isinstance(x, Mapping)} if isinstance(descriptors, list) else set()
    raw = [(Path(trade_statistics).name, _sha(Path(trade_statistics))), *((p.name, _sha(p)) for p in history_paths)]
    if any(x not in declared_trading for x in raw): raise ValueError("TRADING_SOURCE_PROVENANCE_MISMATCH")

    execution = trading_report.get("execution"); trading = trading_report.get("trading"); metrics = pipeline.get("metrics"); lifecycles = pipeline.get("lifecycles")
    if not all(isinstance(x, Mapping) for x in (execution, trading, metrics)) or not isinstance(lifecycles, list): raise ValueError("MALFORMED_GOVERNED_REPORT")
    ra = _num(runtime.get("execution_accept_count"), "runtime.accepted", integer=True, nonnegative=True)
    rr = _num(runtime.get("execution_rejection_count"), "runtime.rejected", integer=True, nonnegative=True)
    ta = _num(execution.get("order_accept_count"), "trading.accepted", integer=True, nonnegative=True)
    tr = _num(execution.get("order_rejection_count"), "trading.rejected", integer=True, nonnegative=True)
    if (ra, rr) != (ta, tr) or (ra, rr) != (daily_accepts, daily_rejects):
        raise ValueError("EXECUTION_METRIC_INCONSISTENCY")
    total = _num(metrics.get("total_lifecycles"), "pipeline.total", integer=True, nonnegative=True)
    successful = _num(metrics.get("successful_lifecycles"), "pipeline.successful", integer=True, nonnegative=True)
    reported_rate = _num(metrics.get("pipeline_success_rate"), "pipeline.rate", nonnegative=True)
    missing = _num(metrics.get("missing_stage_count"), "pipeline.missing", integer=True, nonnegative=True)
    computed_success = sum(x.get("complete") is True for x in lifecycles if isinstance(x, Mapping))
    computed_missing = sum(len(x.get("missing_stages", [])) for x in lifecycles if isinstance(x, Mapping))
    canonical_rate = round(successful / total, 6) if total else 0
    if (total != len(lifecycles) or successful != computed_success
            or missing != computed_missing or reported_rate > 1
            or reported_rate != canonical_rate):
        raise ValueError("PIPELINE_METRIC_INCONSISTENCY")
    if missing and successful == total: raise ValueError("PIPELINE_METRIC_INCONSISTENCY")

    items = backlog.get("items")
    if not isinstance(items, list): raise ValueError("INVALID_BACKLOG")
    blockers = []
    for item in items:
        if not isinstance(item, Mapping) or item.get("status") not in ALLOWED_BACKLOG_STATUSES: raise ValueError("INVALID_BACKLOG_STATUS")
        if item["status"] == "RESOLVED":
            resolution = item.get("resolution")
            required = ("approved_by", "verified_by", "resolved_at_utc", "evidence_reference", "implementation_or_verification_artifact")
            if not isinstance(resolution, Mapping) or not all(isinstance(resolution.get(x), str) and resolution.get(x) for x in required):
                raise ValueError("INCOMPLETE_BACKLOG_RESOLUTION")
            _time(resolution["resolved_at_utc"], "backlog.resolved_at_utc")
        elif item.get("category") in BLOCKING_CATEGORIES or item.get("priority") in ("P0", "P1"):
            blockers.append(item)

    submissions = ra + rr; order_rate = ra / submissions if submissions else 0
    trade_count = _num(trading.get("total_trades"), "trading.total", integer=True, nonnegative=True)
    expectancy = _num(trading.get("expectancy"), "trading.expectancy")
    pf = _num(trading.get("profit_factor"), "trading.profit_factor", nonnegative=True)
    drawdown = _num(trading.get("maximum_equity_drawdown_percent"), "trading.drawdown", nonnegative=True)
    if trading.get("drawdown_unit") != "percent" or trading.get("drawdown_basis") != "equity_peak_to_trough": raise ValueError("DRAWDOWN_CONTRACT_MISMATCH")
    duplicates = _num(runtime.get("duplicate_decision_count"), "runtime.duplicates", integer=True, nonnegative=True)
    criteria = [
        _criterion("continuous_seven_day_observation_window", "runtime", {"start_utc": manifest["observation_window_start_utc"], "end_utc": manifest["observation_window_end_utc"], "daily_summaries": len(daily)}, {"minimum_seconds": MIN_WINDOW_SECONDS, "unit": "seconds"}, window_clean, "runtime_daily_summary.json"),
        _criterion("pipeline_success_rate", "pipeline", round(reported_rate, 6), {"value": MIN_RATE, "unit": "ratio"}, total > 0 and reported_rate >= MIN_RATE and missing == 0, "pipeline_validation_report.json"),
        _criterion("order_submission_success", "execution", round(order_rate, 6), {"value": MIN_RATE, "unit": "ratio"}, submissions > 0 and order_rate >= MIN_RATE, "runtime_metrics.json + production_trading_report.json"),
        _criterion("no_duplicate_decision_publication", "execution", duplicates, {"value": 0, "unit": "publications"}, duplicates == 0, "runtime_metrics.json"),
        _criterion("no_blocking_operational_backlog", "execution", len(blockers), {"value": 0, "unit": "items"}, not blockers, "production_improvement_backlog.json"),
        _criterion("completed_trade_sample", "trading", trade_count, {"value": trades_required, "unit": "completed_trades"}, trade_count >= trades_required, "production_trading_report.json"),
        _criterion("positive_expectancy", "trading", expectancy, {"exclusive_minimum": 0, "unit": "report_currency_per_trade"}, expectancy > 0, "production_trading_report.json"),
        _criterion("profit_factor", "trading", pf, {"value": pf_limit, "unit": "ratio"}, pf >= pf_limit, "production_trading_report.json"),
        _criterion("maximum_equity_drawdown_percent", "trading", drawdown, {"value": dd_limit, "unit": "percent", "basis": "equity_peak_to_trough"}, drawdown <= dd_limit, "production_trading_report.json")]
    hard = any(x["status"] == "FAIL" and x["domain"] != "trading" for x in criteria)
    result = "NOT READY" if hard else ("READY FOR EXTENDED DEMO" if any(x["status"] == "FAIL" for x in criteria) else "READY FOR LIVE REVIEW")
    generated = _time(generated_at_utc or datetime.now(timezone.utc).isoformat(), "certification.generated_at_utc")
    sources = sorted(({"basename": p.name, "sha256": digest, "role": "provenance_only" if p.name == "trade_statistics.csv" or p.name.startswith("ReportHistory") else "governed_measurement"} for p, (_, digest) in zip(named, identities)), key=lambda x: (x["basename"], x["sha256"]))
    report = {"schema_version": SCHEMA_VERSION, "generated_at_utc": generated.isoformat().replace("+00:00", "Z"),
        "certification_result": result, "advisory_only": True, "human_approval_required_before_live_trading": True,
        "evidence_batch_id": batch, "observation_window_start_utc": manifest["observation_window_start_utc"],
        "observation_window_end_utc": manifest["observation_window_end_utc"],
        "policy_authority": {"policy_id": policy_doc["policy_id"], "policy_version": policy_doc["policy_version"],
            "owner": policy_doc["owner"], "approver": policy_doc["approver"], "effective_at_utc": policy_doc["effective_at_utc"], "sha256": _sha(policy_path)},
        "raw_trade_evidence_role": "provenance_only; PR253 is the sole governed analytics authority",
        "source_evidence": sources, "criteria": criteria}
    output = Path(output_directory); output.mkdir(parents=True, exist_ok=True)
    destination = output / "production_demo_certification.json"; temporary = destination.with_name(destination.name + ".tmp")
    temporary.unlink(missing_ok=True)
    try:
        with temporary.open("wb") as stream: stream.write((json.dumps(report, indent=2, sort_keys=True) + "\n").encode()); stream.flush(); os.fsync(stream.fileno())
        os.replace(temporary, destination)
    finally: temporary.unlink(missing_ok=True)
    return report


def main(argv: Sequence[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="Generate governed PR256 Production Demo certification")
    for name in ("policy", "evidence-manifest", "runtime-metrics", "production-trading-report", "pipeline-validation-report", "production-improvement-backlog", "trade-statistics", "output-directory"): p.add_argument(f"--{name}", required=True)
    p.add_argument("--runtime-daily-summary", action="append", required=True, dest="runtime_daily_summaries")
    p.add_argument("--mt5-report-history", action="append", required=True); p.add_argument("--generated-at-utc")
    generate_certification(**vars(p.parse_args(argv))); return 0

if __name__ == "__main__": raise SystemExit(main())
