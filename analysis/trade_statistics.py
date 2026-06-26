"""Trade recorder and execution-consistency audit statistics for V27.4.

This module is intentionally post-entry only. It records completed trades and
compares dashboard exit profiles without changing direction, bias, entry,
score, or indicator logic.
"""

from __future__ import annotations

import csv
import os
import warnings
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


CSV_SCHEMA_VERSION = "V27_4_EXECUTION_CONSISTENCY_AUDIT"

AUDIT_FIELDS = [
    "trade_uuid", "decision_uuid", "decision_sequence_id", "market_state_sequence_id",
    "order_ticket", "position_ticket", "deal_ticket",
    "ai_intended_action", "ai_intended_bias", "ai_intended_mode", "ai_intended_bb_state",
    "ai_intended_management", "ai_intended_execution_state", "ai_intended_entry_price",
    "ai_intended_stop_loss", "ai_intended_take_profit", "ai_intended_tp1",
    "ai_intended_risk_distance", "ai_intended_planned_rr", "ai_intended_exit_style",
    "ai_intended_runner_enabled", "ai_intended_be_policy", "ai_intended_trail_policy",
    "ai_intended_position_size_factor",
    "executor_received_decision", "executor_received_action", "executor_received_sl",
    "executor_received_tp", "executor_received_management", "executor_payload_valid",
    "executor_final_gate_pass", "executor_broker_safety_pass", "executor_order_send_attempted",
    "executor_order_send_result", "executor_order_send_error",
    "dashboard_profile_at_entry", "dashboard_profile_at_exit",
    "dashboard_trade_management_enabled", "dashboard_be_enabled", "dashboard_trail_enabled",
    "dashboard_runner_enabled", "dashboard_profit_lock_enabled", "dashboard_time_exit_enabled",
    "dashboard_fixed_tp_enabled", "dashboard_runtime_sl_distance", "dashboard_runtime_tp_target",
    "dashboard_last_close_intent", "dashboard_effective_exit_owner",
    "broker_order_open_price", "broker_order_sl", "broker_order_tp",
    "broker_position_sl_at_close", "broker_position_tp_at_close", "broker_close_price",
    "broker_deal_reason", "broker_close_source", "actual_holding_seconds", "actual_profit_usd",
    "intent_vs_executor_match", "executor_vs_broker_sl_match", "executor_vs_broker_tp_match",
    "ai_management_vs_dashboard_match", "intended_exit_vs_actual_exit_match",
    "exit_timing_consistency", "rr_intent_vs_realized_ratio", "execution_drift_detected",
    "execution_drift_reason",
]

LEGACY_FIELDS = [
    "ticket", "symbol", "direction", "mode", "entry_time", "exit_time",
    "entry_price", "exit_price", "stop_loss", "take_profit", "exit_reason",
    "mfe", "mae", "net_profit", "duration", "dashboard_profile",
    "be_trigger_count", "be_trigger_price", "be_trigger_profit", "be_trigger_time",
    "be_trigger_age_seconds", "be_sl_price", "be_offset_usd", "be_stop_out",
    "realized_profit", "profit_before_be", "maximum_profit_after_be",
    "maximum_drawdown_after_be", "lost_opportunity_after_be", "be_false_trigger",
    "be_false_trigger_distance", "be_false_trigger_time", "be_survival_time_seconds",
    "capture_ratio_after_be", "post_sl_continuation_direction",
]

CSV_FIELDS = ["csv_schema_version", *AUDIT_FIELDS, *LEGACY_FIELDS]


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

    trade_uuid: str = ""
    decision_uuid: str = ""
    execution_drift_detected: bool = False
    execution_drift_reason: str = "NO_DRIFT"
    ai_intended_planned_rr: float = 0.0
    rr_intent_vs_realized_ratio: float = 0.0
    dashboard_effective_exit_owner: str = ""
    broker_close_source: str = ""
    actual_holding_seconds: float = 0.0


