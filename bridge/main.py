import json
import time
from datetime import datetime

MARKET_FILE = r"C:\Users\rpfunds\AppData\Roaming\MetaQuotes\Terminal\Common\Files\RP_AI_EA\shared\market_state.json"
DECISION_FILE = r"C:\Users\rpfunds\AppData\Roaming\MetaQuotes\Terminal\Common\Files\RP_AI_EA\shared\decision.json"

def read_json(path):
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        print("read_json error:", e)
        return None

def write_json(path, data):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)

def calculate_decision(state):
    bid = state.get("bid", 0)
    spread = state.get("spread_points", 9999)

    ma50 = state.get("ma50", 0)
    ma90 = state.get("ma90", 0)
    ma200 = state.get("ma200", 0)
    rsi = state.get("rsi", 0)

    macd_main = state.get("macd_main", 0)
    macd_signal = state.get("macd_signal", 0)
    macd_ok = state.get("macd_ok", False)

    h1_bias = state.get("h1_bias", "unknown")
    h4_bias = state.get("h4_bias", "unknown")

    position_type = state.get("position_type", "NONE")
    has_position = state.get("has_position", False)

    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    if spread > 500:
        action = "NO_TRADE"
        confidence = 0
        reason = f"spread too high ({spread})"
    elif not macd_ok:
        action = "NO_TRADE"
        confidence = 0
        reason = "macd not ready"
    else:
        bullish_checks = {
            "bid > ma50": bid > ma50,
            "bid > ma90": bid > ma90,
            "bid > ma200": bid > ma200,
            "rsi > 55": rsi > 55,
            "macd_main > macd_signal": macd_main > macd_signal,
        }

        bearish_checks = {
            "bid < ma50": bid < ma50,
            "bid < ma90": bid < ma90,
            "bid < ma200": bid < ma200,
            "rsi < 45": rsi < 45,
            "macd_main < macd_signal": macd_main < macd_signal,
        }

        bullish_passed = [name for name, ok in bullish_checks.items() if ok]
        bullish_failed = [name for name, ok in bullish_checks.items() if not ok]

        bearish_passed = [name for name, ok in bearish_checks.items() if ok]
        bearish_failed = [name for name, ok in bearish_checks.items() if not ok]

        bullish_score = len(bullish_passed)
        bearish_score = len(bearish_passed)

        bullish_bias_bonus = 0
        bearish_bias_bonus = 0

        if h1_bias == "bullish":
            bullish_bias_bonus += 1
        elif h1_bias == "bearish":
            bearish_bias_bonus += 1

        if h4_bias == "bullish":
            bullish_bias_bonus += 1
        elif h4_bias == "bearish":
            bearish_bias_bonus += 1

        adj_bullish = bullish_score + bullish_bias_bonus
        adj_bearish = bearish_score + bearish_bias_bonus

        action = "NO_TRADE"
        confidence = 0
        reason = "no confluence"

        if bullish_score == 5 and h1_bias == "bullish" and h4_bias == "bullish":
            action = "BUY"
            confidence = 95
            reason = "strong bullish MTF confluence"
        elif bullish_score >= 4 and adj_bullish >= 5 and adj_bearish <= 2:
            action = "BUY"
            confidence = 80
            reason = "flex bullish MTF entry"
        elif (
            bullish_score == 3 and
            bid > ma90 and
            macd_main >= macd_signal and
            rsi >= 50 and
            h1_bias != "bearish" and
            h4_bias != "bearish"
        ):
            action = "BUY"
            confidence = 65
            reason = "smart bullish MTF entry 3/5"
        elif bearish_score == 5 and h1_bias == "bearish" and h4_bias == "bearish":
            action = "SELL"
            confidence = 95
            reason = "strong bearish MTF confluence"
        elif bearish_score >= 4 and adj_bearish >= 5 and adj_bullish <= 2:
            action = "SELL"
            confidence = 80
            reason = "flex bearish MTF entry"
        elif (
            bearish_score == 3 and
            bid < ma90 and
            macd_main <= macd_signal and
            rsi <= 50 and
            h1_bias != "bullish" and
            h4_bias != "bullish"
        ):
            action = "SELL"
            confidence = 65
            reason = "smart bearish MTF entry 3/5"
        else:
            if adj_bullish >= adj_bearish:
                confidence = min(adj_bullish * 10, 60)
                reason = "NO_TRADE bullish incomplete | passed: "
                reason += ", ".join(bullish_passed) if bullish_passed else "none"
                reason += " | failed: "
                reason += ", ".join(bullish_failed) if bullish_failed else "none"
                reason += f" | h1={h1_bias}, h4={h4_bias}"
            else:
                confidence = min(adj_bearish * 10, 60)
                reason = "NO_TRADE bearish incomplete | passed: "
                reason += ", ".join(bearish_passed) if bearish_passed else "none"
                reason += " | failed: "
                reason += ", ".join(bearish_failed) if bearish_failed else "none"
                reason += f" | h1={h1_bias}, h4={h4_bias}"

    exit_now = False
    exit_reason = ""

    if has_position:
        if position_type == "BUY":
            if action == "SELL":
                exit_now = True
                exit_reason = "reverse signal: SELL while holding BUY"
            elif action == "NO_TRADE" and confidence <= 30:
                exit_now = True
                exit_reason = "bullish confidence lost while holding BUY"
        elif position_type == "SELL":
            if action == "BUY":
                exit_now = True
                exit_reason = "reverse signal: BUY while holding SELL"
            elif action == "NO_TRADE" and confidence <= 30:
                exit_now = True
                exit_reason = "bearish confidence lost while holding SELL"

    return {
        "action": action,
        "confidence": confidence,
        "reason": reason,
        "exit_now": exit_now,
        "exit_reason": exit_reason,
        "timestamp": now
    }

last_time = None

while True:
    state = read_json(MARKET_FILE)

    if state:
        bar_time = state.get("bar_time")

        if bar_time != last_time:
            result = calculate_decision(state)
            write_json(DECISION_FILE, result)
            print("AI decision:", result)
            last_time = bar_time

    time.sleep(2)