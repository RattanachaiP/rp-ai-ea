"""Evidence-only V27 negative-edge cohort analysis.

This program never writes a decision payload and never changes dashboard or exit
configuration.  It ranks cohorts using completed-trade fields already recorded
by the V27 trade-statistics contract, validates chronological stability, and
identifies (but does not implement) candidates eligible for one entry block.
"""
from __future__ import annotations

import argparse
import csv
import math
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from statistics import median
from typing import Any, Iterable

DATASET_VERSION = "V27_NEGATIVE_EDGE_COHORT_ANALYSIS_1"
MINIMUM_SAMPLE_SIZE = 50
MAX_PROFIT_FACTOR = 0.80
MFE_LOW_USD = 0.25

# Canonical cohort names map only to fields already emitted by V27 trade records.
DIMENSIONS: dict[str, tuple[str, ...]] = {
    "market_mode": ("market_mode", "mode", "ai_intended_mode"),
    "bb_state": ("bb_state", "BB_state", "ai_intended_bb_state"),
    "direction": ("direction", "ai_intended_bias", "ai_intended_action"),
    "buy_score": ("buy_score", "score_buy"),
    "sell_score": ("sell_score", "score_sell"),
    "score_gap": ("score_gap",),
    "execution_state": ("execution_state", "ai_intended_execution_state"),
    "participation_type": ("participation_type", "entry_type", "active_execution_leg"),
    "entry_location_score": ("entry_location_score",),
    "entry_window_score": ("entry_window_score",),
    "execution_confidence_score": ("execution_confidence_score", "execution_confidence"),
    "management_mode": ("management_mode", "ai_intended_management", "mode"),
    "entry_hour": ("entry_hour", "entry_time", "open_time"),
    "dashboard_profile": ("dashboard_profile", "dashboard_profile_at_entry"),
    "cautious_vs_normal_execution": ("cautious_vs_normal_execution", "execution_state"),
}


def _number(row: dict[str, str], keys: Iterable[str], default: float = 0.0) -> float:
    for key in keys:
        try:
            value = row.get(key, "").strip()
            if value:
                return float(value)
        except (AttributeError, TypeError, ValueError):
            pass
    return default


def _text(row: dict[str, str], keys: Iterable[str]) -> str:
    for key in keys:
        value = str(row.get(key, "")).strip()
        if value:
            return value
    return "UNKNOWN"


def _timestamp(row: dict[str, str]) -> datetime | None:
    for key in ("entry_time", "open_time", "close_time", "exit_time", "timestamp"):
        raw = str(row.get(key, "")).strip().replace("T", " ").replace("Z", "")
        for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M", "%Y.%m.%d %H:%M:%S", "%Y.%m.%d %H:%M"):
            try:
                return datetime.strptime(raw[:19 if "%S" in fmt else 16], fmt)
            except ValueError:
                continue
    return None


def _entry_hour(row: dict[str, str]) -> str:
    explicit = str(row.get("entry_hour", "")).strip()
    if explicit:
        return explicit
    stamp = _timestamp(row)
    return str(stamp.hour) if stamp else "UNKNOWN"


def _bucket(value: str, dimension: str) -> str:
    if dimension not in {"buy_score", "sell_score", "score_gap", "entry_location_score", "entry_window_score", "execution_confidence_score"}:
        return value.upper()
    try:
        numeric = float(value)
    except ValueError:
        return "UNKNOWN"
    # Fixed, reportable bins prevent a post-hoc threshold from becoming a block.
    return f"{math.floor(numeric):.0f}-{math.floor(numeric) + 1:.0f}"


def _value(row: dict[str, str], dimension: str) -> str:
    if dimension == "entry_hour":
        return _entry_hour(row)
    if dimension == "cautious_vs_normal_execution":
        state = _text(row, DIMENSIONS[dimension]).upper()
        return "CAUTIOUS" if "CAUTIOUS" in state else "NORMAL" if "NORMAL" in state or "EXECUTE" in state else state
    return _bucket(_text(row, DIMENSIONS[dimension]), dimension)


