from analysis.v27_negative_edge_cohort_analysis import analyze, write_report


def trade(mode: str, profit: float, minute: int) -> dict[str, str]:
    return {
        "market_mode": mode,
        "net_profit": str(profit),
        "entry_time": f"2026-01-01 00:{minute:02d}:00",
        "mfe": "0.10" if profit < 0 else "1.00",
        "mae": "1.20" if profit < 0 else "0.20",
        "exit_reason": "BROKER_SL" if profit < 0 else "FIXED_TP",
    }


def test_stable_negative_cohort_is_ranked_and_eligible():
    # Each chronological half has 30 BAD and 20 GOOD trades.
    rows = []
    for offset in (0, 50):
        rows += [trade("BAD", -1.0, offset + i) for i in range(30)]
        rows += [trade("GOOD", 2.0, offset + 30 + i) for i in range(20)]
    tables, candidates = analyze(rows)
    bad = next(item for item in tables["market_mode"] if item["cohort"] == "BAD")
    assert bad["trade_count"] == 60
    assert bad["profit_factor"] == 0
    assert bad["expectancy"] == -1
    assert bad["first_half_expectancy"] < 0
    assert bad["second_half_expectancy"] < 0
    assert bad["counterfactual"]["expectancy"] > 0
    assert candidates[0]["cohort"] == "BAD"


def test_report_declares_no_valid_group_when_no_rows(tmp_path):
    output = tmp_path / "report.md"
    write_report([], output, tmp_path / "empty.csv")
    report = output.read_text(encoding="utf-8")
    assert "NO_STATISTICALLY_VALID_NEGATIVE_EDGE_GROUP_FOUND" in report
    assert "No runtime entry exclusion was implemented" in report
