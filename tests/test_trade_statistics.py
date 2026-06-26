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


def test_loads_v2735_exit_evidence_csv(tmp_path):
    path = tmp_path / "trade_statistics.csv"
    path.write_text(
        "csv_schema_version,ticket,symbol,direction,trade_mode,entry_time,exit_time,entry_price,exit_price,"
        "stop_loss,take_profit,exit_reason,close_source,broker_exit_reason,dashboard_exit_reason,"
        "mfe,mae,net_profit,duration,dashboard_profile,realized_profit_usd\n"
        "V27_3_5_EXIT_EVIDENCE_AUDIT,9,XAUUSD,BUY,PROTECT,2026.06.25 10:00:00,2026.06.25 10:01:00,"
        "2300.0,2301.0,2299.0,2302.0,DEAL_REASON_TP,BROKER_TP,DEAL_REASON_TP,,1.5,-0.2,1.0,60,Profile_E,1.0\n",
        encoding="utf-8",
    )

    trades = load_completed_trades(path)

    assert len(trades) == 1
    assert trades[0].mode == "PROTECT"
    assert trades[0].net_profit == 1.0


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


def test_profile_e_required_exit_geometry_metrics():
    rows = [
        CompletedTrade(
            "5", "XAUUSD", "BUY", "SCALP", "2026-01-01 00:00:00", "2026-01-01 00:04:00",
            2300, 2300.8, 2298.7, 2300.8, "TP", 0.9, -0.2, 0.8, 240, "Profile_E_SWING_SAFE_SHORT_TP",
        ),
        CompletedTrade(
            "6", "XAUUSD", "BUY", "SCALP", "2026-01-01 00:00:00", "2026-01-01 00:06:00",
            2300, 2298.7, 2298.7, 2300.8, "SL", 0.2, -1.3, -1.3, 360, "Profile_E_SWING_SAFE_SHORT_TP",
            post_sl_continuation_direction="WITH_ORIGINAL_DIRECTION",
        ),
    ]
    metrics = profile_success_metrics(rows)["Profile_E_SWING_SAFE_SHORT_TP"]
    assert metrics["tp_hit_count"] == 1
    assert metrics["sl_hit_count"] == 1
    assert metrics["be_count"] == 0
    assert metrics["average_holding_time"] == 300
    assert metrics["post_sl_continuation_direction"] == {"WITH_ORIGINAL_DIRECTION": 1}


def test_skips_duplicate_v2735_header_with_warning(tmp_path):
    path = tmp_path / "trade_statistics.csv"
    header = "csv_schema_version,ticket,symbol,direction,trade_mode,entry_time,exit_time,entry_price,exit_price,stop_loss,take_profit,exit_reason,mfe,mae,net_profit,duration,dashboard_profile\n"
    path.write_text(
        header
        + "V27_3_5_EXIT_EVIDENCE_AUDIT,10,XAUUSD,BUY,PROTECT,t0,t1,2300,2301,2299,2302,TP,1.2,-0.1,0.8,60,Profile_E\n"
        + header
        + "V27_3_5_EXIT_EVIDENCE_AUDIT,11,XAUUSD,SELL,PROTECT,t0,t1,2301,2300,2302,2299,TP,1.0,-0.2,0.7,70,Profile_E\n",
        encoding="utf-8",
    )

    import pytest

    with pytest.warns(RuntimeWarning, match="DUPLICATE_CSV_HEADER_DETECTED"):
        trades = load_completed_trades(path)

    assert [trade.ticket for trade in trades] == ["10", "11"]


def test_loads_archives_only_when_requested(tmp_path):
    path = tmp_path / "trade_statistics.csv"
    append_completed_trade(trade(12, "Active", 1.0, 1.2, -0.1), path)
    archive_dir = tmp_path / "archive"
    archive_dir.mkdir()
    append_completed_trade(trade(13, "Archived", -0.5, 0.2, -0.7), archive_dir / "trade_statistics_legacy_20260626_113500.csv")

    assert [trade.ticket for trade in load_completed_trades(path)] == ["12"]
    assert [trade.ticket for trade in load_completed_trades(path, include_archives=True)] == ["12", "13"]


def test_execution_consistency_metrics_reports_drift_rates():
    rows = [
        CompletedTrade(
            "14", "XAUUSD", "BUY", "SCALP", "t0", "t1", 2300, 2301, 2299, 2302,
            "TP", 1.0, -0.1, 0.8, 45, "Profile_E", trade_uuid="u1",
            execution_drift_detected=False, execution_drift_reason="NO_DRIFT", ai_intended_planned_rr=2.0,
            rr_intent_vs_realized_ratio=0.4,
        ),
        CompletedTrade(
            "15", "XAUUSD", "BUY", "SCALP", "t0", "t1", 2300, 2300.1, 2299, 2305,
            "EXPERT", 0.2, -0.5, -0.3, 8, "Profile_E", trade_uuid="u2",
            execution_drift_detected=True, execution_drift_reason="EARLY_EXIT_DRIFT", ai_intended_planned_rr=6.0,
            rr_intent_vs_realized_ratio=-0.05,
        ),
    ]
    from analysis.trade_statistics import execution_consistency_metrics

    metrics = execution_consistency_metrics(rows)

    assert metrics["drift_rate"] == 0.5
    assert metrics["drift_by_type"] == {"EARLY_EXIT_DRIFT": 1}
    assert metrics["early_exit_rate"] == 0.5
    assert metrics["is_ai_intent_preserved"] is False


def test_mae_mfe_distribution_metrics():
    from analysis.trade_statistics import mae_mfe_distribution_metrics
    rows = [
        CompletedTrade("1", "XAUUSD", "BUY", "PROTECT", "t0", "t1", 1, 2, 0, 0, "TP", 1.5, -0.3, 1.0, 60, "Profile_F_MARKET_CLOSE_ONLY"),
        CompletedTrade("2", "XAUUSD", "BUY", "PROTECT", "t0", "t1", 1, 0, 0, 0, "HARD_LOSS_CAP", 0.4, -1.2, -1.2, 90, "Profile_F_MARKET_CLOSE_ONLY", broker_close_source="DASHBOARD_MARKET_CLOSE", dashboard_effective_exit_owner="HARD_LOSS_CAP"),
    ]
    metrics = mae_mfe_distribution_metrics(rows)
    assert metrics["trades"] == 2
    assert metrics["average_mfe"] == 0.95
    assert metrics["winning_trades_average_mae"] == 0.3
    assert metrics["losing_trades_mfe_before_sl_or_hard_loss"]["samples"] == 1
