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
