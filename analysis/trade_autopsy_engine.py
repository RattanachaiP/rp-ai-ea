import csv
import json
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path

MEMORY_FILE = Path(r"C:\Users\trader\AppData\Roaming\MetaQuotes\Terminal\Common\Files\RP_AI_EA\trade_memory.csv")
LOCAL_MEMORY_FILE = Path(__file__).with_name("trade_memory.csv")
OUTPUT_DIR = Path(__file__).resolve().parents[1] / "logs" / "trade_autopsy"

LOSS_BUCKETS = {
    "WRONG_DIRECTION", "LATE_ENTRY", "EXHAUSTION_ENTRY", "COUNTERTREND_ENTRY", "CHOP_ENTRY",
    "BB_MIDDLE_ROTATION", "PROFIT_NOT_PROTECTED", "EXIT_TOO_LATE", "SL_TOO_WIDE", "RUNNER_FAILED",
    "THESIS_DECAY", "MOMENTUM_FADED", "EXECUTION_DELAY", "SPREAD_OR_SLIPPAGE", "UNKNOWN",
}
# V28's mandatory loss taxonomy.  The older, more granular buckets remain in
# ``autopsy_primary_reason`` for diagnosis, but every losing trade is also
# assigned exactly one of these decision-engine categories.
LOSS_CLASSIFICATIONS = {
    "DIRECTION_ERROR", "ENTRY_LOCATION_ERROR", "RISK_GEOMETRY_ERROR",
    "EXIT_ERROR", "DECISION_LOGIC_ERROR",
}
WIN_BUCKETS = {
    "CLEAN_TREND_CAPTURE", "SCALP_CAPTURE", "RUNNER_CAPTURE", "PULLBACK_RESUMPTION_SUCCESS",
    "PROFIT_LOCK_SUCCESS", "FAST_EXIT_SUCCESS", "SHADOW_AVOIDED", "OTHER_WIN",
}
AUTOPSY_FIELDS = [
    "ticket", "symbol", "magic", "slot", "leg_type", "direction", "open_time", "close_time", "holding_time_sec",
    "bias", "mode", "BB_state", "score_gap", "entry_window_state", "entry_window_score", "trend_phase",
    "short_term_countertrend", "exhaustion_score_at_entry", "entry_age_after_move",
    "original_management_mode", "effective_management_mode", "exit_authority_owner", "exit_reason",
    "profit_lock_triggered", "breakeven_triggered", "runner_timeout_triggered", "runner_momentum_decay_triggered",
    "hard_loss_cap_triggered", "realized_profit", "realized_R", "planned_R", "MFE", "MAE",
    "MFE_to_realized_ratio", "MAE_to_realized_loss_ratio", "max_floating_profit", "max_floating_loss",
    "profit_given_back", "shadow_direction", "shadow_MFE", "shadow_MAE", "shadow_estimated_profit",
    "original_vs_opposite_profit", "would_opposite_have_won", "autopsy_primary_reason", "autopsy_secondary_reason",
    "autopsy_confidence", "evidence_fields_used", "autopsy_result_bucket",
    "loss_classification", "direction_accuracy", "entry_quality", "exit_efficiency",
    "net_expectancy_contribution",
]


def safe_float(value, default=0.0):
    try:
        if value is None or value == "":
            return default
        return float(value)
    except Exception:
        return default


def safe_bool(value):
    if isinstance(value, bool):
        return value
    return str(value or "").strip().upper() in {"1", "TRUE", "YES", "Y", "ACTIVE", "TRIGGERED"}


def first(row, names, default=""):
    for name in names:
        value = row.get(name)
        if value not in (None, ""):
            return value
    return default


def parse_time(value):
    text = str(value or "").strip().replace("T", " ").replace("Z", "")
    if not text:
        return None
    for fmt, length in (("%Y-%m-%d %H:%M:%S", 19), ("%Y-%m-%d %H:%M", 16), ("%Y.%m.%d %H:%M:%S", 19), ("%Y.%m.%d %H:%M", 16)):
        try:
            return datetime.strptime(text[:length], fmt)
        except Exception:
            pass
    try:
        return datetime.fromisoformat(text)
    except Exception:
        return None


