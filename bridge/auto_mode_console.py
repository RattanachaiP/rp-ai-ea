import json
from pathlib import Path
from datetime import datetime

SHARED_FILE = Path(r"D:\RP_AI_EA\shared\decision.json")

SAFE_NO_TRADE = {
    "symbol": "XAUUSD",
    "timeframe": "M15",
    "bias": "NEUTRAL",
    "confidence": 3,
    "score": 1,
    "decision": "NO_TRADE",
    "entry_type": "",
    "entry_zone": "",
    "stop_loss": "",
    "tp1": "",
    "tp2": "",
    "tp3": ""
}

def write_decision(data):
    data["updated_at"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    SHARED_FILE.parent.mkdir(parents=True, exist_ok=True)

    with open(SHARED_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)

    print("\n✅ decision.json updated")
    print(SHARED_FILE)

def validate(data):
    required = ["symbol", "timeframe", "bias", "confidence", "score", "decision"]
    for key in required:
        if key not in data:
            return False, f"Missing key: {key}"

    if data["symbol"] != "XAUUSD":
        return False, "Only XAUUSD allowed in this test phase"

    if data["bias"] not in ["BUY", "SELL", "NEUTRAL"]:
        return False, "bias must be BUY / SELL / NEUTRAL"

    if data["decision"] not in ["TRADE", "NO_TRADE"]:
        return False, "decision must be TRADE / NO_TRADE"

    if data["decision"] == "TRADE":
        if data["score"] < 3:
            return False, "Blocked: score below 3"
        if data["confidence"] < 6:
            return False, "Blocked: confidence below 6"
        if data["bias"] == "NEUTRAL":
            return False, "Blocked: TRADE cannot use NEUTRAL bias"

    return True, "OK"

def paste_json_mode():
    print("\nPaste JSON from RP Trading GPT, then press Enter twice:")
    lines = []
    while True:
        line = input()
        if line.strip() == "":
            break
        lines.append(line)

    raw = "\n".join(lines)

    try:
        data = json.loads(raw)
    except json.JSONDecodeError as e:
        print("❌ Invalid JSON:", e)
        return

    ok, msg = validate(data)
    if not ok:
        print("❌", msg)
        return

    print("\nParsed decision:")
    print(json.dumps(data, indent=2))

    confirm = input("\nWrite this decision.json? type YES: ")
    if confirm == "YES":
        write_decision(data)
    else:
        print("Cancelled.")

def main():
    while True:
        print("\n=== RP AUTO MODE CONSOLE ===")
        print("1 = Paste GPT JSON")
        print("2 = Write SAFE NO_TRADE")
        print("3 = Exit")

        choice = input("Select: ").strip()

        if choice == "1":
            paste_json_mode()
        elif choice == "2":
            write_decision(SAFE_NO_TRADE.copy())
        elif choice == "3":
            break
        else:
            print("Invalid choice")

if __name__ == "__main__":
    main()