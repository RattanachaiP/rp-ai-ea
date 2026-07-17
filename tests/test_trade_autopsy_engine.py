from analysis.trade_autopsy_engine import build_record, blank_summary, add_summary, finalize


def completed_trade(**overrides):
    row = {
        "ticket": "1",
        "direction": "BUY",
        "profit": "-1.00",
        "planned_risk": "1.00",
        "MFE": "0.00",
        "MAE": "-1.00",
    }
    row.update(overrides)
    return build_record(row)


def test_loss_classification_identifies_wrong_direction_from_shadow_evidence():
    record = completed_trade(would_opposite_have_won="true", original_vs_opposite_profit="-1.50")

    assert record["loss_classification"] == "DIRECTION_ERROR"
    assert record["direction_accuracy"] == "INCORRECT"
    assert record["net_expectancy_contribution"] == -1.0


def test_loss_classification_identifies_poor_entry_location_before_geometry():
    record = completed_trade(exhaustion_score="80", hard_loss_cap_triggered="true")

    assert record["loss_classification"] == "ENTRY_LOCATION_ERROR"
    assert record["entry_quality"] == "POOR"


def test_loss_classification_identifies_risk_geometry_and_exit_capture_metrics():
    geometry = completed_trade(hard_loss_cap_triggered="true")
    exit_error = completed_trade(MFE="2.00", max_floating_profit="2.00")

    assert geometry["loss_classification"] == "RISK_GEOMETRY_ERROR"
    assert exit_error["loss_classification"] == "EXIT_ERROR"
    assert exit_error["exit_efficiency"] == 0.0


def test_unexplained_loss_is_decision_logic_error_and_summary_ranks_damage():
    record = completed_trade(MAE="0.00")
    summary = blank_summary("20260717")
    add_summary(summary, record)
    result = finalize(summary)

    assert record["loss_classification"] == "DECISION_LOGIC_ERROR"
    assert result["loss_classification_distribution"] == {"DECISION_LOGIC_ERROR": 1}
    assert result["mandatory_loss_classification_ranking_by_capital_damage"] == [
        {"classification": "DECISION_LOGIC_ERROR", "damage": -1.0}
    ]
