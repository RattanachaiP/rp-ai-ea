import csv
from collections import defaultdict
from pathlib import Path

MEMORY_FILE = Path(
    r"C:\Users\trader\AppData\Roaming\MetaQuotes\Terminal\Common\Files\RP_AI_EA\trade_memory.csv"
)

def main():
    if not MEMORY_FILE.exists():
        print("trade_memory.csv not found:", MEMORY_FILE)
        return

    stats = defaultdict(lambda: {
        "trades": 0,
        "wins": 0,
        "losses": 0,
        "profit": 0.0,
    })

    with open(MEMORY_FILE, "r", encoding="utf-8", errors="ignore") as f:
        reader = csv.DictReader(f)

        for row in reader:
            entry_type = row.get("entry_type", "UNKNOWN") or "UNKNOWN"
            result = row.get("result", "")
            profit = float(row.get("profit", 0) or 0)

            stats[entry_type]["trades"] += 1
            stats[entry_type]["profit"] += profit

            if result == "WIN":
                stats[entry_type]["wins"] += 1
            else:
                stats[entry_type]["losses"] += 1

    print("\n=== RP TRADE MEMORY ANALYSIS ===\n")

    for entry_type, s in sorted(stats.items()):
        trades = s["trades"]
        wins = s["wins"]
        losses = s["losses"]
        profit = s["profit"]
        winrate = (wins / trades * 100) if trades > 0 else 0

        print(f"ENTRY TYPE: {entry_type}")
        print(f"  Trades : {trades}")
        print(f"  Wins   : {wins}")
        print(f"  Losses : {losses}")
        print(f"  WR     : {winrate:.1f}%")
        print(f"  Profit : {profit:.2f}")
        print("-" * 35)

    print("\n=== DECISION GUIDE ===\n")

    for entry_type, s in sorted(stats.items()):
        trades = s["trades"]
        wins = s["wins"]
        profit = s["profit"]
        winrate = (wins / trades * 100) if trades > 0 else 0

        if trades < 5:
            status = "KEEP TESTING"
        elif winrate >= 55 and profit > 0:
            status = "KEEP / MAY SCALE"
        elif winrate < 40 or profit < 0:
            status = "WEAK / REDUCE OR DISABLE"
        else:
            status = "NEUTRAL / NEED MORE DATA"

        print(f"{entry_type}: {status}")

if __name__ == "__main__":
    main()