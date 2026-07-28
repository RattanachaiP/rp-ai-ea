import csv
import json

import pytest

from analysis.trading_performance_analytics import (
    DAILY_SCHEMA,
    PRODUCTION_SCHEMA,
    generate_reports,
)


def write_json(path, value):
    path.write_text(json.dumps(value), encoding="utf-8")


def series(average):
    return {"count": 1, "total": average, "average": average, "minimum": average, "maximum": average}


def write_trades(path, rows):
    fields = sorted({key for row in rows for key in row})
    with path.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def sources(tmp_path):
    metrics = tmp_path / "runtime_metrics.json"
    daily = tmp_path / "runtime_daily_summary.json"
    trades = tmp_path / "trade_statistics.csv"
    write_json(metrics, {
        "schema_version": "PR252.RUNTIME_METRICS.1.0", "runtime_uptime_seconds": 3600,
        "runtime_restart_count": 2, "runtime_exception_count": 1,
        "execution_rejection_count": 3, "duplicate_decision_count": 4,
        "execution_accept_count": 7, "decision_publish_count": 20,
        "decision_to_execution_latency_ms": series(25), "spread_at_entry_points": series(1.5),
        "slippage_points": series(-0.2),
    })
    write_json(daily, {
        "schema_version": "PR252.RUNTIME_DAILY_SUMMARY.1.0", "summary_date_utc": "2026-07-28",
        "runtime_restart_count": 1, "runtime_exception_count": 0,
        "execution_rejection_count": 1, "duplicate_decision_count": 2,
        "decision_to_execution_latency_ms": series(20), "spread_at_entry_points": series(1.0),
        "slippage_points": series(0.1),
    })
    rows = [
        {"trade_uuid": "one", "entry_time": "2026-07-28T09:00:00Z", "exit_time": "2026-07-28T10:00:00Z", "net_profit": "100", "mfe": "125", "mae": "-10", "exit_reason": "TP", "mode": "TREND", "ai_confidence": "HIGH", "runtime_state": "READY", "direction": "BUY", "spread": "1", "atr": "12", "signal_quality": "A"},
        {"trade_uuid": "two", "entry_time": "2026-07-28T10:00:00Z", "exit_time": "2026-07-28T11:00:00Z", "net_profit": "-40", "mfe": "10", "mae": "-45", "exit_reason": "SL", "mode": "RANGE", "ai_confidence": "LOW", "runtime_state": "READY", "direction": "SELL", "spread": "2", "atr": "10", "signal_quality": "B"},
        {"trade_uuid": "three", "entry_time": "2026-07-27T10:00:00Z", "exit_time": "2026-07-27T11:00:00Z", "net_profit": "20", "mfe": "40", "mae": "-5", "exit_reason": "RUNNER", "dashboard_effective_exit_owner": "TRAILING", "be_trigger_count": "1", "mode": "TREND", "direction": "BUY"},
    ]
    write_trades(trades, rows)
    return metrics, daily, trades


