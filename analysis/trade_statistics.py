"""Trade recorder and exit-profile statistics for V27.3.

This module is intentionally post-entry only. It records completed trades and
compares dashboard exit profiles without changing direction, bias, entry,
score, or indicator logic.
"""

from __future__ import annotations

import csv
import os
from collections import Counter, defaultdict
from statistics import median
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Iterable

DEFAULT_TRADE_STATISTICS_CSV_PATH = Path(os.environ.get(
    "TRADE_STATISTICS_CSV_PATH",
    r"C:\Users\rp_fu\AppData\Roaming\MetaQuotes\Terminal\Common\Files\RP_AI_EA\analysis\trade_statistics.csv",
))


def resolve_trade_statistics_csv_path(csv_path: Path | str | None = None) -> Path:
    """Return the authoritative completed-trade CSV path used by MT5 FILE_COMMON."""
    if csv_path is None or str(csv_path) == "":
        return DEFAULT_TRADE_STATISTICS_CSV_PATH
    return Path(csv_path)


CSV_FIELDS = [
    "ticket", "symbol", "direction", "mode", "entry_time", "exit_time",
    "entry_price", "exit_price", "stop_loss", "take_profit", "exit_reason",
    "mfe", "mae", "net_profit", "duration", "dashboard_profile",
    "be_trigger_count", "be_trigger_price", "be_trigger_profit", "be_trigger_time",
    "be_trigger_age_seconds", "be_sl_price", "be_offset_usd", "be_stop_out",
    "realized_profit", "profit_before_be", "maximum_profit_after_be",
    "maximum_drawdown_after_be", "lost_opportunity_after_be", "be_false_trigger",
    "be_false_trigger_distance", "be_false_trigger_time", "be_survival_time_seconds",
    "capture_ratio_after_be",
    "post_sl_continuation_direction",
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
    be_trigger_count: int = 0
    be_trigger_price: float = 0.0
    be_trigger_profit: float = 0.0
    be_trigger_time: str = ""
    be_trigger_age_seconds: float = 0.0
    be_sl_price: float = 0.0
    be_offset_usd: float = 0.0
    be_stop_out: bool = False
    realized_profit: float = 0.0
    profit_before_be: float = 0.0
    maximum_profit_after_be: float = 0.0
    maximum_drawdown_after_be: float = 0.0
    lost_opportunity_after_be: float = 0.0
    be_false_trigger: bool = False
    be_false_trigger_distance: float = 0.0
    be_false_trigger_time: str = ""
    be_survival_time_seconds: float = 0.0
    capture_ratio_after_be: float = 0.0
    post_sl_continuation_direction: str = ""


def append_completed_trade(trade: CompletedTrade, csv_path: Path | str | None = None) -> None:
    """Append one completed trade to trade_statistics.csv with a stable header."""
    path = resolve_trade_statistics_csv_path(csv_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    write_header = not path.exists() or path.stat().st_size == 0
    with path.open("a", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=CSV_FIELDS)
        if write_header:
            writer.writeheader()
        writer.writerow(asdict(trade))


def _row_bool(row: dict[str, str], key: str) -> bool:
    return str(row.get(key, "")).strip().lower() in {"1", "true", "yes", "on"}


def _row_float(row: dict[str, str], key: str) -> float:
    try:
        return float(row.get(key, "") or 0)
    except ValueError:
        return 0.0


def load_completed_trades(csv_path: Path | str | None = None) -> list[CompletedTrade]:
    path = resolve_trade_statistics_csv_path(csv_path)
    if not path.exists():
        return []
    with path.open("r", newline="", encoding="utf-8") as handle:
        rows = csv.DictReader(handle)
        return [
            CompletedTrade(
                ticket=row.get("ticket", ""), symbol=row.get("symbol", ""), direction=row.get("direction", ""), mode=row.get("mode", row.get("trade_mode", "")),
                entry_time=row.get("entry_time", ""), exit_time=row.get("exit_time", ""),
                entry_price=_row_float(row, "entry_price"), exit_price=_row_float(row, "exit_price"),
                stop_loss=_row_float(row, "stop_loss"), take_profit=_row_float(row, "take_profit"),
                exit_reason=row.get("exit_reason", row.get("broker_exit_reason", "")), mfe=_row_float(row, "mfe"), mae=_row_float(row, "mae"),
                net_profit=_row_float(row, "net_profit") or _row_float(row, "realized_profit_usd"), duration=_row_float(row, "duration"),
                dashboard_profile=row.get("dashboard_profile", row.get("dashboard_profile_at_entry", "")),
                be_trigger_count=int(_row_float(row, "be_trigger_count") or (1 if _row_bool(row, "be_enabled") else 0)),
                be_trigger_price=_row_float(row, "be_trigger_price"),
                be_trigger_profit=_row_float(row, "be_trigger_profit") or _row_float(row, "be_trigger_profit_usd"),
                be_trigger_time=row.get("be_trigger_time", ""),
                be_trigger_age_seconds=_row_float(row, "be_trigger_age_seconds") or _row_float(row, "be_trigger_after_seconds"),
                be_sl_price=_row_float(row, "be_sl_price"),
                be_offset_usd=_row_float(row, "be_offset_usd"),
                be_stop_out=_row_bool(row, "be_stop_out"),
                realized_profit=_row_float(row, "realized_profit") or _row_float(row, "net_profit"),
                profit_before_be=_row_float(row, "profit_before_be") or _row_float(row, "profit_before_be_stop_out"),
                maximum_profit_after_be=_row_float(row, "maximum_profit_after_be") or _row_float(row, "max_profit_after_be_trigger"),
                maximum_drawdown_after_be=_row_float(row, "maximum_drawdown_after_be"),
                lost_opportunity_after_be=_row_float(row, "lost_opportunity_after_be"),
                be_false_trigger=_row_bool(row, "be_false_trigger"),
                be_false_trigger_distance=_row_float(row, "be_false_trigger_distance"),
                be_false_trigger_time=row.get("be_false_trigger_time", ""),
                be_survival_time_seconds=_row_float(row, "be_survival_time_seconds"),
                capture_ratio_after_be=_row_float(row, "capture_ratio_after_be"),
                post_sl_continuation_direction=row.get("post_sl_continuation_direction", ""),
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
        be_triggers = [t for t in items if t.be_trigger_count > 0]
        be_stop_outs = [t for t in items if t.be_stop_out]
        sl_hits = [t for t in items if "SL" in t.exit_reason.upper() or "STOP" in t.exit_reason.upper()]
        tp_hits = [t for t in items if "TP" in t.exit_reason.upper() or "TAKE_PROFIT" in t.exit_reason.upper()]
        post_sl_continuation = Counter(
            t.post_sl_continuation_direction for t in sl_hits if t.post_sl_continuation_direction
        )
        false_triggers = [t for t in be_stop_outs if t.be_false_trigger]
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
            "sl_hit_count": len(sl_hits),
            "sl_hit_rate": len(sl_hits) / len(items) if items else 0.0,
            "tp_hit_count": len(tp_hits),
            "tp_hit_rate": len(tp_hits) / len(items) if items else 0.0,
            "be_count": sum(t.be_trigger_count for t in be_triggers),
            "average_holding_time": _average([t.duration for t in items]),
            "post_sl_continuation_direction": dict(post_sl_continuation),
            "BE_TRIGGER_COUNT": sum(t.be_trigger_count for t in be_triggers),
            "BE_STOP_OUT_COUNT": len(be_stop_outs),
            "BE_STOP_OUT_RATE": len(be_stop_outs) / len(be_triggers) if be_triggers else 0.0,
            "FALSE_BE_RATE": len(false_triggers) / len(be_stop_outs) if be_stop_outs else 0.0,
            "BE_FALSE_TRIGGER": len(false_triggers),
            "AVG_PROFIT_BEFORE_BE_STOP_OUT": _average([t.profit_before_be for t in be_stop_outs]),
            "AVG_LOST_OPPORTUNITY_AFTER_BE": _average([t.lost_opportunity_after_be for t in be_stop_outs]),
            "AVG_CAPTURE_RATIO_AFTER_BE": _average([t.capture_ratio_after_be for t in be_triggers]),
            "AVERAGE_BE_SURVIVAL_TIME": _average([t.be_survival_time_seconds for t in be_stop_outs if t.be_survival_time_seconds > 0]),
            "MEDIAN_BE_SURVIVAL_TIME": median([t.be_survival_time_seconds for t in be_stop_outs if t.be_survival_time_seconds > 0]) if any(t.be_survival_time_seconds > 0 for t in be_stop_outs) else 0.0,
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
