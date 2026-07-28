"""Offline, advisory Production Demo certification for PR256.

The certifier evaluates immutable evidence snapshots.  It neither imports nor
invokes runtime, AI, execution, strategy, risk, or promotion components.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Mapping, Sequence


SCHEMA_VERSION = "PR256.PRODUCTION_DEMO_CERTIFICATION.1.0"
RUNTIME_SCHEMA = "PR252.RUNTIME_METRICS.1.0"
DAILY_SCHEMA = "PR252.RUNTIME_DAILY_SUMMARY.1.0"
TRADING_SCHEMA = "PR253.PRODUCTION_TRADING_REPORT.1.0"
PIPELINE_SCHEMA = "PR254.PIPELINE_VALIDATION_REPORT.1.0"
BACKLOG_SCHEMA = "PR255.PRODUCTION_IMPROVEMENT_BACKLOG.1.1"
MINIMUM_UPTIME_SECONDS = 7 * 24 * 60 * 60
MINIMUM_SUCCESS_RATE = 0.99
HARD_DOMAINS = frozenset({"runtime", "pipeline", "execution"})


def _read(path: Path, schema: str) -> dict[str, object]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"INVALID_JSON_SOURCE:{path.name}") from exc
    if not isinstance(value, dict) or value.get("schema_version") != schema:
        raise ValueError(f"INVALID_SOURCE_SCHEMA:{path.name}")
    return value


def _number(value: object, name: str, *, nonnegative: bool = False) -> float:
    if isinstance(value, bool):
        raise ValueError(f"INVALID_METRIC:{name}")
    try:
        result = float(value)  # type: ignore[arg-type]
    except (TypeError, ValueError) as exc:
        raise ValueError(f"INVALID_METRIC:{name}") from exc
    if not math.isfinite(result) or (nonnegative and result < 0):
        raise ValueError(f"INVALID_METRIC:{name}")
    return result


def _integer(value: object, name: str) -> int:
    result = _number(value, name, nonnegative=True)
    if not result.is_integer():
        raise ValueError(f"INVALID_METRIC:{name}")
    return int(result)


def _digest(path: Path) -> str:
    try:
        return hashlib.sha256(path.read_bytes()).hexdigest()
    except OSError as exc:
        raise ValueError(f"UNREADABLE_EVIDENCE:{path.name}") from exc


def _criterion(identifier: str, domain: str, observed: object, threshold: object,
               passed: bool, evidence: Sequence[dict[str, str]]) -> dict[str, object]:
    return {"id": identifier, "domain": domain, "status": "PASS" if passed else "FAIL",
            "observed": observed, "acceptance_threshold": threshold,
            "evidence": list(evidence)}


def generate_certification(*, runtime_metrics: Path | str,
                           runtime_daily_summary: Path | str,
                           production_trading_report: Path | str,
                           pipeline_validation_report: Path | str,
                           production_improvement_backlog: Path | str,
                           trade_statistics: Path | str,
                           mt5_report_history: Sequence[Path | str],
                           output_directory: Path | str,
                           profit_factor_threshold: float,
                           maximum_drawdown_limit: float,
                           required_trade_sample: int = 300,
                           generated_at_utc: str | None = None) -> dict[str, object]:
    """Evaluate governed evidence and atomically write one advisory report."""
    if required_trade_sample < 300:
        raise ValueError("REQUIRED_TRADE_SAMPLE_BELOW_300")
    pf_limit = _number(profit_factor_threshold, "profit_factor_threshold", nonnegative=True)
    dd_limit = _number(maximum_drawdown_limit, "maximum_drawdown_limit", nonnegative=True)
    if not mt5_report_history:
        raise ValueError("MT5_REPORT_HISTORY_REQUIRED")

    paths = {
        "runtime": Path(runtime_metrics), "daily": Path(runtime_daily_summary),
        "trading": Path(production_trading_report), "pipeline": Path(pipeline_validation_report),
        "backlog": Path(production_improvement_backlog), "trades": Path(trade_statistics),
    }
    history = [Path(item) for item in mt5_report_history]
    expected_names = {"runtime": "runtime_metrics.json", "daily": "runtime_daily_summary.json",
        "trading": "production_trading_report.json", "pipeline": "pipeline_validation_report.json",
        "backlog": "production_improvement_backlog.json", "trades": "trade_statistics.csv"}
    for role, expected in expected_names.items():
        if paths[role].name != expected:
            raise ValueError(f"NON_AUTHORITATIVE_SOURCE:{paths[role].name}")
    if any(item.name != "ReportHistory" and not item.name.startswith("ReportHistory.") for item in history):
        raise ValueError("NON_AUTHORITATIVE_MT5_HISTORY")

    runtime = _read(paths["runtime"], RUNTIME_SCHEMA)
    _read(paths["daily"], DAILY_SCHEMA)
    trading_report = _read(paths["trading"], TRADING_SCHEMA)
    pipeline_report = _read(paths["pipeline"], PIPELINE_SCHEMA)
    backlog = _read(paths["backlog"], BACKLOG_SCHEMA)
    digests = {role: _digest(path) for role, path in paths.items()}
    history_digests = [_digest(path) for path in history]

    # The aggregate report must be cryptographically tied to every raw trading input.
    descriptors = trading_report.get("source_evidence")
    if not isinstance(descriptors, list):
        raise ValueError("MISSING_TRADING_SOURCE_PROVENANCE")
    declared = {(item.get("basename"), item.get("sha256")) for item in descriptors if isinstance(item, Mapping)}
    for role in ("runtime", "daily", "trades"):
        if (paths[role].name, digests[role]) not in declared:
            raise ValueError(f"TRADING_SOURCE_PROVENANCE_MISMATCH:{paths[role].name}")
    for path, digest in zip(history, history_digests):
        if (path.name, digest) not in declared:
            raise ValueError(f"TRADING_SOURCE_PROVENANCE_MISMATCH:{path.name}")

    metrics = pipeline_report.get("metrics")
    trading = trading_report.get("trading")
    execution = trading_report.get("execution")
    items = backlog.get("items")
    if not all(isinstance(value, Mapping) for value in (metrics, trading, execution)) or not isinstance(items, list):
        raise ValueError("MALFORMED_GOVERNED_REPORT")
    metrics, trading, execution = dict(metrics), dict(trading), dict(execution)
    uptime = _number(runtime.get("runtime_uptime_seconds"), "runtime_uptime_seconds", nonnegative=True)
    exceptions = _integer(runtime.get("runtime_exception_count"), "runtime_exception_count")
    restarts = _integer(runtime.get("runtime_restart_count"), "runtime_restart_count")
    total_lifecycles = _integer(metrics.get("total_lifecycles"), "total_lifecycles")
    pipeline_rate = _number(metrics.get("pipeline_success_rate"), "pipeline_success_rate", nonnegative=True)
    missing_stages = _integer(metrics.get("missing_stage_count"), "missing_stage_count")
    accepted = _integer(runtime.get("execution_accept_count"), "execution_accept_count")
    rejected = _integer(runtime.get("execution_rejection_count"), "execution_rejection_count")
    duplicates = _integer(runtime.get("duplicate_decision_count"), "duplicate_decision_count")
    execution_total = accepted + rejected
    order_rate = accepted / execution_total if execution_total else 0.0
    trades = _integer(trading.get("total_trades"), "total_trades")
    expectancy = _number(trading.get("expectancy"), "expectancy")
    profit_factor_raw = trading.get("profit_factor")
    profit_factor = math.inf if profit_factor_raw == "INFINITE" else _number(profit_factor_raw, "profit_factor", nonnegative=True)
    drawdown = _number(trading.get("max_drawdown"), "max_drawdown", nonnegative=True)
    unresolved = [item for item in items if isinstance(item, Mapping) and item.get("status") != "RESOLVED"]
    unresolved_execution = [item for item in unresolved if item.get("category") == "EXECUTION_RELIABILITY"]
    runtime_ref = [{"source": "runtime_metrics.json", "pointer": "/runtime_uptime_seconds"}]
    pipeline_ref = [{"source": "pipeline_validation_report.json", "pointer": "/metrics"}]
    trading_ref = [{"source": "production_trading_report.json", "pointer": "/trading"},
                   {"source": "trade_statistics.csv", "pointer": "completed_trade_rows"},
                   {"source": "MT5 ReportHistory", "pointer": "completed_trade_rows"}]
    criteria = [
        _criterion("continuous_operation", "runtime", uptime, MINIMUM_UPTIME_SECONDS, uptime >= MINIMUM_UPTIME_SECONDS, runtime_ref),
        _criterion("no_unexplained_runtime_crash", "runtime", {"restarts": restarts, "exceptions": exceptions}, "0 restarts and 0 exceptions", restarts == 0 and exceptions == 0, runtime_ref),
        _criterion("no_pipeline_interruption", "pipeline", missing_stages, 0, missing_stages == 0, pipeline_ref),
        _criterion("pipeline_success_rate", "pipeline", pipeline_rate, MINIMUM_SUCCESS_RATE, total_lifecycles > 0 and pipeline_rate >= MINIMUM_SUCCESS_RATE, pipeline_ref),
        _criterion("order_submission_success", "execution", round(order_rate, 6), MINIMUM_SUCCESS_RATE, execution_total > 0 and order_rate >= MINIMUM_SUCCESS_RATE, runtime_ref),
        _criterion("no_unresolved_execution_failures", "execution", len(unresolved_execution), 0, not unresolved_execution, [{"source": "production_improvement_backlog.json", "pointer": "/items"}]),
        _criterion("no_duplicate_lifecycle", "execution", duplicates, 0, duplicates == 0, runtime_ref),
        _criterion("completed_trade_sample", "trading", trades, required_trade_sample, trades >= required_trade_sample, trading_ref),
        _criterion("positive_expectancy", "trading", expectancy, "> 0", expectancy > 0, trading_ref),
        _criterion("profit_factor", "trading", "INFINITE" if math.isinf(profit_factor) else profit_factor, pf_limit, profit_factor >= pf_limit, trading_ref),
        _criterion("maximum_drawdown", "trading", drawdown, dd_limit, drawdown <= dd_limit, trading_ref),
    ]
    hard_failed = any(item["status"] == "FAIL" and item["domain"] in HARD_DOMAINS for item in criteria)
    trading_failed = any(item["status"] == "FAIL" and item["domain"] == "trading" for item in criteria)
    result = "NOT READY" if hard_failed else ("READY FOR EXTENDED DEMO" if trading_failed else "READY FOR LIVE REVIEW")
    now = generated_at_utc or datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    try:
        generated = datetime.fromisoformat(now[:-1] + "+00:00" if now.endswith(("Z", "z")) else now)
    except ValueError as exc:
        raise ValueError("INVALID_GENERATED_AT_UTC") from exc
    if generated.tzinfo is None or generated.utcoffset() is None:
        raise ValueError("AMBIGUOUS_GENERATED_AT_UTC")
    sources = [{"basename": paths[role].name, "sha256": digests[role]} for role in paths]
    sources.extend({"basename": path.name, "sha256": digest} for path, digest in zip(history, history_digests))
    report = {"schema_version": SCHEMA_VERSION,
        "generated_at_utc": generated.astimezone(timezone.utc).isoformat().replace("+00:00", "Z"),
        "certification_result": result, "advisory_only": True,
        "human_approval_required_before_live_trading": True,
        "thresholds": {"minimum_uptime_seconds": MINIMUM_UPTIME_SECONDS,
            "minimum_pipeline_success_rate": MINIMUM_SUCCESS_RATE,
            "minimum_order_submission_success_rate": MINIMUM_SUCCESS_RATE,
            "required_trade_sample": required_trade_sample,
            "profit_factor_threshold": pf_limit, "maximum_drawdown_limit": dd_limit},
        "source_evidence": sources, "criteria": criteria}
    output = Path(output_directory); output.mkdir(parents=True, exist_ok=True)
    destination = output / "production_demo_certification.json"
    temporary = destination.with_name(destination.name + ".tmp")
    payload = (json.dumps(report, indent=2, sort_keys=True) + "\n").encode()
    try:
        with temporary.open("wb") as stream:
            stream.write(payload); stream.flush(); os.fsync(stream.fileno())
        os.replace(temporary, destination)
    finally:
        temporary.unlink(missing_ok=True)
    return report


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Generate the advisory PR256 Production Demo certification")
    parser.add_argument("--runtime-metrics", required=True); parser.add_argument("--runtime-daily-summary", required=True)
    parser.add_argument("--production-trading-report", required=True); parser.add_argument("--pipeline-validation-report", required=True)
    parser.add_argument("--production-improvement-backlog", required=True); parser.add_argument("--trade-statistics", required=True)
    parser.add_argument("--mt5-report-history", action="append", required=True); parser.add_argument("--output-directory", required=True)
    parser.add_argument("--profit-factor-threshold", type=float, required=True); parser.add_argument("--maximum-drawdown-limit", type=float, required=True)
    parser.add_argument("--required-trade-sample", type=int, default=300); parser.add_argument("--generated-at-utc")
    args = parser.parse_args(argv)
    generate_certification(**vars(args))
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
