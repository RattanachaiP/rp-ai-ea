from pathlib import Path

from analysis.zero_broker_sl_validation import compare, demo_contract_validation, profile_metrics


def rows(*items):
    return [{"net_profit": str(profit), "exit_reason": reason} for profit, reason in items]


def test_profile_metrics_produces_all_mandatory_comparison_fields():
    result = profile_metrics(rows((2, "FIXED_TP"), (-1, "BROKER_SL"), (-3, "BROKER_SL"), (1, "FIXED_TP")))

    assert result["available"] is True
    assert result["profit_factor"] == 0.75
    assert result["expectancy"] == -0.25
    assert result["net_profit"] == -1.0
    assert result["win_rate"] == 0.5
    assert result["average_win"] == 1.5
    assert result["average_loss"] == -2.0
    assert result["maximum_drawdown"] == 4.0
    assert result["capital_damage_ranking"] == [{"rank": 1, "exit_bucket": "BROKER_SL", "loss_count": 2, "capital_damage": 4.0, "average_loss": -2.0}]
    assert result["equity_curve"] == [2.0, 1.0, -2.0, -1.0]


def test_equal_or_lower_expectancy_rules_out_broker_sl_as_root_cause():
    baseline = profile_metrics(rows((1, "FIXED_TP"), (-1, "BROKER_SL")))
    zero_sl = profile_metrics(rows((1, "FIXED_TP"), (-1, "HARD_LOSS_CAP")))

    result = compare(baseline, zero_sl)

    assert result["expectancy_improved"] is False
    assert result["broker_sl_root_cause"] == "NOT_ROOT_CAUSE"
    assert "Do not perform further Broker SL-focused work" in result["required_action"]


def test_missing_closed_outcomes_remains_undetermined():
    result = compare(profile_metrics([]), profile_metrics([]))
    assert result["conclusion"] == "INSUFFICIENT_CLOSED_TRADE_EVIDENCE"
    assert result["broker_sl_root_cause"] == "UNDETERMINED"


def test_demo_contract_proves_zero_broker_sl_configuration():
    result = demo_contract_validation(Path(__file__).resolve().parents[1])
    assert result["passed"] is True
    assert result["broker_sl_required"] is False
    assert result["stop_loss"] == 0.0