def trade_day(record):
    dt = parse_time(record.get("close_time")) or parse_time(record.get("open_time"))
    return dt.strftime("%Y%m%d") if dt else "UNKNOWN_DAY"


def holding_seconds(row):
    explicit = safe_float(first(row, ("holding_time_sec", "hold_seconds", "duration_sec"), 0), 0.0)
    if explicit > 0:
        return int(explicit)
    minutes = safe_float(first(row, ("holding_minutes", "hold_minutes", "duration_minutes"), 0), 0.0)
    if minutes > 0:
        return int(minutes * 60)
    opened = parse_time(first(row, ("open_time", "entry_time", "opened_at")))
    closed = parse_time(first(row, ("close_time", "exit_time", "closed_at", "timestamp", "time")))
    return int((closed - opened).total_seconds()) if opened and closed and closed >= opened else 0


def planned_risk(row):
    explicit = abs(safe_float(first(row, ("planned_risk", "planned_sl_loss", "planned_sl_risk", "risk_amount"), 0), 0.0))
    if explicit > 0:
        return explicit
    return abs(safe_float(first(row, ("planned_R", "planned_r", "initial_risk_r"), 1), 1.0))


def build_record(row):
    profit = safe_float(first(row, ("realized_profit", "profit", "pnl", "net_profit"), 0), 0.0)
    risk = planned_risk(row)
    realized_r = safe_float(first(row, ("realized_R", "realized_r", "r_multiple"), 0), 0.0) or (profit / risk if risk else 0.0)
    mfe = safe_float(first(row, ("MFE", "real_MFE", "max_floating_profit", "max_profit"), 0), 0.0)
    mae = safe_float(first(row, ("MAE", "real_MAE", "max_floating_loss", "max_loss"), 0), 0.0)
    max_fp = safe_float(first(row, ("max_floating_profit", "MFE", "real_MFE"), mfe), mfe)
    max_fl = safe_float(first(row, ("max_floating_loss", "MAE", "real_MAE"), mae), mae)
    rec = {
        "ticket": first(row, ("ticket", "order", "position_id", "deal")),
        "symbol": first(row, ("symbol",), "XAUUSD"),
        "magic": first(row, ("magic", "magic_number")),
        "slot": first(row, ("slot", "rp_slot", "active_execution_slot")),
        "leg_type": first(row, ("leg_type", "active_execution_leg", "leg", "entry_type")),
        "direction": normalize_direction(first(row, ("direction", "side", "type", "action", "bias"))),
        "open_time": first(row, ("open_time", "entry_time", "opened_at")),
        "close_time": first(row, ("close_time", "exit_time", "closed_at", "timestamp", "time")),
        "holding_time_sec": holding_seconds(row),
        "bias": first(row, ("bias", "action", "direction")),
        "mode": first(row, ("mode", "market_mode")),
        "BB_state": first(row, ("BB_state", "bb_state", "bb")),
        "score_gap": safe_float(first(row, ("score_gap", "gap"), 0), 0.0),
        "entry_window_state": first(row, ("entry_window_state", "execution_window_state")),
        "entry_window_score": safe_float(first(row, ("entry_window_score",), 0), 0.0),
        "trend_phase": first(row, ("trend_phase",)),
        "short_term_countertrend": first(row, ("short_term_countertrend",)),
        "exhaustion_score_at_entry": safe_float(first(row, ("exhaustion_score_at_entry", "exhaustion_score", "runner_risk_score"), 0), 0.0),
        "entry_age_after_move": safe_float(first(row, ("entry_age_after_move", "expansion_candle_count", "move_age"), 0), 0.0),
        "original_management_mode": first(row, ("original_management_mode", "management", "mgmt")),
        "effective_management_mode": first(row, ("effective_management_mode", "management", "mgmt")),
        "exit_authority_owner": first(row, ("exit_authority_owner", "authority_owner")),
        "exit_reason": first(row, ("exit_reason", "reason", "close_reason")),
        "profit_lock_triggered": safe_bool(first(row, ("profit_lock_triggered", "profit_protection_triggered"), False)),
        "breakeven_triggered": safe_bool(first(row, ("breakeven_triggered", "be_triggered"), False)),
        "runner_timeout_triggered": safe_bool(first(row, ("runner_timeout_triggered",), False)),
        "runner_momentum_decay_triggered": safe_bool(first(row, ("runner_momentum_decay_triggered",), False)),
        "hard_loss_cap_triggered": safe_bool(first(row, ("hard_loss_cap_triggered",), False)),
        "realized_profit": round(profit, 2),
        "realized_R": round(realized_r, 3),
        "planned_R": round(risk, 3),
        "MFE": round(mfe, 3),
        "MAE": round(mae, 3),
        "MFE_to_realized_ratio": round(mfe / profit, 3) if profit > 0 else 0.0,
        "MAE_to_realized_loss_ratio": round(abs(mae) / abs(profit), 3) if profit < 0 else 0.0,
        "max_floating_profit": round(max_fp, 3),
        "max_floating_loss": round(max_fl, 3),
        "profit_given_back": round(max(0.0, max_fp - max(profit, 0.0)), 3),
        "shadow_direction": first(row, ("shadow_direction",)),
        "shadow_MFE": safe_float(first(row, ("shadow_MFE",), 0), 0.0),
        "shadow_MAE": safe_float(first(row, ("shadow_MAE",), 0), 0.0),
        "shadow_estimated_profit": safe_float(first(row, ("shadow_estimated_profit", "shadow_profit"), 0), 0.0),
        "original_vs_opposite_profit": safe_float(first(row, ("original_vs_opposite_profit",), 0), 0.0),
        "would_opposite_have_won": safe_bool(first(row, ("would_opposite_have_won",), False)),
    }
    classify(rec)
    return rec


