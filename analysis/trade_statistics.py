"""Trade recorder and exit-profile statistics for V27.3.

This module is intentionally post-entry only. It records completed trades and
compares dashboard exit profiles without changing direction, bias, entry,
score, or indicator logic.
"""

from __future__ import annotations

import csv
from collections import Counter, defaultdict
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Iterable

CSV_FIELDS = [
    "ticket", "symbol", "direction", "mode", "entry_time", "exit_time",
    "entry_price", "exit_price", "stop_loss", "take_profit", "exit_reason",
    "mfe", "mae", "net_profit", "duration", "dashboard_profile",
]


@dataclass(frozen=True)
class CompletedTrade:
    ticket: str
    symbol: str
    direction: str
    mode: str
    entry_time: str
    exit_time: str
    entry_price: float
    exit_price: float
    stop_loss: float
    take_profit: float
    exit_reason: str
    mfe: float
    mae: float
    net_profit: float
    duration: float
    dashboard_profile: str


def append_completed_trade(trade: CompletedTrade, csv_path: Path | str = "trade_statistics.csv") -> None:
    """Append one completed trade to trade_statistics.csv with a stable header."""
    path = Path(csv_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    write_header = not path.exists() or path.stat().st_size == 0
    with path.open("a", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=CSV_FIELDS)
        if write_header:
            writer.writeheader()
        writer.writerow(asdict(trade))


def load_completed_trades(csv_path: Path | str = "trade_statistics.csv") -> list[CompletedTrade]:
    path = Path(csv_path)
    if not path.exists():
        return []
    with path.open("r", newline="", encoding="utf-8") as handle:
        rows = csv.DictReader(handle)
        return [
            CompletedTrade(
                ticket=row["ticket"], symbol=row["symbol"], direction=row["direction"], mode=row["mode"],
                entry_time=row["entry_time"], exit_time=row["exit_time"],
                entry_price=float(row["entry_price"] or 0), exit_price=float(row["exit_price"] or 0),
                stop_loss=float(row["stop_loss"] or 0), take_profit=float(row["take_profit"] or 0),
                exit_reason=row["exit_reason"], mfe=float(row["mfe"] or 0), mae=float(row["mae"] or 0),
                net_profit=float(row["net_profit"] or 0), duration=float(row["duration"] or 0),
                dashboard_profile=row["dashboard_profile"],
            )
            for row in rows
        ]


def _average(values: list[float]) -> float:
    return sum(values) / len(values) if values else 0.0


def profile_success_metrics(trades: Iterable[CompletedTrade]) -> dict[str, dict[str, object]]:
    """Calculate required V27.3 success metrics by dashboard profile."""
    grouped: dict[str, list[CompletedTrade]] = defaultdict(list)
    for trade in trades:
        grouped[trade.dashboard_profile].append(trade)

    metrics: dict[str, dict[str, object]] = {}
    for profile, items in grouped.items():
        wins = [t.net_profit for t in items if t.net_profit > 0]
        losses = [t.net_profit for t in items if t.net_profit < 0]
        gross_win = sum(wins)
        gross_loss = abs(sum(losses))
        avg_mfe = _average([t.mfe for t in items])
        metrics[profile] = {
            "trades": len(items),
            "win_rate": len(wins) / len(items) if items else 0.0,
            "average_win": _average(wins),
            "average_loss": _average(losses),
            "profit_factor": gross_win / gross_loss if gross_loss else (float("inf") if gross_win else 0.0),
            "expectancy": _average([t.net_profit for t in items]),
            "average_mfe": avg_mfe,
            "average_mae": _average([t.mae for t in items]),
            "mfe_capture_ratio": _average([t.net_profit / t.mfe for t in items if t.mfe > 0]),
            "exit_reason_distribution": dict(Counter(t.exit_reason for t in items)),
        }
    return metrics


def evidence_gate(metrics: dict[str, dict[str, object]], min_trades_per_profile: int = 30) -> tuple[bool, str]:
    """Require statistical evidence before making any optimization decision."""
    if not metrics:
        return False, "NO_TRADE_STATISTICS_AVAILABLE"
    underpowered = [p for p, data in metrics.items() if int(data.get("trades", 0)) < min_trades_per_profile]
    if underpowered:
        return False, "INSUFFICIENT_SAMPLE_SIZE:" + ",".join(sorted(underpowered))
    return True, "STATISTICAL_EVIDENCE_READY"
