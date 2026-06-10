import csv
from collections import defaultdict
from datetime import datetime
from pathlib import Path

MEMORY_FILE = Path(
    r"C:\Users\trader\AppData\Roaming\MetaQuotes\Terminal\Common\Files\RP_AI_EA\trade_memory.csv"
)
LOCAL_MEMORY_FILE = Path(__file__).with_name("trade_memory.csv")


def safe_float(value, default=0.0):
    try:
        return float(value or default)
    except Exception:
        return default


def parse_time(value):
    text = (value or "").strip()
    if not text:
        return None
    text = text.replace("T", " ").replace("Z", "")
    for fmt, length in (
        ("%Y-%m-%d %H:%M:%S", 19),
        ("%Y-%m-%d %H:%M", 16),
        ("%Y.%m.%d %H:%M:%S", 19),
        ("%Y.%m.%d %H:%M", 16),
    ):
        try:
            return datetime.strptime(text[:length], fmt)
        except Exception:
            continue
    try:
        return datetime.fromisoformat(text)
    except Exception:
        return None


def holding_minutes(row):
    explicit = safe_float(row.get("holding_minutes", row.get("hold_minutes", row.get("duration_minutes", 0))), 0.0)
    if explicit > 0:
        return explicit
    open_value = next((row.get(k, "") for k in ("open_time", "entry_time", "opened_at") if row.get(k)), "")
    close_value = next((row.get(k, "") for k in ("close_time", "exit_time", "closed_at") if row.get(k)), "")
    opened = parse_time(open_value)
    closed = parse_time(close_value)
    if opened and closed and closed >= opened:
        return (closed - opened).total_seconds() / 60.0
    return 0.0


def trade_day(row):
    for key in ("close_time", "exit_time", "closed_at", "timestamp", "time", "date"):
        value = (row.get(key) or "").strip()
        if not value:
            continue
        # Accept ISO/date-like strings without forcing a broker-specific format.
        normalized = value.replace("T", " ").split(" ")[0]
        if len(normalized) >= 10:
            return normalized[:10]
    return "UNKNOWN_DAY"


def is_runner(row):
    haystack = " ".join(
        str(row.get(k, ""))
        for k in ("entry_type", "management", "mgmt", "profit_role", "active_execution_leg", "leg")
    ).upper()
    return "RUNNER" in haystack or "SLOT3" in haystack or "LEG C" in haystack


def planned_risk_value(row):
    explicit = safe_float(row.get("planned_risk", row.get("planned_sl_loss", row.get("planned_sl_risk", 0))), 0.0)
    if explicit > 0:
        return explicit
    entry = safe_float(row.get("entry_price", row.get("open_price", row.get("price", 0))), 0.0)
    sl = safe_float(row.get("sl", row.get("stop_loss", 0)), 0.0)
    lots = safe_float(row.get("lots", row.get("volume", row.get("lot", 0))), 0.0)
    tick_value = safe_float(row.get("tick_value", row.get("point_value", 0)), 0.0)
    risk_points = abs(entry - sl) if entry > 0 and sl > 0 else safe_float(row.get("planned_sl_risk_points", 0), 0.0)
    if risk_points > 0 and lots > 0 and tick_value > 0:
        return risk_points * lots * tick_value
    return risk_points


def realized_r(row, profit):
    explicit = safe_float(row.get("realized_r", row.get("r_multiple", 0)), 0.0)
    if explicit != 0:
        return explicit
    planned = planned_risk_value(row)
    if planned > 0:
        return profit / planned
    return 0.0


def blank_stats():
    return {
        "trades": 0,
        "wins": 0,
        "losses": 0,
        "gross_win": 0.0,
        "gross_loss": 0.0,
        "win_r_total": 0.0,
        "loss_r_total": 0.0,
        "planned_loss_total": 0.0,
        "realized_loss_total": 0.0,
        "loss_over_plan_count": 0,
        "max_loss_over_plan_r": 0.0,
        "holding_minutes_total": 0.0,
        "holding_time_trades": 0,
        "runner_trades": 0,
        "runner_wins": 0,
    }


def add_trade(stats, row):
    profit = safe_float(row.get("profit", row.get("pnl", row.get("net_profit", 0))), 0.0)
    result = str(row.get("result", "")).upper()
    win = profit > 0 or result == "WIN"
    loss = profit < 0 or result == "LOSS"

    stats["trades"] += 1
    r_value = realized_r(row, profit)
    if win:
        stats["wins"] += 1
        stats["gross_win"] += max(profit, 0.0)
        if r_value > 0:
            stats["win_r_total"] += r_value
    elif loss:
        planned = planned_risk_value(row)
        realized_loss = abs(min(profit, 0.0))
        stats["losses"] += 1
        stats["gross_loss"] += realized_loss
        if r_value < 0:
            stats["loss_r_total"] += abs(r_value)
        if planned > 0:
            stats["planned_loss_total"] += planned
            stats["realized_loss_total"] += realized_loss
            loss_over_plan_r = realized_loss / planned
            if loss_over_plan_r > 1.05:
                stats["loss_over_plan_count"] += 1
            stats["max_loss_over_plan_r"] = max(stats["max_loss_over_plan_r"], loss_over_plan_r)

    if is_runner(row):
        stats["runner_trades"] += 1
        if win:
            stats["runner_wins"] += 1

    hold_minutes = holding_minutes(row)
    if hold_minutes > 0:
        stats["holding_minutes_total"] += hold_minutes
        stats["holding_time_trades"] += 1