def _stats(rows: list[dict[str, str]]) -> dict[str, Any]:
    pnl = [_number(row, ("net_profit", "actual_profit_usd", "profit", "pnl", "realized_profit")) for row in rows]
    wins = [item for item in pnl if item > 0]
    losses = [item for item in pnl if item < 0]
    gross_profit, gross_loss = sum(wins), abs(sum(losses))
    pf = gross_profit / gross_loss if gross_loss else (float("inf") if gross_profit else 0.0)
    mfe = [_number(row, ("mfe", "mfe_usd", "maximum_favorable_excursion")) for row in rows]
    mae = [_number(row, ("mae", "mae_usd", "maximum_adverse_excursion")) for row in rows]
    tp = sum("TP" in _text(row, ("exit_reason", "broker_deal_reason", "broker_close_source", "dashboard_last_close_intent")).upper() or "TAKE_PROFIT" in _text(row, ("exit_reason", "broker_deal_reason", "broker_close_source", "dashboard_last_close_intent")).upper() for row in rows)
    hard_loss = sum(any(token in _text(row, ("exit_reason", "broker_deal_reason", "broker_close_source", "dashboard_last_close_intent")).upper() for token in ("HARD_LOSS", "BROKER_SL", "STOP_LOSS", " SL")) for row in rows)
    count = len(rows)
    return {
        "trade_count": count, "win_rate": len(wins) / count if count else 0.0, "loss_rate": len(losses) / count if count else 0.0,
        "gross_profit": gross_profit, "gross_loss": gross_loss, "net_profit": sum(pnl), "profit_factor": pf,
        "average_win": gross_profit / len(wins) if wins else 0.0, "average_loss": gross_loss / len(losses) if losses else 0.0,
        "expectancy": sum(pnl) / count if count else 0.0, "median_mfe": median(mfe) if mfe else 0.0,
        "median_mae": median(mae) if mae else 0.0, "mfe_below_025_pct": sum(item < MFE_LOW_USD for item in mfe) / count if count else 0.0,
        "fixed_tp_close_pct": tp / count if count else 0.0, "hard_loss_or_broker_sl_pct": hard_loss / count if count else 0.0,
    }


def _counterfactual(all_rows: list[dict[str, str]], excluded: list[dict[str, str]]) -> dict[str, Any]:
    excluded_ids = {id(row) for row in excluded}
    remaining = [row for row in all_rows if id(row) not in excluded_ids]
    result = _stats(remaining)
    result["trades_removed_pct"] = len(excluded) / len(all_rows) if all_rows else 0.0
    return result


def analyze(rows: list[dict[str, str]]) -> tuple[dict[str, list[dict[str, Any]]], list[dict[str, Any]]]:
    chronologically_sorted = sorted(rows, key=lambda row: _timestamp(row) or datetime.min)
    half = len(chronologically_sorted) // 2
    first_half, second_half = chronologically_sorted[:half], chronologically_sorted[half:]
    baseline = _stats(rows)
    tables: dict[str, list[dict[str, Any]]] = {}
    candidates: list[dict[str, Any]] = []
    for dimension in DIMENSIONS:
        cohorts: dict[str, list[dict[str, str]]] = defaultdict(list)
        for row in rows:
            cohorts[_value(row, dimension)].append(row)
        table = []
        for cohort, items in cohorts.items():
            metrics = _stats(items)
            first = _stats([row for row in first_half if _value(row, dimension) == cohort])
            second = _stats([row for row in second_half if _value(row, dimension) == cohort])
            counterfactual = _counterfactual(rows, items)
            item = {"dimension": dimension, "cohort": cohort, **metrics, "first_half_expectancy": first["expectancy"], "second_half_expectancy": second["expectancy"], "first_half_count": first["trade_count"], "second_half_count": second["trade_count"], "counterfactual": counterfactual}
            item["eligible"] = (metrics["trade_count"] >= MINIMUM_SAMPLE_SIZE and metrics["profit_factor"] < MAX_PROFIT_FACTOR and metrics["expectancy"] < 0 and first["expectancy"] < 0 and second["expectancy"] < 0 and counterfactual["profit_factor"] > baseline["profit_factor"] and counterfactual["expectancy"] > baseline["expectancy"])
            table.append(item)
            if item["eligible"]:
                candidates.append(item)
        tables[dimension] = sorted(table, key=lambda item: (item["expectancy"], item["profit_factor"], -item["trade_count"]))
    candidates.sort(key=lambda item: (-(item["counterfactual"]["expectancy"] - baseline["expectancy"]), -(item["counterfactual"]["profit_factor"] - baseline["profit_factor"]), item["trade_count"]))
    return tables, candidates


def _format(value: Any) -> str:
    if isinstance(value, float):
        return "INF" if math.isinf(value) else f"{value:.3f}"
    return str(value)