def test_generates_complete_evidence_backed_reports_without_trade_details(tmp_path):
    metrics, daily, trades = sources(tmp_path)
    experts = tmp_path / "Experts.log"
    experts.write_text("JSON read failed\nRuntime exception\nJSON write error\n", encoding="utf-8")
    windows_log = tmp_path / r"C:\Users\TraderName\Terminal\Experts.log"
    network_log = tmp_path / r"\\server\private-share\Journal.log"
    windows_log.write_text("normal line\n", encoding="utf-8")
    network_log.write_text("normal line\n", encoding="utf-8")
    output = tmp_path / "reports"

    production, review = generate_reports(
        runtime_metrics=metrics, runtime_daily_summary=daily, trade_statistics=trades,
        experts_logs=[experts, windows_log], journal_logs=[network_log], output_directory=output,
        generated_at_utc="2026-07-28T12:00:00Z")

    assert production["schema_version"] == PRODUCTION_SCHEMA
    assert production["analysis_only"] is True
    assert production["trading"] == {
        "total_trades": 3, "win_rate": 0.666667, "loss_rate": 0.333333,
        "average_profit": 60.0, "average_loss": -40.0, "profit_factor": 3.0,
        "expectancy": 26.666667, "net_profit": 80.0, "max_drawdown": 40.0,
        "consecutive_wins": 2, "consecutive_losses": 1,
    }
    assert production["execution"]["decision_to_execution_latency_ms"] == 25
    assert production["runtime"]["telemetry_runtime_exception_count"] == 1
    assert production["runtime"]["log_exception_indicator_count"] == 1
    assert production["runtime"]["json_read_failure_indicator_count"] == 1
    assert production["runtime"]["json_write_failure_indicator_count"] == 1
    assert production["entry_quality"]["market_state"]["groups"]["TREND"]["trades"] == 2
    assert production["exit_quality"]["tp_efficiency"]["mfe_capture_ratio"] == 0.8
    assert production["exit_quality"]["be_activation"]["trade_count"] == 1
    assert production["measurable_observations"][0] == {
        "metric": "win_rate", "value": 0.666667, "direction": "higher_is_favorable",
        "sample_size": 3, "source_role": "completed_trades",
    }
    assert "top_measurable_strengths" not in production
    assert "top_measurable_weaknesses" not in production
    assert review["schema_version"] == DAILY_SCHEMA
    assert review["trading"]["total_trades"] == 2
    assert json.loads((output / "production_trading_report.json").read_text()) == production
    assert json.loads((output / "daily_trade_review.json").read_text()) == review
    assert not list(output.glob("*.tmp"))
    assert "trade_uuid" not in json.dumps(production)
    assert str(tmp_path) not in json.dumps(production)
    assert "TraderName" not in json.dumps(production)
    assert "private-share" not in json.dumps(production)
    assert "C:" not in json.dumps(production)
    assert set(production["source_evidence"][0]) == {
        "role", "basename", "schema_version", "record_count", "sha256"}


def test_mt5_history_is_deduplicated_against_trade_statistics(tmp_path):
    metrics, daily, trades = sources(tmp_path)
    production, _ = generate_reports(
        runtime_metrics=metrics, runtime_daily_summary=daily, trade_statistics=trades,
        mt5_report_history=[trades], output_directory=tmp_path / "out")
    assert production["trading"]["total_trades"] == 3


def test_invalid_authoritative_json_fails_before_outputs_are_written(tmp_path):
    metrics, daily, trades = sources(tmp_path)
    write_json(metrics, {"schema_version": "UNKNOWN"})
    output = tmp_path / "out"
    with pytest.raises(ValueError, match="INVALID_SOURCE_SCHEMA"):
        generate_reports(runtime_metrics=metrics, runtime_daily_summary=daily,
                         trade_statistics=trades, output_directory=output)
    assert not output.exists()


@pytest.mark.parametrize("profit, expected", [
    (None, "MISSING_REALIZED_PROFIT"), ("", "MISSING_REALIZED_PROFIT"),
    ("not-money", "INVALID_REALIZED_PROFIT"), ("NaN", "INVALID_REALIZED_PROFIT"),
    ("inf", "INVALID_REALIZED_PROFIT"), ("-Infinity", "INVALID_REALIZED_PROFIT"),
])
def test_invalid_profit_fails_closed_with_source_and_row(tmp_path, profit, expected):
    metrics, daily, trades = sources(tmp_path)
    row = {"trade_uuid": "bad", "entry_time": "2026-07-28T09:00:00Z",
           "exit_time": "2026-07-28T10:00:00Z"}
    if profit is not None:
        row["net_profit"] = profit
    write_trades(trades, [row])
    with pytest.raises(ValueError, match=rf"{expected}:trade_statistics.csv:row=2"):
        generate_reports(runtime_metrics=metrics, runtime_daily_summary=daily,
                         trade_statistics=trades, output_directory=tmp_path / "out")


def test_alias_timestamps_deduplicate_and_distinct_fallback_trades_survive(tmp_path):
    metrics, daily, trades = sources(tmp_path)
    rows = [
        {"symbol": "XAUUSD", "direction": "BUY", "time_open": "2026-07-28T08:00:00Z",
         "time_close": "2026-07-28T09:00:00Z", "profit": "10"},
        {"symbol": "XAUUSD", "direction": "BUY", "open_time": "2026-07-28T10:00:00Z",
         "close_time": "2026-07-28T11:00:00Z", "profit": "10"},
    ]
    write_trades(trades, rows)
    history = tmp_path / "ReportHistory.csv"
    write_trades(history, [rows[0]])
    report, _ = generate_reports(runtime_metrics=metrics, runtime_daily_summary=daily,
                                 trade_statistics=trades, mt5_report_history=[history],
                                 output_directory=tmp_path / "out")
    assert report["trading"]["total_trades"] == 2
    assert report["trading"]["net_profit"] == 20


