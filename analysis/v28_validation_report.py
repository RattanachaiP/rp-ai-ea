"""Generate evidence-only V27/V28 validation metrics from a closed-trade CSV.

No outcome is inferred when the source lacks a numeric realized P/L column.
"""
from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
from typing import Any, Iterable

PROFIT_COLUMNS = ("profit", "profit_usd", "realized_profit", "pnl", "net_profit")


def _number(row: dict[str, str], names: Iterable[str]) -> float | None:
    for name in names:
        try:
            value = row.get(name, "").strip()
            if value:
                return float(value)
        except (AttributeError, ValueError):
            pass
    return None


def metrics(rows: list[dict[str, str]]) -> dict[str, Any]:
    profits = [value for row in rows if (value := _number(row, PROFIT_COLUMNS)) is not None]
    if not profits:
        return {"available": False, "limitation": "No numeric realized P/L column was available; no profitability result was calculated.", "trade_count": 0}
    wins, losses = [p for p in profits if p > 0], [p for p in profits if p < 0]
    gross_profit, gross_loss = sum(wins), abs(sum(losses))
    streak = best = 0
    equity = peak = max_drawdown = 0.0
    for profit in profits:
        streak = streak + 1 if profit < 0 else 0
        best = max(best, streak)
        equity += profit
        peak = max(peak, equity)
        max_drawdown = max(max_drawdown, peak - equity)
    return {"available": True, "trade_count": len(profits), "win_rate": len(wins) / len(profits), "profit_factor": gross_profit / gross_loss if gross_loss else None, "expectancy": sum(profits) / len(profits), "average_win": sum(wins) / len(wins) if wins else 0.0, "average_loss": sum(losses) / len(losses) if losses else 0.0, "net_pl": sum(profits), "gross_profit": gross_profit, "gross_loss": gross_loss, "maximum_losing_streak": best, "estimated_drawdown": max_drawdown}


def main() -> None:
    parser = argparse.ArgumentParser(description="Create a V28 evidence validation report; it does not backtest missing data.")
    parser.add_argument("--trades", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    with args.trades.open(newline="", encoding="utf-8-sig") as handle:
        rows = list(csv.DictReader(handle))
    report = {"report_version": "V28_VALIDATION_REPORT_1", "source": str(args.trades), "source_rows": len(rows), "v27_completed_trade_outcomes": metrics(rows), "v28_replay": {"available": False, "limitation": "Market-state snapshots linked to completed outcomes are not present in this input; V28 replay metrics were not fabricated."}, "shadow_comparison": {"available": False, "required_fields": ["v27 decision", "v28 decision", "candidate timestamp", "confidence tier", "risk package validity"]}}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