def normalize_direction(value):
    text = str(value or "").upper()
    if "BUY" in text:
        return "BUY"
    if "SELL" in text:
        return "SELL"
    return text or "UNKNOWN"


def classify(rec):
    profit = rec["realized_profit"]
    evidence = []
    secondary = ""
    confidence = 0.55
    reason = "UNKNOWN"
    if profit < 0:
        explicit = str(rec.get("exit_reason", "")).upper()
        if rec["would_opposite_have_won"] or rec["original_vs_opposite_profit"] < 0:
            reason, confidence = "WRONG_DIRECTION", 0.86; evidence += ["would_opposite_have_won", "original_vs_opposite_profit"]
        elif rec["profit_given_back"] > abs(profit) * 0.75 and rec["MFE"] > 0:
            reason, confidence = "PROFIT_NOT_PROTECTED", 0.84; evidence += ["MFE", "realized_profit", "profit_given_back"]
        elif rec["exhaustion_score_at_entry"] >= 70:
            reason, confidence = "EXHAUSTION_ENTRY", 0.82; evidence.append("exhaustion_score_at_entry")
        elif str(rec["short_term_countertrend"]).upper() in {"TRUE", "YES", "STRONG", "ACTIVE"}:
            reason, confidence = "COUNTERTREND_ENTRY", 0.78; evidence.append("short_term_countertrend")
        elif rec["entry_age_after_move"] >= 4 or "LATE" in explicit:
            reason, confidence = "LATE_ENTRY", 0.76; evidence.append("entry_age_after_move")
        elif "MIDDLE" in str(rec["BB_state"]).upper():
            reason, confidence = "BB_MIDDLE_ROTATION", 0.74; evidence.append("BB_state")
        elif str(rec["mode"]).upper() == "TRANSITION" and str(rec["BB_state"]).upper() == "NORMAL":
            reason, confidence = "CHOP_ENTRY", 0.72; evidence += ["mode", "BB_state"]
        elif rec["runner_timeout_triggered"] or "RUNNER" in str(rec["leg_type"]).upper():
            reason, confidence = "RUNNER_FAILED", 0.72; evidence += ["leg_type", "runner_timeout_triggered"]
        elif rec["runner_momentum_decay_triggered"] or "MOMENTUM" in explicit:
            reason, confidence = "MOMENTUM_FADED", 0.72; evidence += ["runner_momentum_decay_triggered", "exit_reason"]
        elif rec["hard_loss_cap_triggered"] or rec["MAE_to_realized_loss_ratio"] >= 0.95:
            reason, confidence = "SL_TOO_WIDE", 0.68; evidence += ["hard_loss_cap_triggered", "MAE_to_realized_loss_ratio"]
        elif "SPREAD" in explicit or "SLIPPAGE" in explicit:
            reason, confidence = "SPREAD_OR_SLIPPAGE", 0.8; evidence.append("exit_reason")
        elif "DELAY" in explicit:
            reason, confidence = "EXECUTION_DELAY", 0.75; evidence.append("exit_reason")
        else:
            evidence.append("realized_profit")
        if reason != "PROFIT_NOT_PROTECTED" and rec["profit_given_back"] > 0:
            secondary = "PROFIT_NOT_PROTECTED"
    elif profit > 0:
        if "RUNNER" in str(rec["leg_type"]).upper() or "RUNNER" in str(rec["effective_management_mode"]).upper():
            reason = "RUNNER_CAPTURE"
        elif rec["profit_lock_triggered"] or rec["breakeven_triggered"]:
            reason = "PROFIT_LOCK_SUCCESS"
        elif rec["would_opposite_have_won"] is False and rec["shadow_direction"]:
            reason = "SHADOW_AVOIDED"
        elif rec["holding_time_sec"] and rec["holding_time_sec"] <= 120:
            reason = "FAST_EXIT_SUCCESS"
        elif "PULLBACK" in str(rec["trend_phase"]).upper() or "RESUMPTION" in str(rec["trend_phase"]).upper():
            reason = "PULLBACK_RESUMPTION_SUCCESS"
        elif str(rec["mode"]).upper() == "TREND":
            reason = "CLEAN_TREND_CAPTURE"
        elif "SCALP" in str(rec["effective_management_mode"]).upper():
            reason = "SCALP_CAPTURE"
        else:
            reason = "OTHER_WIN"
        confidence = 0.7
        evidence.append("realized_profit")
    else:
        reason = "UNKNOWN"
        evidence.append("realized_profit")
    rec["autopsy_primary_reason"] = reason
    rec["autopsy_secondary_reason"] = secondary
    rec["autopsy_confidence"] = round(confidence, 2)
    rec["evidence_fields_used"] = "|".join(evidence)
    rec["autopsy_result_bucket"] = "LOSS" if profit < 0 else "WIN" if profit > 0 else "FLAT"
    _add_v28_required_metrics(rec)