def test_insufficient_fallback_identity_fails_closed(tmp_path):
    metrics, daily, trades = sources(tmp_path)
    write_trades(trades, [{"symbol": "XAUUSD", "entry_time": "2026-07-28T08:00:00Z",
                           "exit_time": "2026-07-28T09:00:00Z", "net_profit": "10"}])
    with pytest.raises(ValueError, match="INSUFFICIENT_TRADE_IDENTITY:trade_statistics.csv:row=2"):
        generate_reports(runtime_metrics=metrics, runtime_daily_summary=daily,
                         trade_statistics=trades, output_directory=tmp_path / "out")


def test_path_metrics_are_independent_of_selected_source_order(tmp_path):
    metrics, daily, _ = sources(tmp_path)
    early = tmp_path / "early.csv"
    late = tmp_path / "late.csv"
    write_trades(early, [
        {"deal_ticket": "1", "entry_time": "2026-07-28T07:00:00Z", "exit_time": "2026-07-28T08:00:00Z", "profit": "100"},
        {"deal_ticket": "2", "entry_time": "2026-07-28T08:00:00Z", "exit_time": "2026-07-28T09:00:00Z", "profit": "50"},
    ])
    write_trades(late, [
        {"deal_ticket": "3", "entry_time": "2026-07-28T09:00:00Z", "exit_time": "2026-07-28T10:00:00Z", "profit": "-80"},
        {"deal_ticket": "4", "entry_time": "2026-07-28T10:00:00Z", "exit_time": "2026-07-28T11:00:00Z", "profit": "-90"},
    ])
    first, _ = generate_reports(runtime_metrics=metrics, runtime_daily_summary=daily,
                                trade_statistics=early, mt5_report_history=[late], output_directory=tmp_path / "one")
    second, _ = generate_reports(runtime_metrics=metrics, runtime_daily_summary=daily,
                                 trade_statistics=late, mt5_report_history=[early], output_directory=tmp_path / "two")
    keys = ("max_drawdown", "consecutive_wins", "consecutive_losses")
    assert {key: first["trading"][key] for key in keys} == {key: second["trading"][key] for key in keys}
    assert first["trading"]["max_drawdown"] == 170
    assert first["trading"]["consecutive_wins"] == 2
    assert first["trading"]["consecutive_losses"] == 2


def test_daily_review_normalizes_explicit_offsets_to_utc(tmp_path):
    metrics, daily, trades = sources(tmp_path)
    write_trades(trades, [
        {"trade_uuid": "z", "entry_time": "2026-07-28T00:00:00Z", "exit_time": "2026-07-28T01:00:00Z", "profit": "1"},
        {"trade_uuid": "positive-cross", "entry_time": "2026-07-28T00:00:00+02:00", "exit_time": "2026-07-28T01:00:00+02:00", "profit": "2"},
        {"trade_uuid": "negative-cross", "entry_time": "2026-07-27T21:30:00-02:00", "exit_time": "2026-07-27T22:30:00-02:00", "profit": "3"},
    ])
    _, review = generate_reports(runtime_metrics=metrics, runtime_daily_summary=daily,
                                 trade_statistics=trades, output_directory=tmp_path / "out")
    assert review["trading"]["total_trades"] == 2
    assert review["trading"]["net_profit"] == 4


@pytest.mark.parametrize("field, value, expected", [
    ("exit_time", "bad", "INVALID_TRADE_TIMESTAMP"),
    ("exit_time", "", "MISSING_TRADE_TIMESTAMP"),
    ("exit_time", "2026-07-28T10:00:00", "AMBIGUOUS_TRADE_TIMESTAMP"),
])
def test_invalid_or_ambiguous_exit_timestamp_fails_closed(tmp_path, field, value, expected):
    metrics, daily, trades = sources(tmp_path)
    write_trades(trades, [{"trade_uuid": "bad-time", "entry_time": "2026-07-28T09:00:00Z",
                           field: value, "profit": "10"}])
    with pytest.raises(ValueError, match=expected):
        generate_reports(runtime_metrics=metrics, runtime_daily_summary=daily,
                         trade_statistics=trades, output_directory=tmp_path / "out")