def write_report(rows: list[dict[str, str]], output: Path, source: Path) -> None:
    tables, candidates = analyze(rows)
    baseline = _stats(rows)
    lines = ["# V27 Negative-Edge Cohort Report", "", "## 1. Dataset summary", "", f"- Analysis dataset version: `{DATASET_VERSION}`.", f"- Source: `{source}`.", f"- Closed trades available: **{len(rows)}**.", f"- Baseline PF: **{_format(baseline['profit_factor'])}**; expectancy: **{_format(baseline['expectancy'])} USD/trade**.", ""]
    if not rows:
        lines += [
            "The repository contains no completed-trade rows (the supplied `analysis/trade_memory.csv` is empty). The stated 829-trade aggregate evidence does not include the per-trade entry fields required to calculate cohorts, chronological stability, or counterfactuals.",
            "", "## 2. Cohort profitability table", "", "No cohort table can be calculated without per-trade rows.",
            "", "## 3. Worst negative expectancy cohort", "", "`NO_STATISTICALLY_VALID_NEGATIVE_EDGE_GROUP_FOUND`",
            "", "## 4. Sample size and time stability", "", "Not evaluable: no chronological trade records are available.",
            "", "## 5. Counterfactual system result after exclusion", "", "Not evaluable: no candidate cohort exists.",
            "", "## 6. Percentage of trades removed", "", "0.0% (no runtime rule).",
            "", "## 7. Expected PF improvement", "", "None claimed without a validated cohort.",
            "", "## 8. Expected expectancy improvement", "", "None claimed without a validated cohort.",
            "", "## 9. Selected runtime rule", "", "No rule selected; runtime behavior remains unchanged.",
            "", "No runtime entry exclusion was implemented.", "", "## 10. Rejected alternative rules and reasons", "", "- All potential rules: rejected because the required per-trade cohort data and chronological stability evidence are unavailable.",
            "", "Profile_F and all exit/dashboard settings remain unchanged.",
        ]
        output.write_text("\n".join(lines) + "\n", encoding="utf-8")
        return
    lines += ["## 2. Cohort profitability table", "", "Every available dimension is ranked worst-to-best by expectancy. `TP%` means fixed-TP closes; `SL%` means Risk Hard Loss Cap/Broker SL closes.", ""]
    for dimension, table in tables.items():
        lines += [f"### {dimension}", "", "| Cohort | N | Win% | Loss% | Gross profit | Gross loss | Net | PF | Avg win | Avg loss | Exp. | Med MFE | Med MAE | MFE < $0.25 | TP% | SL% |", "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|"]
        for item in table:
            lines.append("| {cohort} | {trade_count} | {win_rate:.1%} | {loss_rate:.1%} | {gross_profit:.2f} | {gross_loss:.2f} | {net_profit:.2f} | {pf} | {average_win:.2f} | {average_loss:.2f} | {expectancy:.2f} | {median_mfe:.2f} | {median_mae:.2f} | {mfe_below_025_pct:.1%} | {fixed_tp_close_pct:.1%} | {hard_loss_or_broker_sl_pct:.1%} |".format(**item, pf=_format(item["profit_factor"])))
        lines.append("")
    lines += ["## 3. Worst negative expectancy cohort", "", "No cohort meets the implementation gate." if not candidates else f"Selected candidate: `{candidates[0]['dimension']}={candidates[0]['cohort']}`.", "", "## 4. Sample size and time stability", ""]
    for candidate in candidates[:5]:
        lines.append(f"- `{candidate['dimension']}={candidate['cohort']}`: N={candidate['trade_count']}, first-half={candidate['first_half_expectancy']:.2f} (N={candidate['first_half_count']}), second-half={candidate['second_half_expectancy']:.2f} (N={candidate['second_half_count']}).")
    if not candidates:
        lines.append("- No cohort satisfies N >= 50, PF < 0.80, negative expectancy in both chronological halves, and counterfactual PF/expectancy improvement.")
    lines += ["", "## 5. Counterfactual system result after exclusion", "", "No validated cohort; no historical exclusion result is selected.", "", "## 6. Percentage of trades removed", "", "0.0% (no runtime rule).", "", "## 7. Expected PF improvement", "", "None claimed without a validated cohort.", "", "## 8. Expected expectancy improvement", "", "None claimed without a validated cohort.", "", "## 9. Selected runtime rule", "", "No rule selected; runtime behavior remains unchanged.", "", "No runtime entry exclusion was implemented.", "", "## 10. Rejected alternative rules and reasons", "", "- All cohort dimensions: rejected unless and until they independently meet every minimum-sample, PF, expectancy, chronological-stability, and counterfactual requirement."]
    output.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", type=Path, default=Path(__file__).with_name("trade_memory.csv"))
    parser.add_argument("--output", type=Path, default=Path(__file__).parents[1] / "V27_NEGATIVE_EDGE_COHORT_REPORT.md")
    args = parser.parse_args()
    rows: list[dict[str, str]] = []
    if args.input.exists() and args.input.stat().st_size:
        with args.input.open(newline="", encoding="utf-8-sig") as handle:
            rows = [row for row in csv.DictReader(handle) if row]
    write_report(rows, args.output, args.input)


if __name__ == "__main__":
    main()
