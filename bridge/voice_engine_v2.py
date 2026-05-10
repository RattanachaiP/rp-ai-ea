import os
import json
import time
import pyttsx3

BASE_DIR = r"D:\RP_AI_EA"
SHARED_DIR = os.path.join(BASE_DIR, "shared")
CONFIG_FILE = os.path.join(SHARED_DIR, "voice_config.json")

CHECK_INTERVAL_SEC = 1.0


def load_json(path, default=None):
    try:
        if not os.path.exists(path):
            return default
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        print(f"[ERROR] Cannot read JSON: {path} | {e}")
        return default


def speak(engine, text):
    try:
        print(f"[VOICE] {text}")
        engine.say(text)
        engine.runAndWait()
    except Exception as e:
        print(f"[ERROR] Speak failed: {e}")


def get_decision_file(symbol):
    return os.path.join(SHARED_DIR, symbol, "decision.json")


def get_action(data):
    decision = str(data.get("decision", data.get("action", "NO_TRADE"))).upper()
    bias = str(data.get("bias", "")).upper()

    if decision == "TRADE" and bias in ["BUY", "SELL"]:
        return bias

    return decision


def make_message(symbol, data, config):
    action = get_action(data)
    reason = data.get("reason", "")
    entry_type = data.get("entry_type", "")
    sl = data.get("stop_loss", "")
    tp1 = data.get("tp1", "")

    speak_sl_tp = bool(config.get("speak_sl_tp", True))
    speak_reason = bool(config.get("speak_reason", True))

    message = f"{symbol} {action}"

    if entry_type:
        message += f". Setup {entry_type}"

    if speak_sl_tp:
        if sl != "":
            message += f". Stop loss {sl}"
        if tp1 != "":
            message += f". TP one {tp1}"

    if speak_reason and reason:
        message += f". {reason}"

    return message


def main():
    print("====================================")
    print(" RP Voice Engine V2 Smart Filter started")
    print("====================================")

    engine = pyttsx3.init()
    engine.setProperty("rate", 165)
    engine.setProperty("volume", 1.0)

    last_signature = {}
    last_voice_time = {}

    while True:
        config = load_json(CONFIG_FILE, default={})

        voice_enabled = bool(config.get("voice_enabled", True))
        speak_buy_sell_only = bool(config.get("speak_buy_sell_only", True))
        speak_no_trade = bool(config.get("speak_no_trade", False))
        min_gap = int(config.get("min_seconds_between_voice", 20))
        symbols = config.get("symbols", ["BTCUSD", "XAUUSD"])

        if not voice_enabled:
            time.sleep(CHECK_INTERVAL_SEC)
            continue

        now = time.time()

        for symbol in symbols:
            decision_file = get_decision_file(symbol)
            data = load_json(decision_file, default=None)

            if not data:
                continue

            action = get_action(data)
            updated_at = str(data.get("updated_at", data.get("timestamp", "")))
            entry_type = str(data.get("entry_type", ""))
            reason = str(data.get("reason", ""))
            sl = str(data.get("stop_loss", ""))
            tp1 = str(data.get("tp1", ""))

            signature = f"{symbol}|{action}|{updated_at}|{entry_type}|{sl}|{tp1}|{reason}"

            if last_signature.get(symbol) == signature:
                continue

            if speak_buy_sell_only and action not in ["BUY", "SELL"]:
                last_signature[symbol] = signature
                continue

            if action == "NO_TRADE" and not speak_no_trade:
                last_signature[symbol] = signature
                continue

            last_time = last_voice_time.get(symbol, 0)

            if now - last_time < min_gap:
                print(f"[SKIP] {symbol} voice cooldown active")
                last_signature[symbol] = signature
                continue

            last_signature[symbol] = signature
            last_voice_time[symbol] = now

            message = make_message(symbol, data, config)
            speak(engine, message)

        time.sleep(CHECK_INTERVAL_SEC)


if __name__ == "__main__":
    main()