def derived(stats):
    trades = stats["trades"]
    wins = stats["wins"]
    losses = stats["losses"]
    avg_win = stats["gross_win"] / wins if wins else 0.0
    avg_loss = stats["gross_loss"] / losses if losses else 0.0
    win_rate = wins / trades if trades else 0.0
    loss_rate = losses / trades if trades else 0.0
    profit_factor = (stats["gross_win"] / stats["gross_loss"]) if stats["gross_loss"] else (float("inf") if stats["gross_win"] > 0 else 0.0)
    expectancy = (win_rate * avg_win) - (loss_rate * avg_loss)
    avg_holding_minutes = stats["holding_minutes_total"] / stats["holding_time_trades"] if stats["holding_time_trades"] else 0.0
    runner_capture_rate = stats["runner_wins"] / stats["runner_trades"] if stats["runner_trades"] else 0.0
    avg_r_win = stats["win_r_total"] / wins if wins else 0.0
    avg_r_loss = stats["loss_r_total"] / losses if losses else 0.0
    loss_plan_ratio = stats["realized_loss_total"] / stats["planned_loss_total"] if stats["planned_loss_total"] else 0.0
    return win_rate, avg_win, avg_loss, profit_factor, expectancy, avg_holding_minutes, runner_capture_rate, avg_r_win, avg_r_loss, loss_plan_ratio


def print_stats(label, stats):
    win_rate, avg_win, avg_loss, profit_factor, expectancy, avg_holding_minutes, runner_capture_rate, avg_r_win, avg_r_loss, loss_plan_ratio = derived(stats)
    pf = "INF" if profit_factor == float("inf") else f"{profit_factor:.2f}"
    print(label)
    print(f"  Trades              : {stats['trades']}")
    print(f"  Win Rate            : {win_rate * 100:.1f}%")
    print(f"  Average Win         : {avg_win:.2f}")
    print(f"  Average Loss        : {avg_loss:.2f}")
    print(f"  Average R Win       : {avg_r_win:.2f}R")
    print(f"  Average R Loss      : {avg_r_loss:.2f}R")
    print(f"  Profit Factor       : {pf}")
    print(f"  Expectancy          : {expectancy:.2f}")
    print(f"  Average Holding Time: {avg_holding_minutes:.1f} min")
    print(f"  Runner Capture Rate : {runner_capture_rate * 100:.1f}%")
    if stats["planned_loss_total"] > 0:
        print(f"  Realized/Planned Loss: {loss_plan_ratio:.2f}x")
        print(f"  Loss > 1.05R Count  : {stats['loss_over_plan_count']}")
        print(f"  Max Loss vs Plan    : {stats['max_loss_over_plan_r']:.2f}R")


def main():
    memory_file = MEMORY_FILE if MEMORY_FILE.exists() else LOCAL_MEMORY_FILE
    if not memory_file.exists():
        print("trade_memory.csv not found:", MEMORY_FILE, "or", LOCAL_MEMORY_FILE)
        return

    by_entry = defaultdict(blank_stats)
    by_day = defaultdict(blank_stats)
    overall = blank_stats()

    with open(memory_file, "r", encoding="utf-8", errors="ignore", newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            if not row:
                continue
            entry_type = row.get("entry_type", "UNKNOWN") or "UNKNOWN"
            add_trade(overall, row)
            add_trade(by_entry[entry_type], row)
            add_trade(by_day[trade_day(row)], row)

    print("\n=== RP TRADE MEMORY ANALYSIS — EXPECTANCY FIRST ===\n")
    print_stats("OVERALL", overall)

    print("\n=== DAILY METRICS ===\n")
    for day, stats in sorted(by_day.items()):
        print_stats(day, stats)

    print("\n=== ENTRY TYPE METRICS ===\n")
    for entry_type, stats in sorted(by_entry.items()):
        print_stats(f"ENTRY TYPE: {entry_type}", stats)

    print("\n=== DECISION GUIDE ===\n")
    for entry_type, stats in sorted(by_entry.items()):
        trades = stats["trades"]
        win_rate, _avg_win, _avg_loss, profit_factor, expectancy, _avg_holding_minutes, _runner_capture_rate, _avg_r_win, _avg_r_loss, _loss_plan_ratio = derived(stats)
        if trades < 5:
            status = "KEEP TESTING"
        elif expectancy > 0 and profit_factor >= 1.25:
            status = "KEEP / MAY SCALE"
        elif expectancy <= 0 or profit_factor < 1.0:
            status = "WEAK / REDUCE OR DISABLE"
        else:
            status = "NEUTRAL / NEED MORE DATA"
        print(f"{entry_type}: {status} | expectancy={expectancy:.2f} win_rate={win_rate * 100:.1f}%")


if __name__ == "__main__":
    main()