def _add_v28_required_metrics(rec):
    """Attach the V28 completed-trade metrics without changing live decisions.

    ``net_expectancy_contribution`` is the closed P/L contribution of one
    trade.  The mean of this field over a cohort is that cohort's expectancy;
    keeping it per trade makes capital-damage rankings additive and auditable.
    """
    profit = rec["realized_profit"]
    mfe = rec["MFE"]
    primary = rec["autopsy_primary_reason"]
    secondary = rec["autopsy_secondary_reason"]

    rec["direction_accuracy"] = (
        "INCORRECT" if rec["would_opposite_have_won"] or rec["original_vs_opposite_profit"] < 0
        else "CORRECT" if profit > 0
        else "UNKNOWN"
    )
    rec["entry_quality"] = (
        "POOR" if primary in {"EXHAUSTION_ENTRY", "COUNTERTREND_ENTRY", "LATE_ENTRY", "BB_MIDDLE_ROTATION", "CHOP_ENTRY"}
        else "GOOD" if profit > 0
        else "UNKNOWN"
    )
    # A positive MFE is required before exit capture can be evaluated.  A
    # losing trade that never turned positive is not an exit-management error.
    rec["exit_efficiency"] = round(max(profit, 0.0) / mfe, 3) if mfe > 0 else None
    rec["net_expectancy_contribution"] = round(profit, 2)

    if profit >= 0:
        rec["loss_classification"] = "NOT_A_LOSS"
    elif rec["direction_accuracy"] == "INCORRECT":
        rec["loss_classification"] = "DIRECTION_ERROR"
    elif rec["entry_quality"] == "POOR":
        rec["loss_classification"] = "ENTRY_LOCATION_ERROR"
    elif primary == "SL_TOO_WIDE":
        rec["loss_classification"] = "RISK_GEOMETRY_ERROR"
    elif primary == "PROFIT_NOT_PROTECTED" or secondary == "PROFIT_NOT_PROTECTED":
        rec["loss_classification"] = "EXIT_ERROR"
    else:
        # This is intentionally a diagnosis, not a runtime gate.  It identifies
        # approvals that lack evidence for direction, location, geometry, or
        # post-entry exit failure and must be investigated at the score logic.
        rec["loss_classification"] = "DECISION_LOGIC_ERROR"