def append_completed_trade(trade: CompletedTrade, csv_path: Path | str | None = None) -> None:
    """Append one completed trade to trade_statistics.csv with a stable header."""
    path = resolve_trade_statistics_csv_path(csv_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    write_header = not path.exists() or path.stat().st_size == 0
    with path.open("a", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=CSV_FIELDS)
        if write_header:
            writer.writeheader()
        row = {field: "" for field in CSV_FIELDS}
        row.update(asdict(trade))
        row["csv_schema_version"] = CSV_SCHEMA_VERSION
        writer.writerow(row)


def _row_bool(row: dict[str, str], key: str) -> bool:
    return str(row.get(key, "")).strip().lower() in {"1", "true", "yes", "on"}


def _row_float(row: dict[str, str], key: str) -> float:
    try:
        return float(row.get(key, "") or 0)
    except ValueError:
        return 0.0


def _load_completed_trades_from_file(path: Path) -> list[CompletedTrade]:
    with path.open("r", newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        if reader.fieldnames is None:
            return []
        header_signature = [name.strip() for name in reader.fieldnames]
        trades: list[CompletedTrade] = []
        for row in reader:
            row_values = [str(value).strip() for value in row.values() if value is not None]
            if row_values[: len(header_signature)] == header_signature:
                warnings.warn("DUPLICATE_CSV_HEADER_DETECTED", RuntimeWarning, stacklevel=2)
                continue
            if row.get("csv_schema_version", CSV_SCHEMA_VERSION) not in {"", CSV_SCHEMA_VERSION}:
                warnings.warn(f"UNKNOWN_CSV_SCHEMA_VERSION:{row.get('csv_schema_version')}", RuntimeWarning, stacklevel=2)
            trades.append(
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
                    trade_uuid=row.get("trade_uuid", ""),
                    decision_uuid=row.get("decision_uuid", ""),
                    execution_drift_detected=_row_bool(row, "execution_drift_detected"),
                    execution_drift_reason=row.get("execution_drift_reason", "NO_DRIFT"),
                    ai_intended_planned_rr=_row_float(row, "ai_intended_planned_rr"),
                    rr_intent_vs_realized_ratio=_row_float(row, "rr_intent_vs_realized_ratio"),
                    dashboard_effective_exit_owner=row.get("dashboard_effective_exit_owner", ""),
                    broker_close_source=row.get("broker_close_source", row.get("close_source", "")),
                    actual_holding_seconds=_row_float(row, "actual_holding_seconds") or _row_float(row, "duration"),
                )
            )
        return trades


def load_completed_trades(csv_path: Path | str | None = None, *, include_archives: bool = False) -> list[CompletedTrade]:
    path = resolve_trade_statistics_csv_path(csv_path)
    if not path.exists():
        return []
    paths = [path]
    if include_archives:
        paths.extend(sorted((path.parent / "archive").glob("trade_statistics_legacy_*.csv")))
    trades: list[CompletedTrade] = []
    for item in paths:
        trades.extend(_load_completed_trades_from_file(item))
    return trades


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


def execution_consistency_metrics(trades: Iterable[CompletedTrade]) -> dict[str, object]:
    """Compute V27.4 execution consistency audit metrics without changing trading behavior."""
    items = list(trades)
    total = len(items)
    drifted = [t for t in items if t.execution_drift_detected or (t.execution_drift_reason and t.execution_drift_reason != "NO_DRIFT")]
    reason_counts = Counter(t.execution_drift_reason or "UNKNOWN_DRIFT" for t in drifted)
    owner_mismatches = [t for t in items if "EXIT_OWNER" in (t.execution_drift_reason or "")]
    sltp_mismatches = [t for t in items if "SL_TP" in (t.execution_drift_reason or "") or "BROKER" in (t.execution_drift_reason or "")]
    early_exits = [t for t in items if (t.execution_drift_reason or "") == "EARLY_EXIT_DRIFT"]
    profile_mismatches = [t for t in items if (t.execution_drift_reason or "") == "DASHBOARD_PROFILE_DRIFT"]
    management_mismatches = [t for t in items if (t.execution_drift_reason or "") == "MANAGEMENT_MODE_DRIFT"]
    realized_rr = [t.rr_intent_vs_realized_ratio for t in items if t.rr_intent_vs_realized_ratio]
    intended_rr = [t.ai_intended_planned_rr for t in items if t.ai_intended_planned_rr]
    layer_loss = defaultdict(float)
    for t in drifted:
        layer_loss[t.execution_drift_reason or "UNKNOWN_DRIFT"] += min(0.0, t.net_profit)
    worst_layer = min(layer_loss.items(), key=lambda item: item[1])[0] if layer_loss else "NO_DRIFT"
    return {
        "trades": total,
        "drift_rate": len(drifted) / total if total else 0.0,
        "drift_by_type": dict(reason_counts),
        "average_realized_rr_vs_intended_rr": _average(realized_rr),
        "average_intended_rr": _average(intended_rr),
        "exit_owner_mismatch_rate": len(owner_mismatches) / total if total else 0.0,
        "sl_tp_publication_mismatch_rate": len(sltp_mismatches) / total if total else 0.0,
        "early_exit_rate": len(early_exits) / total if total else 0.0,
        "profile_mismatch_rate": len(profile_mismatches) / total if total else 0.0,
        "management_mode_mismatch_rate": len(management_mismatches) / total if total else 0.0,
        "is_ai_intent_preserved": len(drifted) == 0,
        "executor_changing_trade": any(r in reason_counts for r in ("AI_TO_EXECUTOR_DRIFT", "EXECUTOR_TO_BROKER_DRIFT", "SL_TP_PUBLICATION_DRIFT")),
        "dashboard_changing_trade": any(r in reason_counts for r in ("DASHBOARD_PROFILE_DRIFT", "MANAGEMENT_MODE_DRIFT", "EXIT_OWNER_DRIFT", "EARLY_EXIT_DRIFT")),
        "broker_receiving_expected_sl_tp": not any(r in reason_counts for r in ("EXECUTOR_TO_BROKER_DRIFT", "SL_TP_PUBLICATION_DRIFT")),
        "largest_expectancy_loss_layer": worst_layer,
    }
