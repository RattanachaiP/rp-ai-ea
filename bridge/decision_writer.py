import json
from pathlib import Path
from datetime import datetime

SHARED_FILE = Path(r"D:\RP_AI_EA\shared\decision.json")

def write_decision(decision: dict):
    SHARED_FILE.parent.mkdir(parents=True, exist_ok=True)

    decision["updated_at"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    with open(SHARED_FILE, "w", encoding="utf-8") as f:
        json.dump(decision, f, indent=2)

    print("✅ decision.json updated")
    print(SHARED_FILE)

def main():
    print("RP Decision Writer")
    print("Paste JSON from RP Trading GPT, then press Enter twice:")
    print("-" * 50)

    lines = []
    while True:
        line = input()
        if line.strip() == "":
            break
        lines.append(line)

    raw_json = "\n".join(lines)

    try:
        decision = json.loads(raw_json)
    except json.JSONDecodeError as e:
        print("❌ Invalid JSON:", e)
        return

    required = ["symbol", "bias", "confidence", "score", "decision"]

    for key in required:
        if key not in decision:
            print(f"❌ Missing key: {key}")
            return

    if decision["decision"] not in ["TRADE", "NO_TRADE"]:
        print("❌ decision must be TRADE or NO_TRADE")
        return

    if decision["bias"] not in ["BUY", "SELL", "NEUTRAL"]:
        print("❌ bias must be BUY / SELL / NEUTRAL")
        return

    if decision["decision"] == "TRADE":
        if decision["score"] < 3 or decision["confidence"] < 6:
            print("❌ BLOCKED: score/confidence too low for TRADE")
            return

    write_decision(decision)

if __name__ == "__main__":
    main()