def blank_summary(day):
    return {"date": day, "total_trades": 0, "win_count": 0, "loss_count": 0, "gross_win": 0.0, "gross_loss": 0.0,
            "largest_win": 0.0, "largest_loss": 0.0, "loss_bucket_distribution": Counter(), "loss_bucket_total_damage": defaultdict(float),
            "win_bucket_distribution": Counter(), "MFE_total": 0.0, "realized_positive_total": 0.0, "MAE_loss_total": 0.0,
            "realized_loss_total": 0.0, "shadow_opposite_wins": 0, "shadow_opposite_count": 0, "shadow_opposite_net_result": 0.0,
            "late_entry_loss_count": 0, "exhaustion_entry_loss_count": 0, "profit_not_protected_count": 0, "runner_failed_count": 0,
            "profit_given_back_total": 0.0}


def add_summary(summary, rec):
    p = rec["realized_profit"]
    summary["total_trades"] += 1
    summary["largest_win"] = max(summary["largest_win"], p)
    summary["largest_loss"] = min(summary["largest_loss"], p)
    summary["MFE_total"] += max(0.0, rec["MFE"])
    summary["realized_positive_total"] += max(0.0, p)
    summary["profit_given_back_total"] += rec["profit_given_back"]
    if rec["shadow_direction"]:
        summary["shadow_opposite_count"] += 1
        summary["shadow_opposite_wins"] += 1 if rec["would_opposite_have_won"] else 0
        summary["shadow_opposite_net_result"] += rec["shadow_estimated_profit"]
    if p > 0:
        summary["win_count"] += 1; summary["gross_win"] += p; summary["win_bucket_distribution"][rec["autopsy_primary_reason"]] += 1
    elif p < 0:
        loss = abs(p); summary["loss_count"] += 1; summary["gross_loss"] += loss; summary["realized_loss_total"] += loss
        summary["MAE_loss_total"] += abs(rec["MAE"])
        summary["loss_bucket_distribution"][rec["autopsy_primary_reason"]] += 1
        summary["loss_bucket_total_damage"][rec["autopsy_primary_reason"]] += p
        summary.setdefault("loss_classification_distribution", Counter())[rec["loss_classification"]] += 1
        summary.setdefault("loss_classification_total_damage", defaultdict(float))[rec["loss_classification"]] += p
        summary["late_entry_loss_count"] += int(rec["autopsy_primary_reason"] == "LATE_ENTRY")
        summary["exhaustion_entry_loss_count"] += int(rec["autopsy_primary_reason"] == "EXHAUSTION_ENTRY")
        summary["profit_not_protected_count"] += int(rec["autopsy_primary_reason"] == "PROFIT_NOT_PROTECTED" or rec["autopsy_secondary_reason"] == "PROFIT_NOT_PROTECTED")
        summary["runner_failed_count"] += int(rec["autopsy_primary_reason"] == "RUNNER_FAILED")


