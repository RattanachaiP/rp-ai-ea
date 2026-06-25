from analysis.trade_statistics import CompletedTrade, append_completed_trade, load_completed_trades, profile_success_metrics, evidence_gate


def trade(ticket, profile, profit, mfe, mae, reason="TP"):
    return CompletedTrade(str(ticket), "XAUUSD", "BUY", "SCALP", "2026-01-01 00:00:00", "2026-01-01 00:05:00", 2300, 2301, 2299, 2301, reason, mfe, mae, profit, 300, profile)


def test_records_stable_trade_statistics_csv(tmp_path):
    path = tmp_path / "trade_statistics.csv"
    append_completed_trade(trade(1, "Profile_A", 1.0, 1.2, -0.2), path)
    rows = load_completed_trades(path)
    assert rows[0].ticket == "1"
    assert rows[0].dashboard_profile == "Profile_A"


def test_success_metrics_and_evidence_gate():
    rows = [trade(1, "Profile_A", 1.0, 2.0, -0.2), trade(2, "Profile_A", -0.5, 0.4, -0.7, "SL")]
    metrics = profile_success_metrics(rows)
    assert metrics["Profile_A"]["win_rate"] == 0.5
    assert metrics["Profile_A"]["profit_factor"] == 2.0
    assert metrics["Profile_A"]["exit_reason_distribution"] == {"TP": 1, "SL": 1}
    assert evidence_gate(metrics, min_trades_per_profile=3)[0] is False


def test_breakeven_analytics_metrics():
    rows = [
        CompletedTrade(
            "3", "XAUUSD", "BUY", "SCALP", "2026-01-01 00:00:00", "2026-01-01 00:02:00",
            2300, 2300.5, 2299, 2301, "SL", 1.4, -0.1, 0.1, 120, "Profile_B",
            be_trigger_count=1, be_stop_out=True, realized_profit=0.1, profit_before_be=0.8,
            maximum_profit_after_be=1.4, maximum_drawdown_after_be=-0.7, lost_opportunity_after_be=1.3,
            be_false_trigger=True, be_false_trigger_distance=0.4, be_survival_time_seconds=30,
            capture_ratio_after_be=0.0714,
        ),
        CompletedTrade(
            "4", "XAUUSD", "BUY", "SCALP", "2026-01-01 00:00:00", "2026-01-01 00:03:00",
            2300, 2301, 2299, 2301, "TP", 1.0, -0.1, 1.0, 180, "Profile_B",
            be_trigger_count=1, realized_profit=1.0, maximum_profit_after_be=1.0,
            capture_ratio_after_be=1.0,
        ),
    ]
    metrics = profile_success_metrics(rows)["Profile_B"]
    assert metrics["BE_TRIGGER_COUNT"] == 2
    assert metrics["BE_STOP_OUT_COUNT"] == 1
    assert metrics["BE_STOP_OUT_RATE"] == 0.5
    assert metrics["BE_FALSE_TRIGGER"] == 1
    assert metrics["FALSE_BE_RATE"] == 1.0
    assert metrics["AVERAGE_BE_SURVIVAL_TIME"] == 30
    assert metrics["MEDIAN_BE_SURVIVAL_TIME"] == 30
    assert metrics["AVG_LOST_OPPORTUNITY_AFTER_BE"] == 1.3
