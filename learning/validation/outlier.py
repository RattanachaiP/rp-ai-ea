"""Non-destructive IQR outlier marking."""
from __future__ import annotations
from collections.abc import Iterable, Mapping
import math

def _quartile(values: list[float], fraction: float) -> float:
    position = (len(values) - 1) * fraction; low = int(position); high = min(low + 1, len(values) - 1)
    return values[low] + (values[high] - values[low]) * (position - low)

def detect_outliers(values: Iterable[float], *, multiplier: float = 1.5) -> list[bool]:
    """Return an aligned boolean mask; data is never discarded or changed."""
    items = [float(value) for value in values]
    if len(items) < 4: return [False] * len(items)
    ordered = sorted(items); q1, q3 = _quartile(ordered, .25), _quartile(ordered, .75); spread = q3 - q1
    low, high = q1 - multiplier * spread, q3 + multiplier * spread
    return [not math.isfinite(value) or value < low or value > high for value in items]

def mark_outliers(records: Iterable[Mapping[str, object]]) -> list[dict[str, object]]:
    """Copy records and attach flags for profit, loss, and holding-time extremes."""
    items = [dict(record) for record in records]
    def number(record: Mapping[str, object], keys: tuple[str, ...]) -> float:
        for key in keys:
            try: return float(record[key])
            except (KeyError, TypeError, ValueError): continue
        return 0.0
    profit = [number(item, ("net_profit", "profit", "pnl")) for item in items]
    holding = [number(item, ("holding_time", "holding", "duration", "duration_seconds")) for item in items]
    profit_flags, holding_flags = detect_outliers(profit), detect_outliers(holding)
    return [{**item, "outliers": {"extreme_profit": flag and value > 0, "extreme_loss": flag and value < 0,
             "extreme_holding_time": holding_flags[index]}} for index, (item, flag, value) in enumerate(zip(items, profit_flags, profit))]
find_outliers = detect_outliers
