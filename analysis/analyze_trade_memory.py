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


def blank_stats():
    return {
        "trades": 0,
        "wins": 0,
        "losses": 0,
        "gross_win": 0.0,
        "gross_loss": 0.0,
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
    if win:
        stats["wins"] += 1
        stats["gross_win"] += max(profit, 0.0)
    elif loss:
        stats["losses"] += 1
        stats["gross_loss"] += abs(min(profit, 0.0))

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
    return win_rate, avg_win, avg_loss, profit_factor, expectancy, avg_holding_minutes, runner_capture_rate


def print_stats(label, stats):
    win_rate, avg_win, avg_loss, profit_factor, expectancy, avg_holding_minutes, runner_capture_rate = derived(stats)
    pf = "INF" if profit_factor == float("inf") else f"{profit_factor:.2f}"
    print(label)
    print(f"  Trades              : {stats['trades']}")
    print(f"  Win Rate            : {win_rate * 100:.1f}%")
    print(f"  Average Win         : {avg_win:.2f}")
    print(f"  Average Loss        : {avg_loss:.2f}")
    print(f"  Profit Factor       : {pf}")
    print(f"  Expectancy          : {expectancy:.2f}")
    print(f"  Average Holding Time: {avg_holding_minutes:.1f} min")
    print(f"  Runner Capture Rate : {runner_capture_rate * 100:.1f}%")


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
        win_rate, _avg_win, _avg_loss, profit_factor, expectancy, _avg_holding_minutes, _runner_capture_rate = derived(stats)
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
