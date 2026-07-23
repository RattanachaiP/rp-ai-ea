"""Outcome aggregation for candidate pattern groups."""
from __future__ import annotations
from collections.abc import Iterable, Mapping
import math
from statistics import median, pstdev

def _number(record: Mapping[str, object], *keys: str) -> float | None:
    outcomes = record.get("outcomes", {})
    sources = (record, outcomes) if isinstance(outcomes, Mapping) else (record,)
    for source in sources:
        for key in keys:
            value = source.get(key)
            if value is not None:
                try:
                    value = float(value)
                except (TypeError, ValueError):
                    continue
                if math.isfinite(value): return value
    return None

def calculate_statistics(records: Iterable[Mapping[str, object]]) -> dict[str, float | int]:
    items = list(records); profits = [_number(item, "net_profit", "profit", "pnl", "realized_profit") for item in items]
    profits = [value for value in profits if value is not None]
    wins = [value for value in profits if value > 0]; losses = [value for value in profits if value < 0]
    samples = len(items); breakeven = sum(value == 0 for value in profits)
    def average(values: list[float]) -> float: return sum(values) / len(values) if values else 0.0
    values = {"samples": samples, "wins": len(wins), "losses": len(losses), "breakeven": breakeven,
        "win_rate": len(wins) / samples if samples else 0.0, "avg_profit": average(wins), "avg_loss": average(losses),
        "avg_rr": average([x for item in items if (x := _number(item, "rr", "risk_reward")) is not None]),
        "avg_mae": average([x for item in items if (x := _number(item, "mae")) is not None]),
        "avg_mfe": average([x for item in items if (x := _number(item, "mfe")) is not None]),
        "avg_holding": average([x for item in items if (x := _number(item, "holding", "holding_time", "duration", "duration_seconds")) is not None]),
        "median_profit": float(median(wins)) if wins else 0.0, "median_loss": float(median(losses)) if losses else 0.0,
        "stddev_profit": float(pstdev(profits)) if len(profits) > 1 else 0.0}
    return values

class StatisticsCalculator:
    calculate = staticmethod(calculate_statistics)