def finalize(summary):
    total = summary["total_trades"]; wins = summary["win_count"]; losses = summary["loss_count"]
    avg_win = summary["gross_win"] / wins if wins else 0.0
    avg_loss = summary["gross_loss"] / losses if losses else 0.0
    result = dict(summary)
    result.update({
        "win_rate": round(wins / total, 4) if total else 0.0,
        "avg_win": round(avg_win, 2), "avg_loss": round(avg_loss, 2),
        "profit_factor": round(summary["gross_win"] / summary["gross_loss"], 3) if summary["gross_loss"] else 0.0,
        "expectancy": round(((wins / total) * avg_win - (losses / total) * avg_loss), 2) if total else 0.0,
        "MFE_capture_efficiency": round(summary["realized_positive_total"] / summary["MFE_total"], 3) if summary["MFE_total"] else 0.0,
        "MAE_containment_score": round(1 - (summary["realized_loss_total"] / summary["MAE_loss_total"]), 3) if summary["MAE_loss_total"] else 0.0,
        "shadow_opposite_win_rate": round(summary["shadow_opposite_wins"] / summary["shadow_opposite_count"], 4) if summary["shadow_opposite_count"] else 0.0,
        "shadow_opposite_net_result": round(summary["shadow_opposite_net_result"], 2),
        "average_profit_given_back": round(summary["profit_given_back_total"] / total, 3) if total else 0.0,
        "root_cause_ranking_by_capital_damage": sorted(
            ({"bucket": k, "damage": round(v, 2)} for k, v in summary["loss_bucket_total_damage"].items()),
            key=lambda item: item["damage"],
        ),
        "mandatory_loss_classification_ranking_by_capital_damage": sorted(
            ({"classification": k, "damage": round(v, 2)} for k, v in summary.get("loss_classification_total_damage", {}).items()),
            key=lambda item: item["damage"],
        ),
    })
    result["loss_bucket_distribution"] = dict(summary["loss_bucket_distribution"])
    result["loss_bucket_total_damage"] = {k: round(v, 2) for k, v in summary["loss_bucket_total_damage"].items()}
    result["loss_classification_distribution"] = dict(summary.get("loss_classification_distribution", {}))
    result["loss_classification_total_damage"] = {k: round(v, 2) for k, v in summary.get("loss_classification_total_damage", {}).items()}
    result["win_bucket_distribution"] = dict(summary["win_bucket_distribution"])
    for k in ("gross_win", "gross_loss", "MFE_total", "realized_positive_total", "MAE_loss_total", "realized_loss_total", "profit_given_back_total"):
        result.pop(k, None)
    return result


def generate_autopsies(memory_file=None, output_dir=OUTPUT_DIR):
    path = Path(memory_file) if memory_file else (MEMORY_FILE if MEMORY_FILE.exists() else LOCAL_MEMORY_FILE)
    output_dir = Path(output_dir)
    if not path.exists():
        return {"available": False, "reason": f"trade_memory.csv not found: {path}", "records": [], "summaries": {}}
    records = []
    with open(path, "r", encoding="utf-8", errors="ignore", newline="") as f:
        for row in csv.DictReader(f):
            if row:
                records.append(build_record(row))
    summaries = defaultdict(lambda: None)
    for rec in records:
        day = trade_day(rec)
        if summaries[day] is None:
            summaries[day] = blank_summary(day)
        add_summary(summaries[day], rec)
    output_dir.mkdir(parents=True, exist_ok=True)
    finalized = {}
    by_day = defaultdict(list)
    for rec in records:
        by_day[trade_day(rec)].append(rec)
    for day, day_records in by_day.items():
        csv_path = output_dir / f"trade_autopsy_{day}.csv"
        with open(csv_path, "w", encoding="utf-8", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=AUTOPSY_FIELDS, extrasaction="ignore")
            writer.writeheader(); writer.writerows(day_records)
        finalized[day] = finalize(summaries[day])
        (output_dir / f"trade_autopsy_summary_{day}.json").write_text(json.dumps(finalized[day], indent=2, sort_keys=True), encoding="utf-8")
    return {"available": True, "source": str(path), "output_dir": str(output_dir), "records": records, "summaries": finalized}


def main():
    result = generate_autopsies()
    if not result["available"]:
        print(result["reason"]); return 1
    print(f"Trade autopsy records: {len(result['records'])}")
    print(f"Output directory: {result['output_dir']}")
    for day, summary in sorted(result["summaries"].items()):
        print(f"{day}: trades={summary['total_trades']} PF={summary['profit_factor']} expectancy={summary['expectancy']}")
        for i, item in enumerate(summary["root_cause_ranking_by_capital_damage"], 1):
            print(f"  {i}. {item['bucket']} = {item['damage']:.2f}")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
