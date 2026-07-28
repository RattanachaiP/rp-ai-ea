"""Governed, read-only production trading performance analytics (PR253).

The analyzer consumes snapshots and completed-trade exports after the fact.  It
does not import or call any Runtime, Strategy, Writer, Executor, or broker code.
Only the two explicitly selected report paths are written.
"""
from __future__ import annotations

import argparse
import csv
import json
import math
import os
import re
from collections import Counter, defaultdict
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


def _trade_key(row: Mapping[str, object]) -> tuple[str, ...]:
    identity = _first(row, "trade_uuid", "deal_ticket", "ticket", "position_ticket")
    if identity:
        return ("identity", identity)
    return ("values", _first(row, "symbol"), _first(row, "entry_time"),
            _first(row, "exit_time"), _first(row, "net_profit", "actual_profit_usd", "profit"))


def _normalized_trades(paths: Sequence[Path]) -> list[dict[str, object]]:
    unique: dict[tuple[str, ...], dict[str, object]] = {}
    for path in paths:
        for row in _read_csv(path):
            if not any(str(value or "").strip() for value in row.values()):
                continue
            unique.setdefault(_trade_key(row), {
                "profit": _number(_first(row, "net_profit", "actual_profit_usd", "realized_profit_usd", "realized_profit", "profit")) or 0.0,
                "entry_time": _first(row, "entry_time", "time_open", "open_time"),
                "exit_time": _first(row, "exit_time", "time_close", "close_time"),
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
            })
    return list(unique.values())


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


def _ranked_findings(trading: Mapping[str, object], execution: Mapping[str, object], runtime: Mapping[str, object]) -> tuple[list[dict[str, object]], list[dict[str, object]]]:
    candidates = [
        ("win_rate", trading["win_rate"], "higher", "trade_statistics"),
        ("profit_factor", trading["profit_factor"], "higher", "trade_statistics"),
        ("expectancy", trading["expectancy"], "higher", "trade_statistics"),
        ("net_profit", trading["net_profit"], "higher", "trade_statistics"),
        ("max_drawdown", trading["max_drawdown"], "lower", "trade_statistics"),
        ("consecutive_losses", trading["consecutive_losses"], "lower", "trade_statistics"),
        ("execution_rejections", execution["order_rejection_count"], "lower", "runtime_metrics"),
        ("duplicate_decisions", execution["duplicate_decision_count"], "lower", "runtime_metrics"),
        ("runtime_restarts", runtime["restart_count"], "lower", "runtime_metrics"),
        ("runtime_exceptions", runtime["exception_count"], "lower", "runtime_metrics_and_logs"),
    ]
    strengths, weaknesses = [], []
    for metric, value, desired, source in candidates:
        if value is None or value == "INFINITE":
            classification = "strength" if value == "INFINITE" else None
        elif desired == "higher":
            classification = "strength" if float(value) > 0 else "weakness"
        else:
            classification = "strength" if float(value) == 0 else "weakness"
        if classification:
            finding = {"metric": metric, "observed_value": value, "evidence": {"source": source, "calculation": metric}}
            (strengths if classification == "strength" else weaknesses).append(finding)
    return weaknesses[:10], strengths[:10]


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
    }
    runtime = {
        "uptime_seconds": _number(metrics.get("runtime_uptime_seconds")),
        "restart_count": int(metrics.get("runtime_restart_count", 0)),
        "exception_count": max(int(metrics.get("runtime_exception_count", 0)), log_counts["exception_count"]),
        "json_read_failures": log_counts["json_read_failures"], "json_write_failures": log_counts["json_write_failures"],
    }
    trading = _trading(trades)
    weaknesses, strengths = _ranked_findings(trading, execution, runtime)
    generated = generated_at_utc or datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    sources = [{"role": "runtime_metrics", "path": str(metrics_path)}, {"role": "runtime_daily_summary", "path": str(daily_path)},
               *({"role": "completed_trades", "path": str(path)} for path in csv_paths),
               *({"role": "runtime_log", "path": str(path)} for path in logs)]
    report = {"schema_version": PRODUCTION_SCHEMA, "generated_at_utc": generated, "analysis_only": True,
              "source_evidence": sources, "trading": trading, "execution": execution, "runtime": runtime,
              "entry_quality": _entry_quality(trades), "exit_quality": _exit_quality(trades),
              "top_measurable_weaknesses": weaknesses, "top_measurable_strengths": strengths,
              "limitations": (["No Experts or Journal logs supplied; JSON failure counts are zero from inspected logs only."] if not logs else [])}
    day = str(daily_metrics["summary_date_utc"])
    daily_trades = [trade for trade in trades if str(trade["exit_time"])[:10] == day]
    daily = {"schema_version": DAILY_SCHEMA, "generated_at_utc": generated, "review_date_utc": day,
             "analysis_only": True, "source_evidence": sources, "trading": _trading(daily_trades),
             "execution": {"decision_to_execution_latency_ms": _series_average(daily_metrics, "decision_to_execution_latency_ms"),
                           "order_rejection_count": int(daily_metrics.get("execution_rejection_count", 0)),
                           "duplicate_decision_count": int(daily_metrics.get("duplicate_decision_count", 0)),
                           "average_spread": _series_average(daily_metrics, "spread_at_entry_points"),
                           "average_slippage": _series_average(daily_metrics, "slippage_points")},
             "runtime": {"restart_count": int(daily_metrics.get("runtime_restart_count", 0)),
                         "exception_count": int(daily_metrics.get("runtime_exception_count", 0))},
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
