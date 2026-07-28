"""Governed, read-only production trading performance analytics (PR253).

The analyzer consumes snapshots and completed-trade exports after the fact.  It
does not import or call any Runtime, Strategy, Writer, Executor, or broker code.
Only the two explicitly selected report paths are written.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import os
import re
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable, Mapping, Sequence


PRODUCTION_SCHEMA = "PR253.PRODUCTION_TRADING_REPORT.1.0"
DAILY_SCHEMA = "PR253.DAILY_TRADE_REVIEW.1.0"
RUNTIME_SCHEMA = "PR252.RUNTIME_METRICS.1.0"
DAILY_RUNTIME_SCHEMA = "PR252.RUNTIME_DAILY_SUMMARY.1.0"


def _number(value: object) -> float | None:
    try:
        result = float(str(value).strip())
    except (TypeError, ValueError):
        return None
    return result if math.isfinite(result) else None


def _first(row: Mapping[str, object], *names: str) -> str:
    for name in names:
        value = row.get(name)
        if value is not None and str(value).strip():
            return str(value).strip()
    return ""


def _read_json(path: Path, schema: str) -> dict[str, object]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"INVALID_JSON_SOURCE:{path.name}") from exc
    if not isinstance(value, dict) or value.get("schema_version") != schema:
        raise ValueError(f"INVALID_SOURCE_SCHEMA:{path.name}")
    return value


def _read_csv(path: Path) -> list[dict[str, str]]:
    try:
        with path.open("r", newline="", encoding="utf-8-sig") as stream:
            reader = csv.DictReader(stream)
            if not reader.fieldnames:
                raise ValueError(f"MISSING_CSV_HEADER:{path.name}")
            return [dict(row) for row in reader]
    except OSError as exc:
        raise ValueError(f"UNREADABLE_CSV_SOURCE:{path.name}") from exc


def _timestamp(value: str, *, source: Path, row_number: int, field: str) -> datetime:
    """Parse the PR253 timestamp contract: ISO-8601 with an explicit UTC offset."""
    if not value:
        raise ValueError(f"MISSING_TRADE_TIMESTAMP:{source.name}:row={row_number}:field={field}")
    try:
        parsed = datetime.fromisoformat(value[:-1] + "+00:00" if value.endswith(("Z", "z")) else value)
    except ValueError as exc:
        raise ValueError(f"INVALID_TRADE_TIMESTAMP:{source.name}:row={row_number}:field={field}") from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ValueError(f"AMBIGUOUS_TRADE_TIMESTAMP:{source.name}:row={row_number}:field={field}")
    return parsed.astimezone(timezone.utc)


def _required_profit(row: Mapping[str, object], *, source: Path, row_number: int) -> float:
    aliases = ("net_profit", "actual_profit_usd", "realized_profit_usd", "realized_profit", "profit")
    raw = _first(row, *aliases)
    value = _number(raw)
    if value is None:
        reason = "MISSING" if not raw else "INVALID"
        raise ValueError(f"{reason}_REALIZED_PROFIT:{source.name}:row={row_number}")
    return value


def _trade_identity(row: Mapping[str, object], *, source: Path, row_number: int,
                    entry_utc: datetime, exit_utc: datetime, profit: float) -> tuple[str, ...]:
    for field in ("trade_uuid", "deal_ticket", "position_ticket", "order_ticket", "ticket"):
        value = _first(row, field)
        if value:
            return (field, value)
    symbol = _first(row, "symbol")
    direction = _first(row, "direction", "ai_intended_action")
    if not symbol or not direction:
        raise ValueError(f"INSUFFICIENT_TRADE_IDENTITY:{source.name}:row={row_number}")
    return ("fallback", symbol, direction, entry_utc.isoformat(), exit_utc.isoformat(), repr(profit))


def _normalized_trades(paths: Sequence[Path]) -> list[dict[str, object]]:
    unique: dict[tuple[str, ...], dict[str, object]] = {}
    for path in paths:
        for row_number, row in enumerate(_read_csv(path), start=2):
            if not any(str(value or "").strip() for value in row.values()):
                continue
            profit = _required_profit(row, source=path, row_number=row_number)
            entry_raw = _first(row, "entry_time", "time_open", "open_time")
            exit_raw = _first(row, "exit_time", "time_close", "close_time")
            entry_utc = _timestamp(entry_raw, source=path, row_number=row_number, field="entry_time")
            exit_utc = _timestamp(exit_raw, source=path, row_number=row_number, field="exit_time")
            if exit_utc < entry_utc:
                raise ValueError(f"INVALID_TRADE_CHRONOLOGY:{path.name}:row={row_number}")
            identity = _trade_identity(row, source=path, row_number=row_number,
                                       entry_utc=entry_utc, exit_utc=exit_utc, profit=profit)
            normalized = {
                "profit": profit, "entry_utc": entry_utc, "exit_utc": exit_utc,
                "sort_key": (*identity, entry_utc.isoformat(), exit_utc.isoformat()),
                "exit_reason": _first(row, "exit_reason", "broker_deal_reason", "deal_reason"),
                "exit_owner": _first(row, "dashboard_effective_exit_owner", "broker_close_source", "close_source"),
                "mfe": _number(_first(row, "mfe", "maximum_favorable_excursion")),
                "mae": _number(_first(row, "mae", "maximum_adverse_excursion")),
                "be_count": _number(_first(row, "be_trigger_count")) or 0.0,
                "market_state": _first(row, "market_state", "mode", "ai_intended_mode") or "UNAVAILABLE",
                "ai_confidence": _first(row, "ai_confidence", "confidence") or "UNAVAILABLE",
                "runtime_state": _first(row, "runtime_state", "ai_intended_execution_state") or "UNAVAILABLE",
                "entry_direction": _first(row, "direction", "ai_intended_action") or "UNAVAILABLE",
                "spread": _number(_first(row, "spread", "spread_at_entry_points", "entry_spread")),
                "atr": _number(_first(row, "atr", "entry_atr")),
                "signal_quality": _first(row, "signal_quality", "quality") or "UNAVAILABLE",
            }
            previous = unique.get(identity)
            if previous is not None and previous != normalized:
                raise ValueError(f"CONFLICTING_TRADE_IDENTITY:{path.name}:row={row_number}")
            unique.setdefault(identity, normalized)
    return sorted(unique.values(), key=lambda trade: (trade["exit_utc"], trade["sort_key"]))


def _average(values: Iterable[float | None]) -> float | None:
    available = [float(value) for value in values if value is not None]
    return round(sum(available) / len(available), 6) if available else None


def _ratio(numerator: int | float, denominator: int | float) -> float | None:
    return round(float(numerator) / float(denominator), 6) if denominator else None


def _series_average(document: Mapping[str, object], key: str) -> float | None:
    value = document.get(key)
    return _number(value.get("average")) if isinstance(value, Mapping) else None


def _streaks(profits: Sequence[float]) -> tuple[int, int]:
    max_wins = max_losses = wins = losses = 0
    for profit in profits:
        wins = wins + 1 if profit > 0 else 0
        losses = losses + 1 if profit < 0 else 0
        max_wins, max_losses = max(max_wins, wins), max(max_losses, losses)
    return max_wins, max_losses


def _drawdown(profits: Sequence[float]) -> float:
    equity = peak = maximum = 0.0
    for profit in profits:
        equity += profit
        peak = max(peak, equity)
        maximum = max(maximum, peak - equity)
    return round(maximum, 6)


def _trading(trades: Sequence[Mapping[str, object]]) -> dict[str, object]:
    profits = [float(trade["profit"]) for trade in trades]
    wins = [value for value in profits if value > 0]
    losses = [value for value in profits if value < 0]
    max_wins, max_losses = _streaks(profits)
    gross_profit, gross_loss = sum(wins), abs(sum(losses))
    return {
        "total_trades": len(profits), "win_rate": _ratio(len(wins), len(profits)),
        "loss_rate": _ratio(len(losses), len(profits)), "average_profit": _average(wins),
        "average_loss": _average(losses),
        "profit_factor": round(gross_profit / gross_loss, 6) if gross_loss else (None if not gross_profit else "INFINITE"),
        "expectancy": _average(profits), "net_profit": round(sum(profits), 6),
        "max_drawdown": _drawdown(profits), "consecutive_wins": max_wins,
        "consecutive_losses": max_losses,
    }


def _log_counts(paths: Sequence[Path]) -> dict[str, int]:
    patterns = {
        "exception_count": re.compile(r"\b(exception|traceback|fatal)\b", re.I),
        "json_read_failures": re.compile(r"json.{0,40}(read|load|parse).{0,30}(fail|error|invalid)|(?:fail|error|invalid).{0,30}json.{0,30}(read|load|parse)", re.I),
        "json_write_failures": re.compile(r"json.{0,40}(write|publish|save).{0,30}(fail|error)|(?:fail|error).{0,30}json.{0,30}(write|publish|save)", re.I),
    }
    counts = {key: 0 for key in patterns}
    for path in paths:
        try:
            lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
        except OSError as exc:
            raise ValueError(f"UNREADABLE_LOG_SOURCE:{path.name}") from exc
        for line in lines:
            for key, pattern in patterns.items():
                counts[key] += bool(pattern.search(line))
    return counts


def _entry_quality(trades: Sequence[Mapping[str, object]]) -> dict[str, object]:
    fields = ("market_state", "ai_confidence", "runtime_state", "entry_direction", "spread", "atr", "signal_quality")
    result: dict[str, object] = {}
    for field in fields:
        available = [trade for trade in trades if trade[field] not in (None, "", "UNAVAILABLE")]
        if field in ("spread", "atr"):
            result[field] = {"available_trades": len(available), "average": _average(trade[field] for trade in available)}
            continue
        groups: dict[str, list[float]] = defaultdict(list)
        for trade in available:
            groups[str(trade[field])].append(float(trade["profit"]))
        result[field] = {"available_trades": len(available), "groups": {
            name: {"trades": len(values), "win_rate": _ratio(sum(v > 0 for v in values), len(values)),
                   "expectancy": _average(values), "net_profit": round(sum(values), 6)}
            for name, values in sorted(groups.items())}}
    return result


def _exit_quality(trades: Sequence[Mapping[str, object]]) -> dict[str, object]:
    def selected(term: str) -> list[Mapping[str, object]]:
        return [trade for trade in trades if term in f'{trade["exit_reason"]} {trade["exit_owner"]}'.upper()]
    tp, sl, trailing, runners = selected("TP"), selected("SL"), selected("TRAIL"), selected("RUNNER")
    be = [trade for trade in trades if float(trade["be_count"]) > 0]
    efficiency = lambda items: _average(
        float(item["profit"]) / float(item["mfe"]) for item in items
        if item["mfe"] is not None and float(item["mfe"]) > 0)
    return {
        "tp_efficiency": {"exit_count": len(tp), "exit_rate": _ratio(len(tp), len(trades)), "mfe_capture_ratio": efficiency(tp)},
        "sl_efficiency": {"exit_count": len(sl), "exit_rate": _ratio(len(sl), len(trades)), "average_mae": _average(item["mae"] for item in sl)},
        "be_activation": {"trade_count": len(be), "activation_rate": _ratio(len(be), len(trades))},
        "trailing_efficiency": {"exit_count": len(trailing), "mfe_capture_ratio": efficiency(trailing), "net_profit": round(sum(float(x["profit"]) for x in trailing), 6)},
        "runner_performance": {"exit_count": len(runners), "win_rate": _ratio(sum(float(x["profit"]) > 0 for x in runners), len(runners)), "net_profit": round(sum(float(x["profit"]) for x in runners), 6)},
    }


def _observations(trading: Mapping[str, object], execution: Mapping[str, object],
                  runtime: Mapping[str, object]) -> list[dict[str, object]]:
    """Return non-evaluative facts; PR253 owns no performance thresholds."""
    sample_size = int(trading["total_trades"])
    candidates = (
        ("win_rate", trading["win_rate"], "higher_is_favorable", sample_size, "completed_trades"),
        ("profit_factor", trading["profit_factor"], "higher_is_favorable", sample_size, "completed_trades"),
        ("expectancy", trading["expectancy"], "higher_is_favorable", sample_size, "completed_trades"),
        ("net_profit", trading["net_profit"], "higher_is_favorable", sample_size, "completed_trades"),
        ("max_drawdown", trading["max_drawdown"], "lower_is_favorable", sample_size, "completed_trades"),
        ("consecutive_losses", trading["consecutive_losses"], "lower_is_favorable", sample_size, "completed_trades"),
        ("execution_rejections", execution["order_rejection_count"], "lower_is_favorable", execution["execution_sample_size"], "runtime_metrics"),
        ("duplicate_decisions", execution["duplicate_decision_count"], "lower_is_favorable", execution["decision_sample_size"], "runtime_metrics"),
        ("runtime_restarts", runtime["restart_count"], "lower_is_favorable", None, "runtime_metrics"),
        ("telemetry_runtime_exceptions", runtime["telemetry_runtime_exception_count"], "lower_is_favorable", None, "runtime_metrics"),
        ("log_exception_indicators", runtime["log_exception_indicator_count"], "lower_is_favorable", runtime["inspected_log_count"], "runtime_logs"),
    )
    return [{"metric": metric, "value": value, "direction": direction,
             "sample_size": size, "source_role": source}
            for metric, value, direction, size, source in candidates]


def _source_descriptor(role: str, path: Path, *, schema_version: str | None,
                       record_count: int | None) -> dict[str, object]:
    try:
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
    except OSError as exc:
        raise ValueError(f"UNREADABLE_SOURCE:{path.name}") from exc
    basename = str(path).replace("\\", "/").rstrip("/").rsplit("/", 1)[-1]
    return {"role": role, "basename": basename, "schema_version": schema_version,
            "record_count": record_count, "sha256": digest}


def generate_reports(*, runtime_metrics: Path | str, runtime_daily_summary: Path | str,
                     trade_statistics: Path | str, output_directory: Path | str,
                     mt5_report_history: Sequence[Path | str] = (), experts_logs: Sequence[Path | str] = (),
                     journal_logs: Sequence[Path | str] = (), generated_at_utc: str | None = None) -> tuple[dict[str, object], dict[str, object]]:
    """Generate both governed reports from explicitly selected immutable snapshots."""
    metrics_path, daily_path, trade_path = map(Path, (runtime_metrics, runtime_daily_summary, trade_statistics))
    metrics = _read_json(metrics_path, RUNTIME_SCHEMA)
    daily_metrics = _read_json(daily_path, DAILY_RUNTIME_SCHEMA)
    csv_paths = [trade_path, *(Path(path) for path in mt5_report_history)]
    trades = _normalized_trades(csv_paths)
    logs = [*(Path(path) for path in experts_logs), *(Path(path) for path in journal_logs)]
    log_counts = _log_counts(logs)
    execution = {
        "decision_to_execution_latency_ms": _series_average(metrics, "decision_to_execution_latency_ms"),
        "order_rejection_count": int(metrics.get("execution_rejection_count", 0)),
        "duplicate_decision_count": int(metrics.get("duplicate_decision_count", 0)),
        "average_spread": _series_average(metrics, "spread_at_entry_points"),
        "average_slippage": _series_average(metrics, "slippage_points"),
        "execution_sample_size": int(metrics.get("execution_accept_count", 0)) + int(metrics.get("execution_rejection_count", 0)),
        "decision_sample_size": int(metrics.get("decision_publish_count", 0)),
    }
    runtime = {
        "uptime_seconds": _number(metrics.get("runtime_uptime_seconds")),
        "restart_count": int(metrics.get("runtime_restart_count", 0)),
        "telemetry_runtime_exception_count": int(metrics.get("runtime_exception_count", 0)),
        "log_exception_indicator_count": log_counts["exception_count"],
        "json_read_failure_indicator_count": log_counts["json_read_failures"],
        "json_write_failure_indicator_count": log_counts["json_write_failures"],
        "inspected_log_count": len(logs),
    }
    trading = _trading(trades)
    generated = generated_at_utc or datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    csv_counts = [len(_read_csv(path)) for path in csv_paths]
    sources = [_source_descriptor("runtime_metrics", metrics_path, schema_version=RUNTIME_SCHEMA, record_count=1),
               _source_descriptor("runtime_daily_summary", daily_path, schema_version=DAILY_RUNTIME_SCHEMA, record_count=1),
               *(_source_descriptor("completed_trades", path, schema_version=None, record_count=count)
                 for path, count in zip(csv_paths, csv_counts)),
               *(_source_descriptor("runtime_log", path, schema_version=None, record_count=None) for path in logs)]
    report = {"schema_version": PRODUCTION_SCHEMA, "generated_at_utc": generated, "analysis_only": True,
              "source_evidence": sources, "trading": trading, "execution": execution, "runtime": runtime,
              "entry_quality": _entry_quality(trades), "exit_quality": _exit_quality(trades),
              "measurable_observations": _observations(trading, execution, runtime),
              "limitations": (["No Experts or Journal logs supplied; JSON failure counts are zero from inspected logs only."] if not logs else [])}
    day = str(daily_metrics["summary_date_utc"])
    try:
        review_day = datetime.strptime(day, "%Y-%m-%d").date()
    except ValueError as exc:
        raise ValueError("INVALID_DAILY_SUMMARY_DATE") from exc
    daily_trades = [trade for trade in trades if trade["exit_utc"].date() == review_day]
    daily = {"schema_version": DAILY_SCHEMA, "generated_at_utc": generated, "review_date_utc": day,
             "analysis_only": True, "source_evidence": sources, "trading": _trading(daily_trades),
             "execution": {"decision_to_execution_latency_ms": _series_average(daily_metrics, "decision_to_execution_latency_ms"),
                           "order_rejection_count": int(daily_metrics.get("execution_rejection_count", 0)),
                           "duplicate_decision_count": int(daily_metrics.get("duplicate_decision_count", 0)),
                           "average_spread": _series_average(daily_metrics, "spread_at_entry_points"),
                           "average_slippage": _series_average(daily_metrics, "slippage_points")},
             "runtime": {"restart_count": int(daily_metrics.get("runtime_restart_count", 0)),
                         "telemetry_runtime_exception_count": int(daily_metrics.get("runtime_exception_count", 0))},
             "entry_quality": _entry_quality(daily_trades), "exit_quality": _exit_quality(daily_trades)}
    output = Path(output_directory)
    output.mkdir(parents=True, exist_ok=True)
    _atomic_json(output / "production_trading_report.json", report)
    _atomic_json(output / "daily_trade_review.json", daily)
    return report, daily


def _atomic_json(path: Path, document: Mapping[str, object]) -> None:
    temporary = path.with_name(path.name + ".tmp")
    payload = (json.dumps(document, indent=2, sort_keys=True) + "\n").encode("utf-8")
    with temporary.open("wb") as stream:
        stream.write(payload); stream.flush(); os.fsync(stream.fileno())
    os.replace(temporary, path)


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Generate read-only PR253 trading analytics")
    parser.add_argument("--runtime-metrics", required=True); parser.add_argument("--runtime-daily-summary", required=True)
    parser.add_argument("--trade-statistics", required=True); parser.add_argument("--output-directory", required=True)
    parser.add_argument("--mt5-report-history", action="append", default=[])
    parser.add_argument("--experts-log", action="append", default=[]); parser.add_argument("--journal-log", action="append", default=[])
    args = parser.parse_args(argv)
    generate_reports(runtime_metrics=args.runtime_metrics, runtime_daily_summary=args.runtime_daily_summary,
                     trade_statistics=args.trade_statistics, output_directory=args.output_directory,
                     mt5_report_history=args.mt5_report_history, experts_logs=args.experts_log, journal_logs=args.journal_log)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
