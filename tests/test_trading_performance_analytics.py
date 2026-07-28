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


def sources(tmp_path):
    metrics = tmp_path / "runtime_metrics.json"
    daily = tmp_path / "runtime_daily_summary.json"
    trades = tmp_path / "trade_statistics.csv"
    write_json(metrics, {
        "schema_version": "PR252.RUNTIME_METRICS.1.0", "runtime_uptime_seconds": 3600,
        "runtime_restart_count": 2, "runtime_exception_count": 1,
        "execution_rejection_count": 3, "duplicate_decision_count": 4,
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
        {"trade_uuid": "one", "exit_time": "2026-07-28T10:00:00Z", "net_profit": "100", "mfe": "125", "mae": "-10", "exit_reason": "TP", "mode": "TREND", "ai_confidence": "HIGH", "runtime_state": "READY", "direction": "BUY", "spread": "1", "atr": "12", "signal_quality": "A"},
        {"trade_uuid": "two", "exit_time": "2026-07-28T11:00:00Z", "net_profit": "-40", "mfe": "10", "mae": "-45", "exit_reason": "SL", "mode": "RANGE", "ai_confidence": "LOW", "runtime_state": "READY", "direction": "SELL", "spread": "2", "atr": "10", "signal_quality": "B"},
        {"trade_uuid": "three", "exit_time": "2026-07-27T11:00:00Z", "net_profit": "20", "mfe": "40", "mae": "-5", "exit_reason": "RUNNER", "dashboard_effective_exit_owner": "TRAILING", "be_trigger_count": "1", "mode": "TREND", "direction": "BUY"},
    ]
    with trades.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=sorted({key for row in rows for key in row}))
        writer.writeheader(); writer.writerows(rows)
    return metrics, daily, trades


def test_generates_complete_evidence_backed_reports_without_trade_details(tmp_path):
    metrics, daily, trades = sources(tmp_path)
    experts = tmp_path / "Experts.log"
    experts.write_text("JSON read failed\nRuntime exception\nJSON write error\n", encoding="utf-8")
    output = tmp_path / "reports"

    production, review = generate_reports(
        runtime_metrics=metrics, runtime_daily_summary=daily, trade_statistics=trades,
        experts_logs=[experts], output_directory=output, generated_at_utc="2026-07-28T12:00:00Z")

    assert production["schema_version"] == PRODUCTION_SCHEMA
    assert production["analysis_only"] is True
    assert production["trading"] == {
        "total_trades": 3, "win_rate": 0.666667, "loss_rate": 0.333333,
        "average_profit": 60.0, "average_loss": -40.0, "profit_factor": 3.0,
        "expectancy": 26.666667, "net_profit": 80.0, "max_drawdown": 40.0,
        "consecutive_wins": 1, "consecutive_losses": 1,
    }
    assert production["execution"]["decision_to_execution_latency_ms"] == 25
    assert production["runtime"]["json_read_failures"] == 1
    assert production["entry_quality"]["market_state"]["groups"]["TREND"]["trades"] == 2
    assert production["exit_quality"]["tp_efficiency"]["mfe_capture_ratio"] == 0.8
    assert production["exit_quality"]["be_activation"]["trade_count"] == 1
    assert production["top_measurable_weaknesses"][0]["evidence"]
    assert production["top_measurable_strengths"][0]["evidence"]
    assert review["schema_version"] == DAILY_SCHEMA
    assert review["trading"]["total_trades"] == 2
    assert json.loads((output / "production_trading_report.json").read_text()) == production
    assert json.loads((output / "daily_trade_review.json").read_text()) == review
    assert not list(output.glob("*.tmp"))
    assert "trade_uuid" not in json.dumps(production)


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
