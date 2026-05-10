import json
import os
import time
from datetime import datetime
from pathlib import Path

# ============================================================
# RP AI Decision Engine XAUUSD V20 TREND PRIORITY MODE + DUAL MODE + ATOMIC WRITE
# - Adds BB state: NORMAL / REVERSAL_UP / REVERSAL_DOWN / WALK_UP / WALK_DOWN / COMPRESSION
# - Adds management: SCALP_TP / HOLD_TRAIL / NO_TRADE
# - Allows TP=0 for runner/trailing trades
# - Adds BB dev4 extreme filter to block chasing at over-extension zones
# - Adds Nova Brain final approval gate before writing TRADE decision
# - V17: Allows qualified trend pullback entries even when momentum temporarily cools at MA/BB middle
# - Adds Manual Trend Report Layer: trend_bias / confidence / manual_action / danger_zone
# - V18: Adds stricter Entry Quality Gate before Daily Loss Guard
# - V19.1: Allows strong TRANSITION + BB NORMAL trades only when score/momentum/RSI/BB-mid filters pass
# - V19: Adds Adaptive Entry Score + learning from real trade results
# - V19.5: Allows selective RANGE BB reversal entries with confirmed bounce momentum
# - V19.8: Dual Mode Auto Switch (SAFE / AGGRESSIVE) for selective faster entries
# - V20: Trend Priority Mode lets clear trends override transition/BB-middle hesitation
# - V21: Soft Direction Lock V2 with TREND_LOCK / TRANSITION_WAIT / REVERSAL_ALLOW
# - V21.1: EA V17/V18 decision schema compatibility fields for entry_allowed / scores
# - V21.2: SPIKE Continuation Mode (breakout after spike, without blocking all SPIKE trades)
# - V22: TREND WALK Override (BB WALK continuation can bypass adaptive score gap when momentum is strong)
# - V22: TREND NORMAL Continuation Override (trend continuation can pass when momentum is strong even if score_gap is only 1)
# - V22: Strong Trend Continuation Cooldown Override (do not miss BB WALK continuation due to cooldown/max signal)
# - V22: Candle Intelligence Layer V1 (candle trend, structure, momentum shape, wick rejection, exhaustion risk)
# - V23_3: TREND NORMAL Momentum Override (TREND_LOCK + strong MACD can pass even with score_gap=1)
# - V23_3: Transition Decay Logic V1 (Soft Lock waits for persistent weakening before TRANSITION_WAIT)
# - V23_3: Trend Exhaustion Detection (avoid late continuation when RSI/MACD/BB/wick show exhaustion)
# - V23_3: Market Structure + Exhaustion Master Gate (HH/HL, LH/LL, BOS/CHOCH, liquidity sweep, distribution/accumulation, late-entry block)
# - V23_3.1: Soft Lock Counter Reset (reset stale persistent weakening counter when context/momentum/bar changes)
# - V23.3: Fresh Market State + Soft Lock Stale Reset (decision.json must follow latest market_state)
# - V23.3: Fresh Market State Read Fix (force fresh file read every loop + MARKET_STATE_READ log)
# ============================================================

SYMBOL = "XAUUSD"
TIMEFRAME = "M15"

BASE_PATH = Path(r"D:\RP_AI_EA\shared") / SYMBOL
FILE_PATH = BASE_PATH / "market_state.json"
OUTPUT_PATH = BASE_PATH / "decision.json"

# V23.3 Fresh Market State Read Fix
MARKET_STATE_DEBUG_READ_LOG = True
MARKET_STATE_MAX_AGE_SECONDS = 10
last_market_state_signature_read = ""

COOLDOWN_SECONDS = 30
MAX_SIGNALS_PER_BAR = 2

SL_POINTS_TREND = 6.0
TP_POINTS_TREND = 12.0
SL_POINTS_RANGE = 3.0
TP_POINTS_RANGE = 4.5
SL_POINTS_SPIKE = 9.0
TP_POINTS_SPIKE = 8.0
SL_POINTS_TRANSITION = 5.0
TP_POINTS_TRANSITION = 7.0

TREND_BUY_RSI = 55.0
TREND_SELL_RSI = 45.0
RANGE_RSI_LOW = 45.0
RANGE_RSI_HIGH = 55.0
RANGE_MACD_ABS_MAX = 0.8
RANGE_MIN_SCORE_EDGE = 1
SPIKE_BUY_RSI = 65.0
SPIKE_SELL_RSI = 35.0
SPIKE_MACD_ABS_MIN = 3.0

ENABLE_SLOT3_RUNNER = True
BUY_SLOT3_MIN_SCORE = 3
SELL_SLOT3_MIN_SCORE = 3
BUY_SLOT3_MIN_RSI = 58.0
SELL_SLOT3_MAX_RSI = 42.0
BUY_SLOT3_MIN_MACD_HIST = 1.5
SELL_SLOT3_MAX_MACD_HIST = -1.5

# BB adaptive thresholds
BB_COMPRESSION_WIDTH_MAX = 3.0      # XAU price units, adjust after logs
BB_NEAR_EDGE_PCT = 0.12             # within 12% band width from edge
BB_WALK_RSI_BUY = 55.0
BB_WALK_RSI_SELL = 45.0
BB_WALK_MACD_MIN = 0.0
BB_DEV4_EDGE_PCT = 0.08

# V17 Trend Pullback Allow
ENABLE_TREND_PULLBACK_ALLOW = True
TREND_PULLBACK_MIN_EDGE = 3
TREND_PULLBACK_BUY_MAX_RSI = 62.0
TREND_PULLBACK_BUY_MIN_RSI = 48.0
TREND_PULLBACK_SELL_MIN_RSI = 38.0
TREND_PULLBACK_SELL_MAX_RSI = 55.0
TREND_PULLBACK_MACD_TOLERANCE = 0.80
TREND_PULLBACK_MA_TOLERANCE = 3.0  # XAU price units around MA50/MA90

# V18 Entry Quality Gate
ENTRY_TRANSITION_NORMAL_MIN_GAP = 3
ENTRY_MIDDLE_ZONE_PCT = 0.15
ENTRY_MOMENTUM_MACD_TOLERANCE = 0.15
ENTRY_SCALP_REQUIRE_ALIGNMENT = True
ENTRY_SPIKE_EXHAUSTION_RSI_LOW = 35.0
ENTRY_SPIKE_EXHAUSTION_RSI_HIGH = 65.0

# V19.7 Relax Transition Carefully
# Allow selective TRANSITION+NORMAL trades when score, RSI, and MACD confirm.
TRANSITION_NORMAL_ALLOW_GAP = 2
TRANSITION_RSI_BUY_MIN = 52.0
TRANSITION_RSI_SELL_MAX = 48.0
# MACD may cool slightly during transition; only block strongly opposite momentum.
TRANSITION_MACD_BUY_MIN = -0.50
TRANSITION_MACD_SELL_MAX = 0.50

# V19.4 Mild MACD Allow for strong TREND + BB NORMAL BUY setups
TREND_NORMAL_BUY_MIN_GAP = 3
TREND_NORMAL_BUY_MIN_RSI = 58.0
TREND_NORMAL_BUY_MILD_MACD_MIN = -0.50

# V19.6 Selective Strong Setup Unlock
RANGE_REVERSAL_MIN_GAP = 1
RANGE_REVERSAL_ALLOW_EQUAL_WITH_MOMENTUM = True
RANGE_REVERSAL_RSI_BUY_MAX = 45.0   # REVERSAL_DOWN bounce BUY should be below neutral
RANGE_REVERSAL_RSI_SELL_MIN = 55.0  # REVERSAL_UP bounce SELL should be above neutral
RANGE_REVERSAL_MACD_BUY_MIN = 0.0
RANGE_REVERSAL_MACD_SELL_MAX = 0.0

# V19.6 Selective Strong Setup Unlock
# Allow very strong direction setups to pass even near BB middle, but only when momentum confirms.
STRONG_NORMAL_UNLOCK_GAP = 4
STRONG_NORMAL_BUY_RSI_MIN = 56.0
STRONG_NORMAL_SELL_RSI_MAX = 44.0
STRONG_NORMAL_BUY_MACD_MIN = 0.0
STRONG_NORMAL_SELL_MACD_MAX = 0.0

# V19 Adaptive Entry Score + Learning
LEARNING_ENABLED = True
LEARNING_RESULTS_JSONL = BASE_PATH / "trade_results.jsonl"
LEARNING_RESULTS_JSON = BASE_PATH / "trade_results.json"
LEARNING_STATE_PATH = BASE_PATH / "learning_stats.json"
LEARNING_MIN_TRADES = 6
LEARNING_BAD_WINRATE = 0.45
LEARNING_GOOD_WINRATE = 0.65
LEARNING_MAX_GAP_ADJUST = 2
ADAPTIVE_GAP_MIN = 2
ADAPTIVE_GAP_MAX = 5

# V19.8 Dual Mode Auto Switch
DUAL_MODE_ENABLED = True
DUAL_AGGRESSIVE_MIN_GAP = 2
DUAL_AGGRESSIVE_BUY_RSI_MIN = 51.5
DUAL_AGGRESSIVE_SELL_RSI_MAX = 48.5
DUAL_AGGRESSIVE_BUY_MACD_MIN = -0.60
DUAL_AGGRESSIVE_SELL_MACD_MAX = 0.60
DUAL_SAFE_SPIKE_RSI_LOW = 35.0
DUAL_SAFE_SPIKE_RSI_HIGH = 65.0

# V20 Trend Priority Mode
# Goal: when the chart is trending clearly, let trend continuation take priority
# over BB middle / transition hesitation. DEV4 and compression remain hard safety blocks.
TREND_PRIORITY_ENABLED = True
TREND_PRIORITY_MIN_GAP = 2
TREND_PRIORITY_STRONG_GAP = 3
TREND_PRIORITY_BUY_RSI_MIN = 52.0
TREND_PRIORITY_SELL_RSI_MAX = 48.0
TREND_PRIORITY_BUY_MACD_MIN = -0.60
TREND_PRIORITY_SELL_MACD_MAX = 0.60
TREND_PRIORITY_MAX_GAP_REQUIRED = 2

# V21 Soft Direction Lock V2
# Replaces hard direction blocking with a state machine:
# - TREND_LOCK: continue with the locked trend direction only
# - TRANSITION_WAIT: trend is weakening; stop adding new trades
# - REVERSAL_ALLOW: confirmed reversal may trade opposite direction
SOFT_DIRECTION_LOCK_ENABLED = True
SOFT_LOCK_BUY_RSI_WEAK = 52.0
SOFT_LOCK_SELL_RSI_WEAK = 48.0
SOFT_LOCK_MACD_WEAK_BUFFER = 0.05
SOFT_REVERSAL_BUY_RSI_MIN = 50.0
SOFT_REVERSAL_SELL_RSI_MAX = 50.0
SOFT_REVERSAL_MACD_MIN = 0.00
SOFT_REVERSAL_MACD_MAX = 0.00
SOFT_REVERSAL_MIN_SCORE_EDGE = 0

# V21.2 SPIKE Continuation Mode
# Goal: do not fully block SPIKE mode. Allow only strong breakout continuation,
# while still blocking fake wick spikes and BB overextension.
SPIKE_CONTINUATION_ENABLED = True
SPIKE_CONT_BUY_MIN_SCORE = 4
SPIKE_CONT_SELL_MIN_SCORE = 4
SPIKE_CONT_BUY_RSI_MIN = 70.0
SPIKE_CONT_SELL_RSI_MAX = 30.0
SPIKE_CONT_BUY_MACD_MIN = 2.0
SPIKE_CONT_SELL_MACD_MAX = -2.0
SPIKE_NO_FOLLOW_MACD_ABS_MAX = 0.50
SPIKE_BB2_WIDTH_MAX = 18.0
SPIKE_BB4_WIDTH_MAX = 36.0

# V23_3 TREND WALK Override
# Goal: BB WALK continuation should not be blocked by score_gap alone.
TREND_WALK_OVERRIDE_ENABLED = True
TREND_WALK_SELL_MIN_EDGE = 1
TREND_WALK_BUY_MIN_EDGE = 1
TREND_WALK_SELL_RSI_MAX = 45.0
TREND_WALK_BUY_RSI_MIN = 55.0
TREND_WALK_SELL_MACD_MAX = -1.5
TREND_WALK_BUY_MACD_MIN = 1.5

# V23_3 TREND NORMAL Continuation Override
# Goal: TREND + BB NORMAL continuation should not be blocked by adaptive score gap alone
# when RSI/MACD and Soft Direction Lock confirm the trend direction.
TREND_NORMAL_CONTINUATION_ENABLED = True
TREND_NORMAL_SELL_MIN_EDGE = 1
TREND_NORMAL_BUY_MIN_EDGE = 1
TREND_NORMAL_SELL_RSI_MAX = 42.0
TREND_NORMAL_BUY_RSI_MIN = 58.0
TREND_NORMAL_SELL_MACD_MAX = -1.0
TREND_NORMAL_BUY_MACD_MIN = 1.0

# V23_3 Strong Trend Continuation Cooldown Override
# Allows one strong BB WALK continuation signal per new bar even if normal cooldown/max gate blocks.
STRONG_CONTINUATION_COOLDOWN_OVERRIDE_ENABLED = True
STRONG_CONTINUATION_MIN_GAP = 5
STRONG_CONTINUATION_BUY_MIN_RSI = 55.0
STRONG_CONTINUATION_SELL_MAX_RSI = 45.0
STRONG_CONTINUATION_BUY_MIN_MACD = 0.0
STRONG_CONTINUATION_SELL_MAX_MACD = 0.0
strong_continuation_bar_used = {}

# V23_3 Candle Intelligence Layer V1
CANDLE_INTELLIGENCE_ENABLED = True
CANDLE_LOOKBACK_DEFAULT = 8
CANDLE_MIN_TREND_QUALITY = 45
CANDLE_LATE_CONTINUATION_BLOCK_QUALITY = 40
CANDLE_EXHAUSTION_BLOCK_LEVEL = 70
CANDLE_WICK_REJECTION_RATIO = 0.55
CANDLE_SMALL_BODY_RATIO = 0.35
CANDLE_BODY_MOMENTUM_RATIO = 0.55

# V23_3 TREND NORMAL Momentum Override
TREND_NORMAL_MOMENTUM_OVERRIDE_ENABLED = True
TREND_NORMAL_MOMENTUM_MIN_EDGE = 1
TREND_NORMAL_MOMENTUM_SELL_RSI_MAX = 43.0
TREND_NORMAL_MOMENTUM_BUY_RSI_MIN = 57.0
TREND_NORMAL_MOMENTUM_SELL_MACD_MAX = -1.50
TREND_NORMAL_MOMENTUM_BUY_MACD_MIN = 1.50
TREND_NORMAL_MOMENTUM_ALLOW_MIDDLE_IF_MACD_STRONG = True

# V23_3 Transition Decay Logic V1
# Soft Lock should not flip to TRANSITION_WAIT on one weak tick/candle.
TRANSITION_DECAY_ENABLED = True
TRANSITION_DECAY_REQUIRED_COUNT = 3
TRANSITION_DECAY_RESET_ON_STRONG_SCORE = True
TRANSITION_DECAY_STRONG_SCORE_GAP = 4
TRANSITION_DECAY_BUY_RSI_RECOVER = 53.0
TRANSITION_DECAY_SELL_RSI_RECOVER = 47.0
TRANSITION_DECAY_BUY_MACD_RECOVER = 0.25
TRANSITION_DECAY_SELL_MACD_RECOVER = -0.25
transition_decay_state = {}

# V23_3.1 Soft Lock Counter Reset
SOFT_LOCK_COUNTER_RESET_ENABLED = True
SOFT_LOCK_COUNTER_MAX_KEEP = 12
SOFT_LOCK_COUNTER_EXPIRE_SECONDS = 300
SOFT_LOCK_RESET_ON_NEW_BAR = True
transition_decay_meta = {}

# V23.3 Fresh Market State + Soft Lock Stale Reset
FRESH_STATE_RESET_ENABLED = True
FRESH_STATE_TS_CHANGE_SECONDS = 60
FRESH_STATE_MACD_FLIP_EPS = 0.05
fresh_state_snapshot = {}

# V23_3 Trend Exhaustion Detection
TREND_EXHAUSTION_ENABLED = True
TREND_EXHAUSTION_BLOCK_LEVEL = 70
TREND_EXHAUSTION_WARN_LEVEL = 50
TREND_EXHAUSTION_RSI_BUY_HIGH = 70.0
TREND_EXHAUSTION_RSI_SELL_LOW = 30.0
TREND_EXHAUSTION_MACD_FADE_ABS = 0.35
TREND_EXHAUSTION_DEV4_WEIGHT = 35
TREND_EXHAUSTION_WICK_WEIGHT = 30
TREND_EXHAUSTION_RSI_WEIGHT = 20
TREND_EXHAUSTION_MACD_FADE_WEIGHT = 20
TREND_EXHAUSTION_CANDLE_FADE_WEIGHT = 20
TREND_EXHAUSTION_TRANSITION_WEIGHT = 15

# V23_3 Market Structure + Exhaustion Master Gate
MS_EXHAUSTION_MASTER_GATE_ENABLED = True
MS_LOOKBACK_DEFAULT = 10
MS_MASTER_BLOCK_SCORE = 70
MS_MASTER_WARN_SCORE = 50
MS_STRUCTURE_CONFLICT_WEIGHT = 30
MS_CHOCH_WEIGHT = 25
MS_LIQUIDITY_SWEEP_WEIGHT = 25
MS_DISTRIBUTION_WEIGHT = 30
MS_ACCUMULATION_WEIGHT = 30
MS_LATE_EXPANSION_WEIGHT = 25
MS_MOMENTUM_DECAY_WEIGHT = 25
MS_WICK_REJECTION_WEIGHT = 20
MS_EXHAUSTION_WEIGHT = 25
MS_PRICE_EXTENSION_BB_WIDTH_RATIO = 0.75

last_signal_key = ""
last_signal_time = 0
bar_signal_count = {}


def now():
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def safe_float(value, default=0.0):
    try:
        return float(value)
    except Exception:
        return default


def safe_int(value, default=0):
    try:
        return int(value)
    except Exception:
        return default


def can_fire(key, bar_time):
    global last_signal_key, last_signal_time, bar_signal_count
    t = time.time()
    if bar_time not in bar_signal_count:
        bar_signal_count.clear()
        bar_signal_count[bar_time] = 0
    if bar_signal_count[bar_time] >= MAX_SIGNALS_PER_BAR:
        return False
    if key != last_signal_key or (t - last_signal_time) > COOLDOWN_SECONDS:
        last_signal_key = key
        last_signal_time = t
        bar_signal_count[bar_time] += 1
        return True
    return False



def is_strong_trend_continuation_signal(key, bar_time, decision, market_mode, bb_state, buy_score, sell_score, rsi, macd_hist):
    """
    V23_3 helper.
    Strong continuation = BB WALK trend continuation that should not be lost due to cooldown/max signal.
    This does not override weak signals; it only applies to strong score gap + momentum + trend walk.
    """
    if not STRONG_CONTINUATION_COOLDOWN_OVERRIDE_ENABLED:
        return False, "override disabled"

    if not isinstance(decision, dict) or str(decision.get("decision", "")).upper() != "TRADE":
        return False, "not TRADE decision"

    bias = str(decision.get("bias", "NEUTRAL")).upper()
    management = str(decision.get("management", "")).upper()
    soft_state = str(decision.get("soft_lock_state", "")).upper()
    score_gap = abs(safe_int(buy_score, 0) - safe_int(sell_score, 0))

    if market_mode != "TREND":
        return False, "not TREND mode"
    if score_gap < STRONG_CONTINUATION_MIN_GAP:
        return False, f"score_gap {score_gap} < {STRONG_CONTINUATION_MIN_GAP}"
    if not (management == "HOLD_TRAIL" or soft_state == "TREND_LOCK"):
        return False, f"management/soft not continuation mgmt={management} soft={soft_state}"

    if bias == "BUY":
        ok = (
            bb_state == "WALK_UP"
            and buy_score > sell_score
            and rsi >= STRONG_CONTINUATION_BUY_MIN_RSI
            and macd_hist >= STRONG_CONTINUATION_BUY_MIN_MACD
        )
        if ok:
            return True, f"STRONG CONTINUATION BUY cooldown override | gap={score_gap} RSI={rsi:.2f} MACDHist={macd_hist:.2f}"

    if bias == "SELL":
        ok = (
            bb_state == "WALK_DOWN"
            and sell_score > buy_score
            and rsi <= STRONG_CONTINUATION_SELL_MAX_RSI
            and macd_hist <= STRONG_CONTINUATION_SELL_MAX_MACD
        )
        if ok:
            return True, f"STRONG CONTINUATION SELL cooldown override | gap={score_gap} RSI={rsi:.2f} MACDHist={macd_hist:.2f}"

    return False, "not strong BB WALK continuation"


def can_fire_or_strong_override(key, bar_time, decision, data):
    """
    V23_3 cooldown/max-signal gate.
    Normal can_fire() remains unchanged. If it blocks, a strong continuation may pass once per new bar.
    """
    if can_fire(key, bar_time):
        return True, "NORMAL_FIRE"

    if not isinstance(decision, dict):
        return False, "no decision"

    market_mode = str(decision.get("market_mode", "")).upper()
    bb_state = str(decision.get("bb_state", "")).upper()
    buy_score = safe_int(decision.get("buy_score", decision.get("buyScore", 0)), 0)
    sell_score = safe_int(decision.get("sell_score", decision.get("sellScore", 0)), 0)
    rsi = safe_float(decision.get("rsi", data.get("rsi", 50)), 50)
    macd_hist = safe_float(decision.get("macd_hist", data.get("macd_hist", 0)), 0)

    ok, reason = is_strong_trend_continuation_signal(
        key, bar_time, decision, market_mode, bb_state, buy_score, sell_score, rsi, macd_hist
    )
    if not ok:
        return False, reason

    override_key = f"{bar_time}|{decision.get('bias','')}|{bb_state}|STRONG_CONTINUATION"
    if strong_continuation_bar_used.get(override_key, False):
        return False, f"STRONG CONTINUATION OVERRIDE already used this bar | {override_key}"

    strong_continuation_bar_used.clear()
    strong_continuation_bar_used[override_key] = True
    decision["cooldown_override"] = True
    decision["cooldown_override_reason"] = reason
    decision["reason"] = f"{decision.get('reason', '')} | {reason}"
    return True, reason

def read_market():
    """
    V23.3 Fresh Market State Read Fix.

    Force fresh disk read every loop from:
      D:\\RP_AI_EA\\shared\\XAUUSD\\market_state.json

    No cached market_state is used.
    """
    global last_market_state_signature_read

    for attempt in range(10):
        try:
            path = Path(str(FILE_PATH))

            if not path.exists():
                print(f"MARKET_STATE_READ_FAIL | path={path} | missing attempt={attempt+1}")
                time.sleep(0.2)
                continue

            stat = path.stat()
            modified_ts = stat.st_mtime
            modified_time = datetime.fromtimestamp(modified_ts).strftime("%Y-%m-%d %H:%M:%S")
            age_sec = max(0.0, time.time() - modified_ts)

            # Fresh open/read on every loop. No cached text/data.
            with open(path, "r", encoding="utf-8") as f:
                raw_text = f.read().strip()

            if not raw_text:
                print(f"MARKET_STATE_READ_FAIL | path={path} | empty file attempt={attempt+1}")
                time.sleep(0.2)
                continue

            data = json.loads(raw_text)

            bid = safe_float(data.get("bid", 0), 0)
            rsi = safe_float(data.get("rsi", 0), 0)
            macd_hist = safe_float(data.get("macd_hist", data.get("macdHist", 0)), 0)
            buy_score = safe_int(data.get("buyScore", data.get("buy_score", data.get("buy", 0))), 0)
            sell_score = safe_int(data.get("sellScore", data.get("sell_score", data.get("sell", 0))), 0)
            server_time = str(data.get("server_time", data.get("updated_at", "")))
            bar_time = str(data.get("bar_time", ""))

            signature = f"{modified_ts}|{bid}|{buy_score}:{sell_score}|{rsi}|{macd_hist}|{server_time}|{bar_time}"
            last_market_state_signature_read = signature

            if MARKET_STATE_DEBUG_READ_LOG:
                print(
                    "MARKET_STATE_READ |",
                    f"path={path}",
                    f"modified_time={modified_time}",
                    f"age={age_sec:.2f}s",
                    f"bid={bid:.3f}",
                    f"buyScore={buy_score}",
                    f"sellScore={sell_score}",
                    f"rsi={rsi:.2f}",
                    f"macd_hist={macd_hist:.2f}",
                    f"server_time={server_time}",
                    f"bar_time={bar_time}",
                )

            if age_sec > MARKET_STATE_MAX_AGE_SECONDS:
                print(
                    "MARKET_STATE_STALE_WARNING |",
                    f"path={path}",
                    f"age={age_sec:.2f}s",
                    f"modified_time={modified_time}",
                )

            # Attach metadata to decision later for audit.
            data["_market_state_path"] = str(path)
            data["_market_state_modified_time"] = modified_time
            data["_market_state_age_sec"] = round(age_sec, 3)
            data["_market_state_read_signature"] = signature

            return data

        except json.JSONDecodeError as e:
            print("READ MARKET JSON ERROR:", e)
            time.sleep(0.2)
        except PermissionError as e:
            print("READ MARKET LOCKED, RETRY:", e)
            time.sleep(0.2)
        except Exception as e:
            print("READ MARKET ERROR:", e)
            time.sleep(0.3)

    return None


def ensure_ea_v17_compat_fields(data):
    """
    Ensure decision.json always contains fields required by EA V17/V18 quality gate.
    This is schema compatibility only; it does not change trading logic.
    """
    if not isinstance(data, dict):
        return data

    is_trade = str(data.get("decision", "")).upper() == "TRADE"

    # EA must never see this as missing. TRADE defaults true; NO_TRADE defaults false.
    if "entry_allowed" not in data:
        data["entry_allowed"] = bool(is_trade)

    # Support both old camelCase and new snake_case field names.
    if "buy_score" not in data and "buyScore" in data:
        data["buy_score"] = safe_int(data.get("buyScore"), 0)
    if "sell_score" not in data and "sellScore" in data:
        data["sell_score"] = safe_int(data.get("sellScore"), 0)
    if "buyScore" not in data and "buy_score" in data:
        data["buyScore"] = safe_int(data.get("buy_score"), 0)
    if "sellScore" not in data and "sell_score" in data:
        data["sellScore"] = safe_int(data.get("sell_score"), 0)

    data.setdefault("buy_score", 0)
    data.setdefault("sell_score", 0)
    data.setdefault("buyScore", safe_int(data.get("buy_score"), 0))
    data.setdefault("sellScore", safe_int(data.get("sell_score"), 0))

    if "score_gap" not in data:
        data["score_gap"] = abs(safe_int(data.get("buy_score"), 0) - safe_int(data.get("sell_score"), 0))

    data.setdefault("adaptive_gap", 0)
    data.setdefault("analysis_quality", 0)
    data.setdefault("dir_m15", 0)
    data.setdefault("dir_m3", 0)
    data.setdefault("rsi", 0)
    data.setdefault("macd_hist", 0)
    data.setdefault("bb_mid", 0)
    data.setdefault("bb_upper2", 0)
    data.setdefault("bb_lower2", 0)

    # V21 debug fields: keep defaults stable for EA/UI readers.
    data.setdefault("soft_lock_state", "UNLOCKED")
    data.setdefault("soft_lock_direction", "NONE")
    data.setdefault("soft_lock_allowed", bool(data.get("entry_allowed", False)))
    data.setdefault("soft_lock_reason", "not evaluated")
    data.setdefault("trend_walk_mode", "")
    data.setdefault("trend_walk_reason", "")
    data.setdefault("trend_normal_mode", "")
    data.setdefault("trend_normal_reason", "")
    data.setdefault("cooldown_override", False)
    data.setdefault("cooldown_override_reason", "")
    data.setdefault("candle_trend", "UNKNOWN")
    data.setdefault("structure_trend", "UNKNOWN")
    data.setdefault("momentum_shape", "UNKNOWN")
    data.setdefault("wick_rejection", "NONE")
    data.setdefault("exhaustion_risk", 0)
    data.setdefault("trend_quality", 0)
    data.setdefault("candle_filter", "NOT_EVALUATED")
    data.setdefault("candle_reason", "")
    data.setdefault("trend_momentum_mode", "")
    data.setdefault("trend_momentum_reason", "")
    data.setdefault("trend_momentum_override", False)
    data.setdefault("transition_decay_count", 0)
    data.setdefault("transition_decay_required", 0)
    data.setdefault("transition_decay_active", False)
    data.setdefault("transition_decay_reason", "")
    data.setdefault("soft_lock_counter_reset", False)
    data.setdefault("soft_lock_counter_reset_reason", "")
    data.setdefault("fresh_state_reset", False)
    data.setdefault("fresh_state_reset_reason", "")
    data.setdefault("market_state_fresh", True)
    data.setdefault("market_state_signature", "")
    data.setdefault("market_state_path", "")
    data.setdefault("market_state_modified_time", "")
    data.setdefault("market_state_age_sec", 0)
    data.setdefault("market_state_read_signature", "")
    data.setdefault("trend_exhaustion", "UNKNOWN")
    data.setdefault("trend_exhaustion_score", 0)
    data.setdefault("trend_exhaustion_reason", "")
    data.setdefault("late_continuation_risk", False)
    data.setdefault("market_structure", "UNKNOWN")
    data.setdefault("structure_signal", "UNKNOWN")
    data.setdefault("bos_signal", "NONE")
    data.setdefault("choch_signal", "NONE")
    data.setdefault("liquidity_sweep", "NONE")
    data.setdefault("distribution_phase", False)
    data.setdefault("accumulation_phase", False)
    data.setdefault("momentum_decay", False)
    data.setdefault("late_entry_risk", False)
    data.setdefault("master_gate_score", 0)
    data.setdefault("master_gate", "NOT_EVALUATED")
    data.setdefault("master_gate_reason", "")


    if "_market_state_path" in data:
        data["market_state_path"] = data.get("_market_state_path", "")
    if "_market_state_modified_time" in data:
        data["market_state_modified_time"] = data.get("_market_state_modified_time", "")
    if "_market_state_age_sec" in data:
        data["market_state_age_sec"] = data.get("_market_state_age_sec", 0)
    if "_market_state_read_signature" in data:
        data["market_state_read_signature"] = data.get("_market_state_read_signature", "")

    return data

def write_decision(data):
    """
    Safe atomic write for decision.json.

    IMPORTANT:
    - Trading logic is unchanged.
    - Write complete JSON to decision.tmp first.
    - Flush + fsync + close the temp file.
    - Atomically replace decision.json only after temp is complete.
    This reduces the chance that EA reads decision.json while Python is writing it.
    """
    data = ensure_ea_v17_compat_fields(data)
    BASE_PATH.mkdir(parents=True, exist_ok=True)
    temp_path = OUTPUT_PATH.with_suffix(".tmp")

    for _ in range(5):
        try:
            with open(temp_path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2)
                f.flush()
                os.fsync(f.fileno())

            os.replace(str(temp_path), str(OUTPUT_PATH))

            print(
                "AI DECISION:", data.get("decision", ""),
                "|", data.get("entry_type", ""),
                "| mode", data.get("market_mode", ""),
                "| bb", data.get("bb_state", ""),
                "| mgmt", data.get("management", ""),
                "| slot", data.get("entry_slot", 0),
                "|", data.get("reason", ""),
            )
            return True
        except PermissionError as e:
            print("WRITE DECISION LOCKED, RETRY:", e)
            time.sleep(0.1)
        except Exception as e:
            print("WRITE DECISION ERROR:", e)
            time.sleep(0.1)

    return False


def trade(bias, entry_type, sl, tp, reason, entry_slot=1, market_mode="UNKNOWN", bb_state="UNKNOWN", management="SCALP_TP"):
    return {
        "symbol": SYMBOL,
        "timeframe": TIMEFRAME,
        "bias": bias,
        "decision": "TRADE",
        "entry_allowed": True,
        "buy_score": 0,
        "sell_score": 0,
        "buyScore": 0,
        "sellScore": 0,
        "score_gap": 0,
        "adaptive_gap": 0,
        "analysis_quality": 0,
        "trend_walk_mode": "",
        "trend_walk_reason": "",
        "trend_normal_mode": "",
        "trend_normal_reason": "",
        "cooldown_override": False,
        "cooldown_override_reason": "",
        "candle_trend": "UNKNOWN",
        "structure_trend": "UNKNOWN",
        "momentum_shape": "UNKNOWN",
        "wick_rejection": "NONE",
        "exhaustion_risk": 0,
        "trend_quality": 0,
        "candle_filter": "NOT_EVALUATED",
        "candle_reason": "",
        "trend_momentum_mode": "",
        "trend_momentum_reason": "",
        "trend_momentum_override": False,
        "transition_decay_count": 0,
        "transition_decay_required": 0,
        "transition_decay_active": False,
        "transition_decay_reason": "",
        "trend_exhaustion": "UNKNOWN",
        "trend_exhaustion_score": 0,
        "trend_exhaustion_reason": "",
        "late_continuation_risk": False,
        "market_structure": "UNKNOWN",
        "structure_signal": "UNKNOWN",
        "bos_signal": "NONE",
        "choch_signal": "NONE",
        "liquidity_sweep": "NONE",
        "distribution_phase": False,
        "accumulation_phase": False,
        "momentum_decay": False,
        "late_entry_risk": False,
        "master_gate_score": 0,
        "master_gate": "NOT_EVALUATED",
        "master_gate_reason": "",
        "soft_lock_counter_reset": False,
        "soft_lock_counter_reset_reason": "",
        "fresh_state_reset": False,
        "fresh_state_reset_reason": "",
        "market_state_fresh": True,
        "market_state_signature": "",
        "entry_type": entry_type,
        "entry_slot": entry_slot,
        "market_mode": market_mode,
        "bb_state": bb_state,
        "management": management,
        "stop_loss": round(sl, 3),
        "tp1": round(tp, 3),
        "reason": reason,
        "trend_bias": "NEUTRAL",
        "confidence": 0,
        "manual_action": "WAIT",
        "danger_zone": "UNKNOWN",
        "updated_at": now(),
    }


def no_trade(reason, market_mode="UNKNOWN", bb_state="UNKNOWN"):
    return {
        "symbol": SYMBOL,
        "timeframe": TIMEFRAME,
        "bias": "NEUTRAL",
        "decision": "NO_TRADE",
        "entry_allowed": False,
        "buy_score": 0,
        "sell_score": 0,
        "buyScore": 0,
        "sellScore": 0,
        "score_gap": 0,
        "adaptive_gap": 0,
        "analysis_quality": 0,
        "trend_walk_mode": "",
        "trend_walk_reason": "",
        "trend_normal_mode": "",
        "trend_normal_reason": "",
        "cooldown_override": False,
        "cooldown_override_reason": "",
        "candle_trend": "UNKNOWN",
        "structure_trend": "UNKNOWN",
        "momentum_shape": "UNKNOWN",
        "wick_rejection": "NONE",
        "exhaustion_risk": 0,
        "trend_quality": 0,
        "candle_filter": "NOT_EVALUATED",
        "candle_reason": "",
        "trend_momentum_mode": "",
        "trend_momentum_reason": "",
        "trend_momentum_override": False,
        "transition_decay_count": 0,
        "transition_decay_required": 0,
        "transition_decay_active": False,
        "transition_decay_reason": "",
        "trend_exhaustion": "UNKNOWN",
        "trend_exhaustion_score": 0,
        "trend_exhaustion_reason": "",
        "late_continuation_risk": False,
        "market_structure": "UNKNOWN",
        "structure_signal": "UNKNOWN",
        "bos_signal": "NONE",
        "choch_signal": "NONE",
        "liquidity_sweep": "NONE",
        "distribution_phase": False,
        "accumulation_phase": False,
        "momentum_decay": False,
        "late_entry_risk": False,
        "master_gate_score": 0,
        "master_gate": "NOT_EVALUATED",
        "master_gate_reason": "",
        "soft_lock_counter_reset": False,
        "soft_lock_counter_reset_reason": "",
        "fresh_state_reset": False,
        "fresh_state_reset_reason": "",
        "market_state_fresh": True,
        "market_state_signature": "",
        "entry_type": "",
        "entry_slot": 0,
        "market_mode": market_mode,
        "bb_state": bb_state,
        "management": "NO_TRADE",
        "stop_loss": 0,
        "tp1": 0,
        "reason": reason,
        "trend_bias": "NEUTRAL",
        "confidence": 0,
        "manual_action": "WAIT",
        "danger_zone": "UNKNOWN",
        "updated_at": now(),
    }


def is_strong_trend_normal_buy_mild_macd(market_mode, bb_state, bb_extreme, rsi, macd_hist, buy_score, sell_score):
    """
    V19.4 Gate Exception
    Allows BUY in TREND + BB NORMAL when score and RSI are strong, while MACDHist is only mildly negative.
    This prevents blocking valid continuation entries during brief MACD cooling.
    """
    return (
        market_mode == "TREND"
        and bb_state == "NORMAL"
        and bb_extreme != "DEV4_UPPER"
        and (buy_score - sell_score) >= TREND_NORMAL_BUY_MIN_GAP
        and rsi > TREND_NORMAL_BUY_MIN_RSI
        and macd_hist > TREND_NORMAL_BUY_MILD_MACD_MIN
    )


def nova_brain_filter(decision, market_mode, bb_state, bb_extreme, rsi, macd_hist, buy_score, sell_score):
    """
    Nova Brain Final Gate V1
    Last quality-control layer before sending TRADE decision to EA.

    Goal:
    - Reduce weak entries
    - Avoid emotional/chasing behavior
    - Let only higher-quality confluence pass
    """
    if decision.get("decision") != "TRADE":
        return True, "Nova Brain: not a trade decision"

    bias = decision.get("bias", "NEUTRAL")
    entry_slot = safe_int(decision.get("entry_slot", 0))
    management = decision.get("management", "SCALP_TP")
    entry_type = decision.get("entry_type", "")
    is_pullback = "PULLBACK" in entry_type

    # 1) Never trade compression. Wait for breakout first.
    if bb_state == "COMPRESSION":
        return False, "NOVA BLOCK | compression zone - wait breakout"

    # 2) Do not chase new entries into BB dev4 extremes.
    if bias == "BUY" and bb_extreme == "DEV4_UPPER":
        return False, "NOVA BLOCK BUY | dev4 upper over-extension"
    if bias == "SELL" and bb_extreme == "DEV4_LOWER":
        return False, "NOVA BLOCK SELL | dev4 lower over-extension"

    # 3) TREND trades must have momentum confirmation.
    # V17 exception: qualified trend pullbacks are allowed while momentum is cooling,
    # as long as the score edge is strong and MACD is not aggressively opposite.
    if market_mode == "TREND":
        if bias == "BUY" and (rsi < 55.0 or macd_hist < 0):
            mild_macd_allow = is_strong_trend_normal_buy_mild_macd(
                market_mode, bb_state, bb_extreme, rsi, macd_hist, buy_score, sell_score
            )
            if not (
                mild_macd_allow
                or (is_pullback and buy_score - sell_score >= TREND_PULLBACK_MIN_EDGE and rsi >= TREND_PULLBACK_BUY_MIN_RSI and macd_hist >= -TREND_PULLBACK_MACD_TOLERANCE)
            ):
                return False, f"NOVA BLOCK BUY | weak trend momentum RSI={rsi:.2f} MACDHist={macd_hist:.2f}"
        if bias == "SELL" and (rsi > 45.0 or macd_hist > 0):
            if not (is_pullback and sell_score - buy_score >= TREND_PULLBACK_MIN_EDGE and rsi <= TREND_PULLBACK_SELL_MAX_RSI and macd_hist <= TREND_PULLBACK_MACD_TOLERANCE):
                return False, f"NOVA BLOCK SELL | weak trend momentum RSI={rsi:.2f} MACDHist={macd_hist:.2f}"

    # 4) RANGE / SCALP trades need clearer score edge.
    if market_mode == "RANGE" or management == "SCALP_TP":
        if abs(buy_score - sell_score) < 2:
            return False, f"NOVA BLOCK | weak scalp/range edge buyScore={buy_score} sellScore={sell_score}"

    # 5) Avoid weak slot1 scalps inside trend. Trend should be slot2/slot3 only.
    if market_mode == "TREND" and entry_slot == 1:
        return False, "NOVA BLOCK | avoid slot1 scalp inside trend"

    # 6) Runner/HOLD_TRAIL must be true BB walk, except V17 qualified pullback continuation.
    if management == "HOLD_TRAIL":
        if bias == "BUY" and bb_state != "WALK_UP" and not is_pullback:
            return False, "NOVA BLOCK BUY RUNNER | no BB walk up confirmation"
        if bias == "SELL" and bb_state != "WALK_DOWN" and not is_pullback:
            return False, "NOVA BLOCK SELL RUNNER | no BB walk down confirmation"

    return True, "NOVA APPROVED"


def apply_nova_brain_or_block(decision, market_mode, bb_state, bb_extreme, rsi, macd_hist, buy_score, sell_score):
    ok, nova_reason = nova_brain_filter(
        decision, market_mode, bb_state, bb_extreme, rsi, macd_hist, buy_score, sell_score
    )

    if not ok:
        print(nova_reason)
        blocked = no_trade(nova_reason, market_mode, bb_state)
        for key in (
            "buy_score", "sell_score", "score_gap", "dir_m15", "dir_m3",
            "rsi", "macd_hist", "bb_mid", "bb_upper2", "bb_lower2",
            "analysis_quality", "entry_allowed", "adaptive_gap", "learning_enabled", "learning_key",
            "learning_gap_adjust", "learning_note", "learning_stats", "bb_extreme",
            "entry_quality", "entry_quality_reason",
            "soft_lock_state", "soft_lock_direction", "soft_lock_allowed", "soft_lock_reason",
            "transition_decay_count", "transition_decay_required", "transition_decay_active", "transition_decay_reason",
            "soft_lock_counter_reset", "soft_lock_counter_reset_reason",
            "fresh_state_reset", "fresh_state_reset_reason", "market_state_fresh", "market_state_signature",
            "trend_walk_mode", "trend_walk_reason", "trend_walk_override",
            "trend_normal_mode", "trend_normal_reason", "trend_normal_override"
        ):
            if key in decision:
                blocked[key] = decision[key]
        blocked["entry_allowed"] = False
        blocked["nova_brain"] = "BLOCKED"
        blocked["nova_reason"] = nova_reason
        return blocked

    decision["nova_brain"] = "APPROVED"
    decision["nova_reason"] = nova_reason
    decision["reason"] = f"{decision.get('reason', '')} | {nova_reason}"
    return decision


def get_scores(data):
    buy_score = safe_int(data.get("buyScore") or data.get("buy_score") or data.get("buy") or 0)
    sell_score = safe_int(data.get("sellScore") or data.get("sell_score") or data.get("sell") or 0)
    return buy_score, sell_score


def classify_bb_state(bid, ma50, bb_upper, bb_middle, bb_lower, rsi, macd_hist, buy_score, sell_score):
    if bb_upper <= 0 or bb_middle <= 0 or bb_lower <= 0 or bb_upper <= bb_lower:
        return "UNKNOWN"

    width = bb_upper - bb_lower
    near_edge = width * BB_NEAR_EDGE_PCT

    if width <= BB_COMPRESSION_WIDTH_MAX:
        return "COMPRESSION"

    near_upper = bid >= (bb_upper - near_edge)
    near_lower = bid <= (bb_lower + near_edge)

    # BB walk = edge + momentum + direction score + MA50 side
    if near_upper and bid > ma50 and rsi >= BB_WALK_RSI_BUY and macd_hist >= BB_WALK_MACD_MIN and buy_score > sell_score:
        return "WALK_UP"
    if near_lower and bid < ma50 and rsi <= BB_WALK_RSI_SELL and macd_hist <= -BB_WALK_MACD_MIN and sell_score > buy_score:
        return "WALK_DOWN"

    if near_upper:
        return "REVERSAL_UP"
    if near_lower:
        return "REVERSAL_DOWN"

    return "NORMAL"



def classify_bb_extreme(bid, bb4_upper, bb4_lower):
    if bb4_upper <= 0 or bb4_lower <= 0 or bb4_upper <= bb4_lower:
        return "NONE"
    width = bb4_upper - bb4_lower
    edge = width * BB_DEV4_EDGE_PCT
    if bid >= (bb4_upper - edge):
        return "DEV4_UPPER"
    if bid <= (bb4_lower + edge):
        return "DEV4_LOWER"
    return "NONE"


def normalize_bias(value):
    return str(value or "").strip().lower()


def is_bearish_context(h1_bias, h4_bias, ma50, ma90, ma200):
    h1 = normalize_bias(h1_bias)
    h4 = normalize_bias(h4_bias)
    return (
        h4 in ("bearish", "sell")
        or h1 in ("bearish", "sell")
        or (ma50 > 0 and ma90 > 0 and ma50 < ma90)
        or (ma90 > 0 and ma200 > 0 and ma90 < ma200)
    )


def is_bullish_context(h1_bias, h4_bias, ma50, ma90, ma200):
    h1 = normalize_bias(h1_bias)
    h4 = normalize_bias(h4_bias)
    return (
        h4 in ("bullish", "buy")
        or h1 in ("bullish", "buy")
        or (ma50 > 0 and ma90 > 0 and ma50 > ma90)
        or (ma90 > 0 and ma200 > 0 and ma90 > ma200)
    )


def is_near_ma_zone(bid, ma50, ma90, bb_middle):
    if ma50 > 0 and abs(bid - ma50) <= TREND_PULLBACK_MA_TOLERANCE:
        return True
    if ma90 > 0 and abs(bid - ma90) <= TREND_PULLBACK_MA_TOLERANCE:
        return True
    if bb_middle > 0 and abs(bid - bb_middle) <= TREND_PULLBACK_MA_TOLERANCE:
        return True
    return False


def is_near_bb_middle(bid, bb_upper, bb_middle, bb_lower):
    if bb_upper <= 0 or bb_middle <= 0 or bb_lower <= 0 or bb_upper <= bb_lower:
        return False
    return abs(bid - bb_middle) <= (bb_upper - bb_lower) * ENTRY_MIDDLE_ZONE_PCT


def infer_m3_direction(rsi, macd_hist, buy_score, sell_score):
    edge = buy_score - sell_score
    if edge >= 2 and (rsi >= 50.0 or macd_hist > 0):
        return "BUY"
    if edge <= -2 and (rsi <= 50.0 or macd_hist < 0):
        return "SELL"
    if edge >= 3:
        return "BUY"
    if edge <= -3:
        return "SELL"
    return "NEUTRAL"


def infer_m15_direction(data, bid, ma50, ma90, ma200):
    for key in ("m15_bias", "m15_trend", "m15_direction"):
        value = normalize_bias(data.get(key, ""))
        if value in ("buy", "bullish"):
            return "BUY"
        if value in ("sell", "bearish"):
            return "SELL"

    # Fallback: use current market_state MA structure. This keeps V18 compatible
    # with existing Writer files that do not yet export m15_bias explicitly.
    if bid > ma50 > 0 and ma50 >= ma90 > 0:
        return "BUY"
    if bid < ma50 and ma50 > 0 and ma50 <= ma90:
        return "SELL"
    if ma50 > ma90 > ma200 > 0:
        return "BUY"
    if ma50 < ma90 < ma200 and ma200 > 0:
        return "SELL"
    return "NEUTRAL"


def has_momentum_confirmation(bias, market_mode, bb_state, rsi, macd_hist, buy_score, sell_score, entry_type):
    is_pullback = "PULLBACK" in str(entry_type)
    is_range_reversal = is_selective_range_reversal_entry(entry_type)

    if bias == "BUY":
        if is_range_reversal and bb_state == "REVERSAL_DOWN" and rsi <= RANGE_REVERSAL_RSI_BUY_MAX and macd_hist >= RANGE_REVERSAL_MACD_BUY_MIN:
            return True, "momentum ok | RANGE REVERSAL_DOWN bounce"
        if buy_score <= sell_score:
            return False, "ENTRY BLOCK BUY | score not dominant"
        # Avoid exhausted upside scalp when RSI is overbought and MACD already rolls down.
        if market_mode == "SPIKE" and rsi >= ENTRY_SPIKE_EXHAUSTION_RSI_HIGH and macd_hist < 0:
            return False, f"ENTRY BLOCK BUY | spike exhaustion RSI={rsi:.2f} MACDHist={macd_hist:.2f}"
        if bb_state == "WALK_UP":
            return True, "momentum ok | BB walk up"
        if is_strong_trend_normal_buy_mild_macd(market_mode, bb_state, "NONE", rsi, macd_hist, buy_score, sell_score):
            return True, "momentum ok | TREND NORMAL strong RSI + mild MACD cooling"
        if is_pullback:
            return macd_hist >= -TREND_PULLBACK_MACD_TOLERANCE, "ENTRY BLOCK BUY | pullback MACD too bearish" if macd_hist < -TREND_PULLBACK_MACD_TOLERANCE else "momentum ok | pullback"
        if rsi >= 50.0 and macd_hist >= -ENTRY_MOMENTUM_MACD_TOLERANCE:
            return True, "momentum ok"
        if buy_score - sell_score >= 3 and macd_hist > 0:
            return True, "momentum ok | score edge + MACD"
        return False, f"ENTRY BLOCK BUY | no momentum confirmation RSI={rsi:.2f} MACDHist={macd_hist:.2f}"

    if bias == "SELL":
        if is_range_reversal and bb_state == "REVERSAL_UP" and rsi >= RANGE_REVERSAL_RSI_SELL_MIN and macd_hist <= RANGE_REVERSAL_MACD_SELL_MAX:
            return True, "momentum ok | RANGE REVERSAL_UP rejection"
        if sell_score <= buy_score:
            return False, "ENTRY BLOCK SELL | score not dominant"
        # Avoid exhausted downside scalp when RSI is oversold and MACD already turns positive.
        if market_mode == "SPIKE" and rsi <= ENTRY_SPIKE_EXHAUSTION_RSI_LOW and macd_hist > 0:
            return False, f"ENTRY BLOCK SELL | spike exhaustion RSI={rsi:.2f} MACDHist={macd_hist:.2f}"
        if bb_state == "WALK_DOWN":
            return True, "momentum ok | BB walk down"
        if is_pullback:
            return macd_hist <= TREND_PULLBACK_MACD_TOLERANCE, "ENTRY BLOCK SELL | pullback MACD too bullish" if macd_hist > TREND_PULLBACK_MACD_TOLERANCE else "momentum ok | pullback"
        if rsi <= 50.0 and macd_hist <= ENTRY_MOMENTUM_MACD_TOLERANCE:
            return True, "momentum ok"
        if sell_score - buy_score >= 3 and macd_hist < 0:
            return True, "momentum ok | score edge + MACD"
        return False, f"ENTRY BLOCK SELL | no momentum confirmation RSI={rsi:.2f} MACDHist={macd_hist:.2f}"

    return False, "ENTRY BLOCK | neutral bias"


def clamp_float(value, min_value=0.0, max_value=1.0):
    try:
        return max(min_value, min(max_value, float(value)))
    except Exception:
        return min_value


def direction_to_int(direction):
    if direction == "BUY":
        return 1
    if direction == "SELL":
        return -1
    return 0


def classify_entry_family(entry_type):
    entry_type = str(entry_type or "").upper()
    if "PULLBACK" in entry_type:
        return "PULLBACK"
    if "RUNNER" in entry_type or "WALK" in entry_type:
        return "WALK_RUNNER"
    if "SPIKE" in entry_type:
        return "SPIKE"
    if "SCALP" in entry_type:
        return "SCALP"
    if "TREND" in entry_type:
        return "TREND"
    return "GENERAL"


def make_learning_key(bias, market_mode, bb_state, management, entry_type):
    family = classify_entry_family(entry_type)
    return f"{bias}|{market_mode}|{bb_state}|{management}|{family}"


def default_learning_state():
    return {"version": "V19", "processed_ids": [], "setups": {}, "updated_at": now()}


def load_learning_state():
    try:
        if LEARNING_STATE_PATH.exists():
            return json.loads(LEARNING_STATE_PATH.read_text(encoding="utf-8"))
    except Exception as e:
        print("LEARNING STATE READ ERROR:", e)
    return default_learning_state()


def save_learning_state(state):
    try:
        BASE_PATH.mkdir(parents=True, exist_ok=True)
        state["updated_at"] = now()
        temp_path = LEARNING_STATE_PATH.with_suffix(".tmp")
        temp_path.write_text(json.dumps(state, indent=2), encoding="utf-8")
        temp_path.replace(LEARNING_STATE_PATH)
    except Exception as e:
        print("LEARNING STATE WRITE ERROR:", e)


def normalize_trade_result_record(record):
    """
    Expected optional input files:
      trade_results.jsonl  one JSON object per line
      trade_results.json   list[object] or {"trades": list[object]}

    Minimal fields accepted:
      profit or pnl: number
      bias, market_mode, bb_state, management, entry_type: strings
      id/order/ticket/position/time: any unique identifier
    """
    if not isinstance(record, dict):
        return None
    profit = safe_float(record.get("profit", record.get("pnl", record.get("net_profit", 0.0))), 0.0)
    rid = str(
        record.get("id")
        or record.get("ticket")
        or record.get("order")
        or record.get("position")
        or record.get("close_time")
        or record.get("time")
        or f"{record.get('entry_type','')}|{record.get('updated_at','')}|{profit}"
    )
    bias = str(record.get("bias", record.get("direction", "NEUTRAL"))).upper()
    if bias not in ("BUY", "SELL"):
        typ = str(record.get("type", "")).lower()
        bias = "BUY" if typ == "buy" else "SELL" if typ == "sell" else "NEUTRAL"
    return {
        "id": rid,
        "profit": profit,
        "win": profit > 0,
        "bias": bias,
        "market_mode": str(record.get("market_mode", "UNKNOWN")).upper(),
        "bb_state": str(record.get("bb_state", "UNKNOWN")).upper(),
        "management": str(record.get("management", "UNKNOWN")).upper(),
        "entry_type": str(record.get("entry_type", "UNKNOWN")).upper(),
    }


def read_trade_result_records():
    records = []
    try:
        if LEARNING_RESULTS_JSONL.exists():
            for line in LEARNING_RESULTS_JSONL.read_text(encoding="utf-8").splitlines():
                line = line.strip()
                if not line:
                    continue
                try:
                    records.append(json.loads(line))
                except Exception:
                    continue
    except Exception as e:
        print("LEARNING JSONL READ ERROR:", e)
    try:
        if LEARNING_RESULTS_JSON.exists():
            raw = json.loads(LEARNING_RESULTS_JSON.read_text(encoding="utf-8"))
            if isinstance(raw, dict):
                raw = raw.get("trades", [])
            if isinstance(raw, list):
                records.extend(raw)
    except Exception as e:
        print("LEARNING JSON READ ERROR:", e)
    return records


def update_learning_from_trade_results():
    if not LEARNING_ENABLED:
        return load_learning_state()
    state = load_learning_state()
    processed = set(state.get("processed_ids", []))
    setups = state.setdefault("setups", {})
    changed = False

    for raw in read_trade_result_records():
        rec = normalize_trade_result_record(raw)
        if rec is None or rec["id"] in processed:
            continue
        key = make_learning_key(rec["bias"], rec["market_mode"], rec["bb_state"], rec["management"], rec["entry_type"])
        stats = setups.setdefault(key, {"trades": 0, "wins": 0, "losses": 0, "net_profit": 0.0, "avg_profit": 0.0, "winrate": 0.0})
        stats["trades"] += 1
        stats["wins"] += 1 if rec["win"] else 0
        stats["losses"] += 0 if rec["win"] else 1
        stats["net_profit"] = round(float(stats.get("net_profit", 0.0)) + rec["profit"], 4)
        stats["avg_profit"] = round(stats["net_profit"] / max(1, stats["trades"]), 4)
        stats["winrate"] = round(stats["wins"] / max(1, stats["trades"]), 4)
        processed.add(rec["id"])
        changed = True

    if changed:
        state["processed_ids"] = list(processed)[-1000:]
        save_learning_state(state)
    return state


def base_adaptive_gap_requirement(market_mode, bb_state, rsi, macd_hist, management, entry_type):
    family = classify_entry_family(entry_type)
    if market_mode == "TREND":
        if bb_state in ("WALK_UP", "WALK_DOWN"):
            return 2
        if family == "PULLBACK":
            return 3
        return 3
    if market_mode == "RANGE":
        return 3
    if market_mode == "SPIKE":
        if rsi <= ENTRY_SPIKE_EXHAUSTION_RSI_LOW or rsi >= ENTRY_SPIKE_EXHAUSTION_RSI_HIGH:
            return 4
        return 3
    if market_mode == "TRANSITION":
        return 4
    return 3


def learning_gap_adjustment(state, learning_key):
    stats = state.get("setups", {}).get(learning_key, {}) if isinstance(state, dict) else {}
    trades = safe_int(stats.get("trades", 0), 0)
    winrate = safe_float(stats.get("winrate", 0.0), 0.0)
    avg_profit = safe_float(stats.get("avg_profit", 0.0), 0.0)
    adjustment = 0
    note = "LEARNING neutral / insufficient data"

    if trades >= LEARNING_MIN_TRADES:
        if winrate < LEARNING_BAD_WINRATE or avg_profit < 0:
            adjustment = 1
            note = f"LEARNING strict | trades={trades} winrate={winrate:.2f} avg={avg_profit:.2f}"
        elif winrate >= LEARNING_GOOD_WINRATE and avg_profit > 0:
            adjustment = -1
            note = f"LEARNING permissive | trades={trades} winrate={winrate:.2f} avg={avg_profit:.2f}"
        else:
            note = f"LEARNING neutral | trades={trades} winrate={winrate:.2f} avg={avg_profit:.2f}"
    return adjustment, stats, note


def compute_analysis_quality(score_gap, m15_dir, m3_dir, bias, market_mode, bb_state, rsi, macd_hist, near_middle, learning_adjust):
    quality = 0
    quality += min(score_gap, 5) * 12
    if m15_dir == m3_dir and m15_dir != "NEUTRAL":
        quality += 18
    if bias == m3_dir:
        quality += 10
    if bias == m15_dir:
        quality += 10
    if market_mode == "TREND":
        quality += 10
    if bb_state in ("WALK_UP", "WALK_DOWN"):
        quality += 10
    if (bias == "BUY" and rsi >= 50 and macd_hist >= -ENTRY_MOMENTUM_MACD_TOLERANCE) or (bias == "SELL" and rsi <= 50 and macd_hist <= ENTRY_MOMENTUM_MACD_TOLERANCE):
        quality += 12
    if near_middle and market_mode != "TREND":
        quality -= 15
    if learning_adjust > 0:
        quality -= 8 * learning_adjust
    elif learning_adjust < 0:
        quality += 5
    return clamp_int(quality, 0, 100)


def enrich_decision_for_entry_gate(decision, data, market_mode, bb_state, bb_extreme, buy_score, sell_score, adaptive_gap=None, learning_key=None, learning_stats=None, learning_adjust=0, learning_note=""):
    bid = safe_float(data.get("bid", 0))
    ma50 = safe_float(data.get("ma50", 0))
    ma90 = safe_float(data.get("ma90", 0))
    ma200 = safe_float(data.get("ma200", 0))
    rsi = safe_float(data.get("rsi", 50))
    macd_hist = safe_float(data.get("macd_hist", 0))
    bb_upper = safe_float(data.get("bb_upper", 0))
    bb_middle = safe_float(data.get("bb_middle", 0))
    bb_lower = safe_float(data.get("bb_lower", 0))
    score_gap = abs(buy_score - sell_score)
    m3_dir = infer_m3_direction(rsi, macd_hist, buy_score, sell_score)
    m15_dir = infer_m15_direction(data, bid, ma50, ma90, ma200)
    bias = decision.get("bias", "NEUTRAL")
    near_middle = is_near_bb_middle(bid, bb_upper, bb_middle, bb_lower)
    analysis_quality = compute_analysis_quality(score_gap, m15_dir, m3_dir, bias, market_mode, bb_state, rsi, macd_hist, near_middle, learning_adjust)
    decision.update({
        "buy_score": buy_score,
        "sell_score": sell_score,
        "buyScore": buy_score,
        "sellScore": sell_score,
        "score_gap": score_gap,
        "dir_m15": direction_to_int(m15_dir),
        "dir_m3": direction_to_int(m3_dir),
        "rsi": round(rsi, 2),
        "macd_hist": round(macd_hist, 5),
        "bb_mid": round(bb_middle, 3),
        "bb_upper2": round(bb_upper, 3),
        "bb_lower2": round(bb_lower, 3),
        "analysis_quality": analysis_quality,
        "entry_allowed": decision.get("decision") == "TRADE",
        "adaptive_gap": adaptive_gap if adaptive_gap is not None else 0,
        "learning_enabled": LEARNING_ENABLED,
        "learning_key": learning_key or "",
        "learning_gap_adjust": learning_adjust,
        "learning_note": learning_note,
        "learning_stats": learning_stats or {},
        "bb_extreme": bb_extreme,
        "trend_walk_mode": decision.get("trend_walk_mode", ""),
        "trend_walk_reason": decision.get("trend_walk_reason", ""),
        "trend_normal_mode": decision.get("trend_normal_mode", ""),
        "trend_normal_reason": decision.get("trend_normal_reason", ""),
        "trend_momentum_mode": decision.get("trend_momentum_mode", ""),
        "trend_momentum_reason": decision.get("trend_momentum_reason", ""),
        "trend_momentum_override": decision.get("trend_momentum_override", False),
        "market_state_path": data.get("_market_state_path", decision.get("market_state_path", "")),
        "market_state_modified_time": data.get("_market_state_modified_time", decision.get("market_state_modified_time", "")),
        "market_state_age_sec": data.get("_market_state_age_sec", decision.get("market_state_age_sec", 0)),
        "market_state_read_signature": data.get("_market_state_read_signature", decision.get("market_state_read_signature", "")),
        "trend_exhaustion": decision.get("trend_exhaustion", "UNKNOWN"),
        "trend_exhaustion_score": decision.get("trend_exhaustion_score", 0),
        "trend_exhaustion_reason": decision.get("trend_exhaustion_reason", ""),
        "late_continuation_risk": decision.get("late_continuation_risk", False),
        "market_structure": decision.get("market_structure", "UNKNOWN"),
        "structure_signal": decision.get("structure_signal", "UNKNOWN"),
        "bos_signal": decision.get("bos_signal", "NONE"),
        "choch_signal": decision.get("choch_signal", "NONE"),
        "liquidity_sweep": decision.get("liquidity_sweep", "NONE"),
        "distribution_phase": decision.get("distribution_phase", False),
        "accumulation_phase": decision.get("accumulation_phase", False),
        "momentum_decay": decision.get("momentum_decay", False),
        "late_entry_risk": decision.get("late_entry_risk", False),
        "master_gate_score": decision.get("master_gate_score", 0),
        "master_gate": decision.get("master_gate", "NOT_EVALUATED"),
        "master_gate_reason": decision.get("master_gate_reason", ""),
    })
    return decision



def is_strong_normal_direction_setup(bias, score_gap, rsi, macd_hist):
    """
    V19.6: very strong directional setup.
    Used to bypass the BB-middle block only when score + RSI + MACD all confirm.
    """
    if bias == "BUY":
        return (
            score_gap >= STRONG_NORMAL_UNLOCK_GAP
            and rsi >= STRONG_NORMAL_BUY_RSI_MIN
            and macd_hist >= STRONG_NORMAL_BUY_MACD_MIN
        )
    if bias == "SELL":
        return (
            score_gap >= STRONG_NORMAL_UNLOCK_GAP
            and rsi <= STRONG_NORMAL_SELL_RSI_MAX
            and macd_hist <= STRONG_NORMAL_SELL_MACD_MAX
        )
    return False


def transition_rsi_macd_confirm(bias, rsi, macd_hist):
    """
    V19.7: direction confirmation for TRANSITION+NORMAL.
    BUY needs RSI >= 52 and MACD not strongly bearish.
    SELL needs RSI <= 48 and MACD not strongly bullish.
    """
    if bias == "BUY":
        return rsi >= TRANSITION_RSI_BUY_MIN and macd_hist >= TRANSITION_MACD_BUY_MIN
    if bias == "SELL":
        return rsi <= TRANSITION_RSI_SELL_MAX and macd_hist <= TRANSITION_MACD_SELL_MAX
    return False


def is_strong_transition_normal_setup(bias, score_gap, rsi, macd_hist, bid, bb_upper, bb_middle, bb_lower):
    """
    V19.7: Allow TRANSITION + BB NORMAL when the setup is selective but not too restrictive.
    Rules:
    1) score_gap >= 2
    2) RSI confirms direction
    3) MACDHist is not strongly opposite
    4) If near BB middle, allow only when RSI + MACD both confirm
    """
    reasons = []
    near_middle = is_near_bb_middle(bid, bb_upper, bb_middle, bb_lower)

    if score_gap < TRANSITION_NORMAL_ALLOW_GAP:
        reasons.append(f"gap<{TRANSITION_NORMAL_ALLOW_GAP}")

    direction_ok = transition_rsi_macd_confirm(bias, rsi, macd_hist)

    if bias == "BUY":
        if rsi < TRANSITION_RSI_BUY_MIN:
            reasons.append(f"rsi_not_bullish:{rsi:.2f}<{TRANSITION_RSI_BUY_MIN}")
        if macd_hist < TRANSITION_MACD_BUY_MIN:
            reasons.append(f"macd_strongly_opposite:{macd_hist:.2f}<{TRANSITION_MACD_BUY_MIN}")
    elif bias == "SELL":
        if rsi > TRANSITION_RSI_SELL_MAX:
            reasons.append(f"rsi_not_bearish:{rsi:.2f}>{TRANSITION_RSI_SELL_MAX}")
        if macd_hist > TRANSITION_MACD_SELL_MAX:
            reasons.append(f"macd_strongly_opposite:{macd_hist:.2f}>{TRANSITION_MACD_SELL_MAX}")
    else:
        reasons.append("neutral_bias")

    # Near BB middle is allowed only if both RSI and MACD confirm the direction.
    if near_middle and not direction_ok:
        reasons.append("near_bb_middle_without_rsi_macd_confirm")

    return len(reasons) == 0, reasons

def get_selective_range_reversal_bias(bb_state, rsi, macd_hist, buy_score, sell_score):
    """
    V19.6 Selective Strong Setup Unlock
    Allows only edge-confirmed BB edge bounce entries:
    - REVERSAL_DOWN -> BUY bounce
    - REVERSAL_UP   -> SELL rejection
    It does NOT allow score_gap=0 unless RSI/MACD clearly confirm the bounce.
    """
    score_gap = abs(buy_score - sell_score)

    if bb_state == "REVERSAL_DOWN":
        momentum_ok = (rsi <= RANGE_REVERSAL_RSI_BUY_MAX and macd_hist >= RANGE_REVERSAL_MACD_BUY_MIN)
        score_ok = (buy_score > sell_score and score_gap >= RANGE_REVERSAL_MIN_GAP)
        equal_ok = (buy_score == sell_score and RANGE_REVERSAL_ALLOW_EQUAL_WITH_MOMENTUM and momentum_ok)
        if momentum_ok and (score_ok or equal_ok):
            return "BUY", f"RANGE REVERSAL BUY ALLOW | bb=REVERSAL_DOWN rsi={rsi:.2f} macd={macd_hist:.2f} score={buy_score}:{sell_score}"

    if bb_state == "REVERSAL_UP":
        momentum_ok = (rsi >= RANGE_REVERSAL_RSI_SELL_MIN and macd_hist <= RANGE_REVERSAL_MACD_SELL_MAX)
        score_ok = (sell_score > buy_score and score_gap >= RANGE_REVERSAL_MIN_GAP)
        equal_ok = (buy_score == sell_score and RANGE_REVERSAL_ALLOW_EQUAL_WITH_MOMENTUM and momentum_ok)
        if momentum_ok and (score_ok or equal_ok):
            return "SELL", f"RANGE REVERSAL SELL ALLOW | bb=REVERSAL_UP rsi={rsi:.2f} macd={macd_hist:.2f} score={buy_score}:{sell_score}"

    return "", ""


def is_selective_range_reversal_entry(entry_type):
    return "RANGE_REVERSAL" in str(entry_type or "").upper()

def dual_direction_confirm(bias, rsi, macd_hist):
    """
    V19.8: softer direction confirmation for aggressive mode.
    Allows transition/range entries faster, but blocks strongly opposite momentum.
    """
    if bias == "BUY":
        return rsi >= DUAL_AGGRESSIVE_BUY_RSI_MIN and macd_hist >= DUAL_AGGRESSIVE_BUY_MACD_MIN
    if bias == "SELL":
        return rsi <= DUAL_AGGRESSIVE_SELL_RSI_MAX and macd_hist <= DUAL_AGGRESSIVE_SELL_MACD_MAX
    return False


def is_trend_priority_setup(bias, bid, ma50, ma90, ma200, bb_state, bb_extreme, rsi, macd_hist, buy_score, sell_score):
    """
    V20 Trend Priority Mode.

    This is an entry-priority classifier, not a blind trade trigger.
    It allows clear directional continuation to be treated as TREND even when
    BB is NORMAL or price is near BB middle. It keeps the hard safety blocks:
    DEV4 over-extension and BB compression.
    """
    if not TREND_PRIORITY_ENABLED:
        return False
    if bb_extreme in ("DEV4_UPPER", "DEV4_LOWER"):
        return False
    if bb_state == "COMPRESSION":
        return False

    score_gap = abs(buy_score - sell_score)
    if score_gap < TREND_PRIORITY_MIN_GAP:
        return False

    if bias == "BUY":
        if buy_score <= sell_score:
            return False
        if bid <= ma50 or ma50 <= 0:
            return False
        if rsi < TREND_PRIORITY_BUY_RSI_MIN:
            return False
        if macd_hist < TREND_PRIORITY_BUY_MACD_MIN:
            return False
        # Prefer at least mild MA structure confirmation when available.
        if ma90 > 0 and ma200 > 0 and not (ma50 >= ma90 or ma90 >= ma200 or score_gap >= TREND_PRIORITY_STRONG_GAP):
            return False
        return True

    if bias == "SELL":
        if sell_score <= buy_score:
            return False
        if bid >= ma50 or ma50 <= 0:
            return False
        if rsi > TREND_PRIORITY_SELL_RSI_MAX:
            return False
        if macd_hist > TREND_PRIORITY_SELL_MACD_MAX:
            return False
        if ma90 > 0 and ma200 > 0 and not (ma50 <= ma90 or ma90 <= ma200 or score_gap >= TREND_PRIORITY_STRONG_GAP):
            return False
        return True

    return False


def trend_priority_bias(bid, ma50, ma90, ma200, bb_state, bb_extreme, rsi, macd_hist, buy_score, sell_score):
    if is_trend_priority_setup("BUY", bid, ma50, ma90, ma200, bb_state, bb_extreme, rsi, macd_hist, buy_score, sell_score):
        return "BUY"
    if is_trend_priority_setup("SELL", bid, ma50, ma90, ma200, bb_state, bb_extreme, rsi, macd_hist, buy_score, sell_score):
        return "SELL"
    return ""



def infer_soft_trend_direction(market_mode, bb_state, bid, ma50, ma90, ma200, buy_score, sell_score):
    """
    V21 Soft Direction Lock V2 helper.
    Detects the active directional lock from BB walk, market mode, MA structure and score.
    This is intentionally softer than the old hard lock: it can move to TRANSITION_WAIT
    or REVERSAL_ALLOW instead of permanently blocking the opposite side.
    """
    if bb_state == "WALK_UP":
        return "BUY", "BB WALK_UP active trend"
    if bb_state == "WALK_DOWN":
        return "SELL", "BB WALK_DOWN active trend"

    if market_mode == "TREND":
        if buy_score > sell_score and bid > ma50 and ma50 > 0:
            return "BUY", "TREND BUY context"
        if sell_score > buy_score and bid < ma50 and ma50 > 0:
            return "SELL", "TREND SELL context"

    # Fallback MA stack context only when score agrees.
    if buy_score > sell_score and ma50 > ma90 > 0 and (ma90 >= ma200 or ma200 <= 0):
        return "BUY", "MA stack bullish context"
    if sell_score > buy_score and ma50 < ma90 and ma90 > 0 and (ma90 <= ma200 or ma200 <= 0):
        return "SELL", "MA stack bearish context"

    return "", "no active soft direction lock"


def is_soft_trend_weakening(locked_direction, bb_state, rsi, macd_hist, buy_score, sell_score):
    """Returns True when the locked trend starts losing internal momentum."""
    if locked_direction == "BUY":
        if bb_state in ("REVERSAL_UP", "COMPRESSION"):
            return True
        if sell_score > buy_score:
            return True
        if rsi < SOFT_LOCK_BUY_RSI_WEAK:
            return True
        if macd_hist < -SOFT_LOCK_MACD_WEAK_BUFFER:
            return True
        return False

    if locked_direction == "SELL":
        if bb_state in ("REVERSAL_DOWN", "COMPRESSION"):
            return True
        if buy_score > sell_score:
            return True
        if rsi > SOFT_LOCK_SELL_RSI_WEAK:
            return True
        if macd_hist > SOFT_LOCK_MACD_WEAK_BUFFER:
            return True
        return False

    return False


def is_soft_reversal_confirmed(locked_direction, bb_state, bb_extreme, rsi, macd_hist, buy_score, sell_score, bid, bb_middle):
    """Returns True when reversal is strong enough to allow opposite direction."""
    if locked_direction == "SELL":
        score_ok = (buy_score - sell_score) >= SOFT_REVERSAL_MIN_SCORE_EDGE
        edge_ok = bb_state == "REVERSAL_DOWN" or bb_extreme == "DEV4_LOWER"
        momentum_ok = rsi >= SOFT_REVERSAL_BUY_RSI_MIN and macd_hist >= SOFT_REVERSAL_MACD_MIN
        location_ok = (bb_middle <= 0) or (bid >= bb_middle) or edge_ok
        return score_ok and edge_ok and momentum_ok and location_ok

    if locked_direction == "BUY":
        score_ok = (sell_score - buy_score) >= SOFT_REVERSAL_MIN_SCORE_EDGE
        edge_ok = bb_state == "REVERSAL_UP" or bb_extreme == "DEV4_UPPER"
        momentum_ok = rsi <= SOFT_REVERSAL_SELL_RSI_MAX and macd_hist <= SOFT_REVERSAL_MACD_MAX
        location_ok = (bb_middle <= 0) or (bid <= bb_middle) or edge_ok
        return score_ok and edge_ok and momentum_ok and location_ok

    return False



def transition_decay_key(locked_direction, market_mode, bb_state):
    return f"{SYMBOL}|{locked_direction}|{market_mode}|{bb_state}"


def is_recovery_from_weakening(locked_direction, rsi, macd_hist, buy_score, sell_score):
    """Returns True when trend shows enough recovery to reset decay counter."""
    score_gap = abs(buy_score - sell_score)

    if TRANSITION_DECAY_RESET_ON_STRONG_SCORE and score_gap >= TRANSITION_DECAY_STRONG_SCORE_GAP:
        if locked_direction == "BUY" and buy_score > sell_score:
            return True
        if locked_direction == "SELL" and sell_score > buy_score:
            return True

    if locked_direction == "BUY":
        return rsi >= TRANSITION_DECAY_BUY_RSI_RECOVER and macd_hist >= TRANSITION_DECAY_BUY_MACD_RECOVER and buy_score >= sell_score

    if locked_direction == "SELL":
        return rsi <= TRANSITION_DECAY_SELL_RSI_RECOVER and macd_hist <= TRANSITION_DECAY_SELL_MACD_RECOVER and sell_score >= buy_score

    return False




def _fresh_dir_from_rsi(rsi):
    return "BUY" if rsi >= 50.0 else "SELL"


def _fresh_dir_from_macd(macd_hist):
    if macd_hist > FRESH_STATE_MACD_FLIP_EPS:
        return "BUY"
    if macd_hist < -FRESH_STATE_MACD_FLIP_EPS:
        return "SELL"
    return "NEUTRAL"


def _fresh_score_dir(buy_score, sell_score):
    if buy_score > sell_score:
        return "BUY"
    if sell_score > buy_score:
        return "SELL"
    return "NEUTRAL"


def make_fresh_state_signature(data, market_mode, bb_state, buy_score, sell_score):
    rsi = safe_float(data.get("rsi", 50), 50)
    macd_hist = safe_float(data.get("macd_hist", 0), 0)
    server_time = str(data.get("server_time", data.get("updated_at", data.get("time", ""))))
    bar_time = str(data.get("bar_time", ""))
    rsi_dir = _fresh_dir_from_rsi(rsi)
    macd_dir = _fresh_dir_from_macd(macd_hist)
    score_dir = _fresh_score_dir(buy_score, sell_score)
    signature = f"{server_time}|{bar_time}|{market_mode}|{bb_state}|{score_dir}|{rsi_dir}|{macd_dir}|{buy_score}:{sell_score}|{rsi:.2f}|{macd_hist:.2f}"
    return {
        "server_time": server_time,
        "bar_time": bar_time,
        "market_mode": str(market_mode),
        "bb_state": str(bb_state),
        "score_dir": score_dir,
        "rsi_dir": rsi_dir,
        "macd_dir": macd_dir,
        "buy_score": buy_score,
        "sell_score": sell_score,
        "rsi": rsi,
        "macd_hist": macd_hist,
        "signature": signature,
    }


def fresh_state_reset_check(active_key, locked_direction, data, market_mode, bb_state, buy_score, sell_score):
    """
    V23.3:
    Reset stale soft-lock/decay when newest market_state no longer matches old lock context.
    This prevents decision.json staying in old TRANSITION_WAIT with old RSI/MACD/score.
    """
    if not FRESH_STATE_RESET_ENABLED:
        return {
            "fresh_state_reset": False,
            "fresh_state_reset_reason": "fresh reset disabled",
            "market_state_fresh": True,
            "market_state_signature": "",
        }

    sig = make_fresh_state_signature(data or {}, market_mode, bb_state, buy_score, sell_score)
    prev = fresh_state_snapshot.get(active_key)
    reasons = []

    if prev:
        if prev.get("market_mode") != sig.get("market_mode"):
            reasons.append(f"market_mode {prev.get('market_mode')}->{sig.get('market_mode')}")
        if prev.get("bb_state") != sig.get("bb_state"):
            reasons.append(f"bb_state {prev.get('bb_state')}->{sig.get('bb_state')}")
        if prev.get("score_dir") != sig.get("score_dir"):
            reasons.append(f"score_dir {prev.get('score_dir')}->{sig.get('score_dir')}")
        if prev.get("rsi_dir") != sig.get("rsi_dir"):
            reasons.append(f"rsi_dir {prev.get('rsi_dir')}->{sig.get('rsi_dir')}")
        if prev.get("macd_dir") != sig.get("macd_dir"):
            reasons.append(f"macd_dir {prev.get('macd_dir')}->{sig.get('macd_dir')}")
        if prev.get("bar_time") and sig.get("bar_time") and prev.get("bar_time") != sig.get("bar_time"):
            reasons.append(f"bar_time {prev.get('bar_time')}->{sig.get('bar_time')}")

    # Current data no longer matches locked direction.
    score_dir = sig.get("score_dir")
    rsi_dir = sig.get("rsi_dir")
    macd_dir = sig.get("macd_dir")
    if locked_direction == "BUY":
        if score_dir == "SELL" or (rsi_dir == "SELL" and macd_dir == "SELL"):
            reasons.append("current data no longer matches BUY lock")
    elif locked_direction == "SELL":
        if score_dir == "BUY" or (rsi_dir == "BUY" and macd_dir == "BUY"):
            reasons.append("current data no longer matches SELL lock")

    if reasons:
        transition_decay_state.clear()
        transition_decay_meta.clear()
        fresh_state_snapshot.clear()
        fresh_state_snapshot[active_key] = sig
        return {
            "fresh_state_reset": True,
            "fresh_state_reset_reason": "; ".join(reasons),
            "market_state_fresh": True,
            "market_state_signature": sig.get("signature", ""),
        }

    fresh_state_snapshot[active_key] = sig
    return {
        "fresh_state_reset": False,
        "fresh_state_reset_reason": "fresh state aligned",
        "market_state_fresh": True,
        "market_state_signature": sig.get("signature", ""),
    }

def reset_stale_transition_decay_keys(active_key, locked_direction, market_mode, bb_state, bar_time, rsi, macd_hist, buy_score, sell_score, data=None):
    """
    V23_3.1 reset controller.
    Resets stale persistent weakening counter when:
    1) direction/mode/bb context changes
    2) momentum becomes aligned again
    3) new bar starts
    4) counter expires by time
    5) counter grows beyond max keep cap
    """
    if not SOFT_LOCK_COUNTER_RESET_ENABLED:
        return {
            "soft_lock_counter_reset": False,
            "soft_lock_counter_reset_reason": "reset disabled",
        }

    now_ts = time.time()
    reasons = []

    fresh_info = fresh_state_reset_check(
        active_key, locked_direction, data or {}, market_mode, bb_state, buy_score, sell_score
    )

    # Direction / market mode / BB state change creates a different key.
    stale_keys = [k for k in list(transition_decay_state.keys()) if k != active_key]
    if stale_keys:
        for k in stale_keys:
            transition_decay_state.pop(k, None)
            transition_decay_meta.pop(k, None)
        reasons.append("context changed: direction/mode/bb")

    meta = transition_decay_meta.get(active_key, {})
    prev_bar = str(meta.get("bar_time", ""))
    prev_ts = safe_float(meta.get("ts", 0), 0)

    # Momentum realigned again.
    if is_recovery_from_weakening(locked_direction, rsi, macd_hist, buy_score, sell_score):
        transition_decay_state[active_key] = 0
        reasons.append("momentum realigned")

    # New bar reset.
    if SOFT_LOCK_RESET_ON_NEW_BAR and prev_bar and bar_time and prev_bar != str(bar_time):
        transition_decay_state[active_key] = 0
        reasons.append(f"new bar {prev_bar}->{bar_time}")

    # Time expiry reset.
    if prev_ts > 0 and (now_ts - prev_ts) >= SOFT_LOCK_COUNTER_EXPIRE_SECONDS:
        transition_decay_state[active_key] = 0
        reasons.append(f"expired {int(now_ts - prev_ts)}s")

    # Hard cap: prevents 1664/3 style stale count.
    current_count = transition_decay_state.get(active_key, 0)
    if current_count > SOFT_LOCK_COUNTER_MAX_KEEP:
        transition_decay_state[active_key] = TRANSITION_DECAY_REQUIRED_COUNT
        reasons.append(f"counter capped {current_count}->{TRANSITION_DECAY_REQUIRED_COUNT}")

    transition_decay_meta[active_key] = {"ts": now_ts, "bar_time": str(bar_time)}

    if fresh_info.get("fresh_state_reset"):
        reasons.append("fresh state reset: " + fresh_info.get("fresh_state_reset_reason", ""))

    return {
        "soft_lock_counter_reset": bool(reasons),
        "soft_lock_counter_reset_reason": "; ".join(reasons) if reasons else "no reset",
        **fresh_info,
    }

def apply_transition_decay(locked_direction, market_mode, bb_state, rsi, macd_hist, buy_score, sell_score, raw_weakening, bar_time='', data=None):
    """
    V23_3 Transition Decay Logic V1.

    If trend is weakening for only 1-2 checks, stay TREND_LOCK but mark decay active.
    Only after persistent weakening count >= required count, allow TRANSITION_WAIT.
    """
    if not TRANSITION_DECAY_ENABLED or not locked_direction:
        return raw_weakening, {
            "transition_decay_count": 0,
            "transition_decay_required": 0,
            "transition_decay_active": False,
            "transition_decay_reason": "disabled or no lock",
            "soft_lock_counter_reset": False,
            "soft_lock_counter_reset_reason": "disabled or no lock",
        }

    key = transition_decay_key(locked_direction, market_mode, bb_state)
    required = TRANSITION_DECAY_REQUIRED_COUNT

    reset_info = reset_stale_transition_decay_keys(
        key, locked_direction, market_mode, bb_state, bar_time, rsi, macd_hist, buy_score, sell_score, data
    )

    if is_recovery_from_weakening(locked_direction, rsi, macd_hist, buy_score, sell_score):
        transition_decay_state[key] = 0
        return False, {
            "transition_decay_count": 0,
            "transition_decay_required": required,
            "transition_decay_active": False,
            "transition_decay_reason": "recovery/reset: strong score or RSI/MACD recovered",
            **reset_info,
        }

    if not raw_weakening:
        transition_decay_state[key] = 0
        return False, {
            "transition_decay_count": 0,
            "transition_decay_required": required,
            "transition_decay_active": False,
            "transition_decay_reason": "not weakening",
            **reset_info,
        }

    count = transition_decay_state.get(key, 0) + 1
    transition_decay_state[key] = count

    if count >= required:
        return True, {
            "transition_decay_count": count,
            "transition_decay_required": required,
            "transition_decay_active": True,
            "transition_decay_reason": f"persistent weakening count={count}/{required}; allow TRANSITION_WAIT",
            **reset_info,
        }

    return False, {
        "transition_decay_count": count,
        "transition_decay_required": required,
        "transition_decay_active": True,
        "transition_decay_reason": f"weakening detected count={count}/{required}; keep TREND_LOCK",
        **reset_info,
    }

def soft_direction_lock_v2(proposed_bias, market_mode, bb_state, bb_extreme, data, buy_score, sell_score):
    """
    V21 Soft Direction Lock V2.

    Output states:
    - TREND_LOCK: trend remains active. Only same-direction trades are allowed.
    - TRANSITION_WAIT: trend is weakening. Stop adding trades until clarity returns.
    - REVERSAL_ALLOW: opposite direction is allowed because reversal confirmation exists.
    - UNLOCKED: no active directional lock.
    """
    if not SOFT_DIRECTION_LOCK_ENABLED:
        return {
            "soft_lock_state": "DISABLED",
            "soft_lock_direction": "NONE",
            "soft_lock_allowed": True,
            "soft_lock_reason": "Soft Direction Lock disabled",
        }

    bid = safe_float(data.get("bid", 0))
    ma50 = safe_float(data.get("ma50", 0))
    ma90 = safe_float(data.get("ma90", 0))
    ma200 = safe_float(data.get("ma200", 0))
    rsi = safe_float(data.get("rsi", 50))
    macd_hist = safe_float(data.get("macd_hist", 0))
    bb_middle = safe_float(data.get("bb_middle", 0))

    locked_direction, context_reason = infer_soft_trend_direction(
        market_mode, bb_state, bid, ma50, ma90, ma200, buy_score, sell_score
    )

    if not locked_direction:
        return {
            "soft_lock_state": "UNLOCKED",
            "soft_lock_direction": "NONE",
            "soft_lock_allowed": True,
            "soft_lock_reason": context_reason,
        }

    reversal_ok = is_soft_reversal_confirmed(
        locked_direction, bb_state, bb_extreme, rsi, macd_hist, buy_score, sell_score, bid, bb_middle
    )

    # Opposite direction may trade only after confirmed reversal.
    if proposed_bias and proposed_bias != locked_direction:
        if reversal_ok:
            return {
                "soft_lock_state": "REVERSAL_ALLOW",
                "soft_lock_direction": locked_direction,
                "soft_lock_allowed": True,
                "soft_lock_reason": f"Reversal confirmed against {locked_direction}: bb={bb_state} ext={bb_extreme} RSI={rsi:.2f} MACDHist={macd_hist:.2f}",
            }
        return {
            "soft_lock_state": "TREND_LOCK",
            "soft_lock_direction": locked_direction,
            "soft_lock_allowed": False,
            "soft_lock_reason": f"Trend locked {locked_direction}; opposite {proposed_bias} not confirmed",
        }

    raw_weakening = is_soft_trend_weakening(locked_direction, bb_state, rsi, macd_hist, buy_score, sell_score)
    bar_time = str(data.get("bar_time", data.get("time", "")))
    weakening, decay_info = apply_transition_decay(
        locked_direction, market_mode, bb_state, rsi, macd_hist, buy_score, sell_score, raw_weakening, bar_time, data
    )

    if weakening:
        return {
            "soft_lock_state": "TRANSITION_WAIT",
            "soft_lock_direction": locked_direction,
            "soft_lock_allowed": False,
            "soft_lock_reason": f"{locked_direction} trend weakening; stop adding trades RSI={rsi:.2f} MACDHist={macd_hist:.2f} score={buy_score}:{sell_score} bb={bb_state} | {decay_info.get('transition_decay_reason','')}",
            **decay_info,
        }

    reason_suffix = decay_info.get("transition_decay_reason", "")
    return {
        "soft_lock_state": "TREND_LOCK",
        "soft_lock_direction": locked_direction,
        "soft_lock_allowed": True,
        "soft_lock_reason": f"Trend locked {locked_direction}; same-direction trade allowed | {context_reason} | {reason_suffix}",
        **decay_info,
    }


def attach_soft_lock_fields(decision, soft_lock):
    if isinstance(decision, dict) and isinstance(soft_lock, dict):
        decision.update(soft_lock)
    return decision



def get_recent_break_levels(data, bid):
    """
    V21.2 helper for SPIKE continuation.
    Prefer explicit recent_high/recent_low from Writer. Fallback to high1/low1.
    If neither exists, return bid as a neutral level, which prevents false breakout approval.
    """
    recent_high = safe_float(
        data.get("recent_high", data.get("high1", data.get("high", 0))), 0
    )
    recent_low = safe_float(
        data.get("recent_low", data.get("low1", data.get("low", 0))), 0
    )
    if recent_high <= 0:
        recent_high = bid
    if recent_low <= 0:
        recent_low = bid
    return recent_high, recent_low


def is_spike_bb_overextended(bb_upper, bb_lower, bb4_upper, bb4_lower):
    """Block only extreme BB expansion in SPIKE mode."""
    bb2_width = bb_upper - bb_lower if bb_upper > 0 and bb_lower > 0 else 0
    bb4_width = bb4_upper - bb4_lower if bb4_upper > 0 and bb4_lower > 0 else 0

    if bb2_width > SPIKE_BB2_WIDTH_MAX:
        return True, f"bb2_width={bb2_width:.2f}>{SPIKE_BB2_WIDTH_MAX:.2f}"
    if bb4_width > SPIKE_BB4_WIDTH_MAX:
        return True, f"bb4_width={bb4_width:.2f}>{SPIKE_BB4_WIDTH_MAX:.2f}"
    return False, ""


def has_extreme_wick_without_followthrough(data, bias, bid, rsi, macd_hist):
    """
    Optional wick filter. Uses high1/low1/close1/open1 when available.
    If OHLC data is missing, do not block by wick. MACD follow-through gate still applies.
    """
    high1 = safe_float(data.get("high1", 0), 0)
    low1 = safe_float(data.get("low1", 0), 0)
    close1 = safe_float(data.get("close1", bid), bid)
    open1 = safe_float(data.get("open1", 0), 0)

    if high1 <= 0 or low1 <= 0 or high1 <= low1:
        return False, ""

    candle_range = high1 - low1
    body = abs(close1 - open1) if open1 > 0 else 0
    upper_wick = high1 - max(open1 if open1 > 0 else close1, close1)
    lower_wick = min(open1 if open1 > 0 else close1, close1) - low1

    # Long wick with weak body/follow-through = fake spike risk.
    if bias == "BUY" and upper_wick >= candle_range * 0.55 and body <= candle_range * 0.35 and macd_hist < SPIKE_CONT_BUY_MACD_MIN:
        return True, f"upper_wick={upper_wick:.2f} range={candle_range:.2f} weak follow-through"
    if bias == "SELL" and lower_wick >= candle_range * 0.55 and body <= candle_range * 0.35 and macd_hist > SPIKE_CONT_SELL_MACD_MAX:
        return True, f"lower_wick={lower_wick:.2f} range={candle_range:.2f} weak follow-through"
    return False, ""


def spike_continuation_signal(data, bias, bid, rsi, macd_hist, buy_score, sell_score):
    """
    V21.2 SPIKE continuation entry filter.
    Allows only strong breakouts after spike. Does not force SPIKE trades.
    """
    if not SPIKE_CONTINUATION_ENABLED:
        return False, "disabled"

    recent_high, recent_low = get_recent_break_levels(data, bid)

    if bias == "BUY":
        ok = (
            buy_score >= SPIKE_CONT_BUY_MIN_SCORE
            and rsi >= SPIKE_CONT_BUY_RSI_MIN
            and macd_hist > SPIKE_CONT_BUY_MACD_MIN
            and bid > recent_high
        )
        if ok:
            return True, f"SPIKE CONTINUATION BUY | break {bid:.3f}>{recent_high:.3f} score={buy_score} RSI={rsi:.2f} MACDHist={macd_hist:.2f}"
        return False, f"BUY spike continuation not confirmed | high={recent_high:.3f}"

    if bias == "SELL":
        ok = (
            sell_score >= SPIKE_CONT_SELL_MIN_SCORE
            and rsi <= SPIKE_CONT_SELL_RSI_MAX
            and macd_hist < SPIKE_CONT_SELL_MACD_MAX
            and bid < recent_low
        )
        if ok:
            return True, f"SPIKE CONTINUATION SELL | break {bid:.3f}<{recent_low:.3f} score={sell_score} RSI={rsi:.2f} MACDHist={macd_hist:.2f}"
        return False, f"SELL spike continuation not confirmed | low={recent_low:.3f}"

    return False, "neutral bias"


def is_learning_high_risk(learn_adjust, learn_stats, learn_note):
    """
    V23_3 helper.
    Treat learning as explicitly high risk only when learning has enough data
    and tells the gate to be stricter. Insufficient/neutral learning does not block.
    """
    trades = safe_int((learn_stats or {}).get("trades", 0), 0)
    if trades >= LEARNING_MIN_TRADES and learn_adjust > 0:
        return True
    if "HIGH_RISK" in str(learn_note).upper():
        return True
    return False


def trend_walk_override_signal(
    bias, market_mode, bb_state, bid, bb_upper, bb_middle, bb_lower,
    rsi, macd_hist, buy_score, sell_score, learn_adjust, learn_stats, learn_note
):
    """
    V23_3 TREND WALK Override.
    In TREND + BB WALK, strong momentum continuation may bypass adaptive score gap.
    This prevents undertrading where score_gap is only 1 but RSI/MACD and BB WALK confirm trend.
    """
    if not TREND_WALK_OVERRIDE_ENABLED:
        return False, "TREND WALK OVERRIDE disabled", ""

    if market_mode != "TREND":
        return False, "not TREND mode", ""

    if is_learning_high_risk(learn_adjust, learn_stats, learn_note):
        return False, f"learning explicitly high risk | {learn_note}", ""

    # BB walk should be edge expansion, not BB middle. Keep this safety check.
    if is_near_bb_middle(bid, bb_upper, bb_middle, bb_lower):
        return False, "price near BB middle", ""

    # WALK_DOWN continuation SELL
    if (
        bb_state == "WALK_DOWN"
        and bias == "SELL"
        and sell_score >= buy_score + TREND_WALK_SELL_MIN_EDGE
        and rsi <= TREND_WALK_SELL_RSI_MAX
        and macd_hist <= TREND_WALK_SELL_MACD_MAX
    ):
        reason = (
            f"TREND WALK_DOWN OVERRIDE SELL | score={buy_score}:{sell_score} "
            f"RSI={rsi:.2f} MACDHist={macd_hist:.2f}"
        )
        return True, reason, "SELL_CONTINUATION"

    # WALK_UP continuation BUY
    if (
        bb_state == "WALK_UP"
        and bias == "BUY"
        and buy_score >= sell_score + TREND_WALK_BUY_MIN_EDGE
        and rsi >= TREND_WALK_BUY_RSI_MIN
        and macd_hist >= TREND_WALK_BUY_MACD_MIN
    ):
        reason = (
            f"TREND WALK_UP OVERRIDE BUY | score={buy_score}:{sell_score} "
            f"RSI={rsi:.2f} MACDHist={macd_hist:.2f}"
        )
        return True, reason, "BUY_CONTINUATION"

    # Explicit block reasons for debug
    if bb_state in ("WALK_DOWN", "WALK_UP"):
        if bb_state == "WALK_DOWN":
            return False, (
                f"WALK_DOWN not strong enough | need SELL edge>={TREND_WALK_SELL_MIN_EDGE} "
                f"RSI<={TREND_WALK_SELL_RSI_MAX} MACD<={TREND_WALK_SELL_MACD_MAX}"
            ), ""
        return False, (
            f"WALK_UP not strong enough | need BUY edge>={TREND_WALK_BUY_MIN_EDGE} "
            f"RSI>={TREND_WALK_BUY_RSI_MIN} MACD>={TREND_WALK_BUY_MACD_MIN}"
        ), ""

    return False, "not BB WALK state", ""


def trend_normal_continuation_signal(
    bias, market_mode, bb_state, bid, bb_upper, bb_middle, bb_lower,
    rsi, macd_hist, buy_score, sell_score, soft_lock_state, soft_lock_direction,
    learn_adjust, learn_stats, learn_note
):
    """
    V23_3 TREND NORMAL Continuation Override.

    This is for cases like:
      MODE=TREND, BB=NORMAL, SELL=3 BUY=2, RSI<=42, MACDHist<=-1.0, SOFT=TREND_LOCK SELL

    It bypasses adaptive score gap only when trend direction and momentum agree.
    It does not loosen RANGE/SPIKE/TRANSITION.
    """
    if not TREND_NORMAL_CONTINUATION_ENABLED:
        return False, "TREND NORMAL continuation disabled", ""

    if market_mode != "TREND" or bb_state != "NORMAL":
        return False, "not TREND+NORMAL", ""

    if is_learning_high_risk(learn_adjust, learn_stats, learn_note):
        return False, f"learning explicitly high risk | {learn_note}", ""

    # Keep BB middle safety. Trend continuation is allowed when price already moved away from middle.
    if is_near_bb_middle(bid, bb_upper, bb_middle, bb_lower):
        return False, "price near BB middle", ""

    # Prefer Soft Direction Lock confirmation when available.
    soft_state = str(soft_lock_state or "").upper()
    soft_dir = str(soft_lock_direction or "").upper()

    if bias == "SELL":
        soft_ok = (soft_state in ("TREND_LOCK", "UNLOCKED", "") and soft_dir in ("SELL", "NONE", ""))
        if (
            soft_ok
            and sell_score >= buy_score + TREND_NORMAL_SELL_MIN_EDGE
            and rsi <= TREND_NORMAL_SELL_RSI_MAX
            and macd_hist <= TREND_NORMAL_SELL_MACD_MAX
        ):
            reason = (
                f"TREND NORMAL CONTINUATION SELL | score={buy_score}:{sell_score} "
                f"RSI={rsi:.2f} MACDHist={macd_hist:.2f} soft={soft_state}/{soft_dir}"
            )
            return True, reason, "SELL_CONTINUATION"

    if bias == "BUY":
        soft_ok = (soft_state in ("TREND_LOCK", "UNLOCKED", "") and soft_dir in ("BUY", "NONE", ""))
        if (
            soft_ok
            and buy_score >= sell_score + TREND_NORMAL_BUY_MIN_EDGE
            and rsi >= TREND_NORMAL_BUY_RSI_MIN
            and macd_hist >= TREND_NORMAL_BUY_MACD_MIN
        ):
            reason = (
                f"TREND NORMAL CONTINUATION BUY | score={buy_score}:{sell_score} "
                f"RSI={rsi:.2f} MACDHist={macd_hist:.2f} soft={soft_state}/{soft_dir}"
            )
            return True, reason, "BUY_CONTINUATION"

    if bias == "SELL":
        return False, (
            f"TREND NORMAL SELL not strong enough | need SELL edge>={TREND_NORMAL_SELL_MIN_EDGE} "
            f"RSI<={TREND_NORMAL_SELL_RSI_MAX} MACD<={TREND_NORMAL_SELL_MACD_MAX}"
        ), ""
    if bias == "BUY":
        return False, (
            f"TREND NORMAL BUY not strong enough | need BUY edge>={TREND_NORMAL_BUY_MIN_EDGE} "
            f"RSI>={TREND_NORMAL_BUY_RSI_MIN} MACD>={TREND_NORMAL_BUY_MACD_MIN}"
        ), ""

    return False, "neutral bias", ""


def _extract_candle_series(data, name_variants):
    for name in name_variants:
        value = data.get(name)
        if isinstance(value, list) and value:
            return [safe_float(v, 0.0) for v in value if safe_float(v, 0.0) != 0.0]
    result = []
    for i in range(1, 11):
        for base in name_variants:
            key = f"{base}{i}"
            if key in data:
                val = safe_float(data.get(key), 0.0)
                if val != 0.0:
                    result.append(val)
                break
    return result


def get_candle_data(data, lookback=CANDLE_LOOKBACK_DEFAULT):
    opens = _extract_candle_series(data, ["opens", "open"])
    highs = _extract_candle_series(data, ["highs", "high"])
    lows = _extract_candle_series(data, ["lows", "low"])
    closes = _extract_candle_series(data, ["closes", "close"])

    if not closes and data.get("close1") is not None:
        close1 = safe_float(data.get("close1"), 0)
        opens = [safe_float(data.get("open1", close1), close1)]
        highs = [safe_float(data.get("high1", close1), close1)]
        lows = [safe_float(data.get("low1", close1), close1)]
        closes = [close1]

    n = min(len(opens), len(highs), len(lows), len(closes), lookback)
    return opens[:n], highs[:n], lows[:n], closes[:n]


def classify_candle_trend(closes):
    if len(closes) < 3:
        return "UNKNOWN", 0
    newest = closes[0]
    oldest = closes[-1]
    up_count = sum(1 for i in range(len(closes)-1) if closes[i] > closes[i+1])
    down_count = sum(1 for i in range(len(closes)-1) if closes[i] < closes[i+1])
    net = newest - oldest
    if up_count >= max(3, int((len(closes)-1) * 0.6)) and net > 0:
        return "UP", up_count
    if down_count >= max(3, int((len(closes)-1) * 0.6)) and net < 0:
        return "DOWN", down_count
    return "SIDEWAYS", max(up_count, down_count)


def classify_structure_trend(highs, lows):
    if len(highs) < 4 or len(lows) < 4:
        return "UNKNOWN"
    hh = sum(1 for i in range(len(highs)-1) if highs[i] > highs[i+1])
    hl = sum(1 for i in range(len(lows)-1) if lows[i] > lows[i+1])
    lh = sum(1 for i in range(len(highs)-1) if highs[i] < highs[i+1])
    ll = sum(1 for i in range(len(lows)-1) if lows[i] < lows[i+1])
    needed = max(2, int((len(highs)-1) * 0.55))
    if hh >= needed and hl >= needed:
        return "HH_HL"
    if lh >= needed and ll >= needed:
        return "LH_LL"
    if hh >= needed and ll >= needed:
        return "EXPANDING"
    return "MIXED"


def classify_momentum_shape(opens, highs, lows, closes):
    if len(closes) < 2:
        return "UNKNOWN", 0
    body_scores = []
    direction_scores = []
    for o, h, l, c in zip(opens, highs, lows, closes):
        rng = max(h - l, 0.00001)
        body = abs(c - o)
        body_scores.append(body / rng)
        direction_scores.append(1 if c > o else -1 if c < o else 0)
    avg_body = sum(body_scores) / max(1, len(body_scores))
    last3 = direction_scores[:3]
    bull = sum(1 for x in last3 if x > 0)
    bear = sum(1 for x in last3 if x < 0)
    if avg_body >= CANDLE_BODY_MOMENTUM_RATIO and bull >= 2:
        return "EXPANDING_BULL", int(avg_body * 100)
    if avg_body >= CANDLE_BODY_MOMENTUM_RATIO and bear >= 2:
        return "EXPANDING_BEAR", int(avg_body * 100)
    if avg_body <= 0.28:
        return "FADING", int(avg_body * 100)
    return "NORMAL", int(avg_body * 100)


def detect_wick_rejection(opens, highs, lows, closes):
    if not closes:
        return "NONE", 0
    o, h, l, c = opens[0], highs[0], lows[0], closes[0]
    rng = max(h - l, 0.00001)
    body = abs(c - o)
    upper = h - max(o, c)
    lower = min(o, c) - l
    upper_ratio = upper / rng
    lower_ratio = lower / rng
    body_ratio = body / rng
    if upper_ratio >= CANDLE_WICK_REJECTION_RATIO and body_ratio <= CANDLE_SMALL_BODY_RATIO:
        return "UPPER_REJECTION", int(upper_ratio * 100)
    if lower_ratio >= CANDLE_WICK_REJECTION_RATIO and body_ratio <= CANDLE_SMALL_BODY_RATIO:
        return "LOWER_REJECTION", int(lower_ratio * 100)
    return "NONE", int(max(upper_ratio, lower_ratio) * 100)


def compute_exhaustion_risk(bias, candle_trend, structure_trend, momentum_shape, wick_rejection, rsi, bb_state, bb_extreme):
    risk = 0
    if bias == "BUY":
        if wick_rejection == "UPPER_REJECTION":
            risk += 35
        if rsi >= 72:
            risk += 20
        if bb_extreme == "DEV4_UPPER":
            risk += 35
        if momentum_shape == "FADING":
            risk += 15
        if candle_trend == "DOWN" or structure_trend == "LH_LL":
            risk += 20
    elif bias == "SELL":
        if wick_rejection == "LOWER_REJECTION":
            risk += 35
        if rsi <= 28:
            risk += 20
        if bb_extreme == "DEV4_LOWER":
            risk += 35
        if momentum_shape == "FADING":
            risk += 15
        if candle_trend == "UP" or structure_trend == "HH_HL":
            risk += 20
    if bb_state == "COMPRESSION":
        risk += 15
    return clamp_int(risk, 0, 100)


def compute_trend_quality(bias, candle_trend, structure_trend, momentum_shape, wick_rejection, trend_count, momentum_score, exhaustion_risk):
    quality = 0
    if bias == "BUY":
        if candle_trend == "UP":
            quality += 25
        if structure_trend == "HH_HL":
            quality += 25
        if momentum_shape == "EXPANDING_BULL":
            quality += 20
        if wick_rejection == "LOWER_REJECTION":
            quality += 10
        if wick_rejection == "UPPER_REJECTION":
            quality -= 25
    elif bias == "SELL":
        if candle_trend == "DOWN":
            quality += 25
        if structure_trend == "LH_LL":
            quality += 25
        if momentum_shape == "EXPANDING_BEAR":
            quality += 20
        if wick_rejection == "UPPER_REJECTION":
            quality += 10
        if wick_rejection == "LOWER_REJECTION":
            quality -= 25
    quality += min(15, trend_count * 3)
    quality += min(15, int(momentum_score / 5))
    quality -= int(exhaustion_risk * 0.35)
    return clamp_int(quality, 0, 100)


def candle_intelligence_layer(data, decision, market_mode, bb_state, bb_extreme, buy_score, sell_score):
    if not CANDLE_INTELLIGENCE_ENABLED:
        return True, "CANDLE INTELLIGENCE disabled", {
            "candle_trend": "DISABLED", "structure_trend": "DISABLED",
            "momentum_shape": "DISABLED", "wick_rejection": "NONE",
            "exhaustion_risk": 0, "trend_quality": 0, "candle_count": 0
        }

    bias = str(decision.get("bias", "NEUTRAL")).upper()
    rsi = safe_float(data.get("rsi", decision.get("rsi", 50)), 50)

    opens, highs, lows, closes = get_candle_data(data)
    candle_trend, trend_count = classify_candle_trend(closes)
    structure_trend = classify_structure_trend(highs, lows)
    momentum_shape, momentum_score = classify_momentum_shape(opens, highs, lows, closes)
    wick_rejection, wick_score = detect_wick_rejection(opens, highs, lows, closes)
    exhaustion_risk = compute_exhaustion_risk(bias, candle_trend, structure_trend, momentum_shape, wick_rejection, rsi, bb_state, bb_extreme)
    trend_quality = compute_trend_quality(bias, candle_trend, structure_trend, momentum_shape, wick_rejection, trend_count, momentum_score, exhaustion_risk)

    info = {
        "candle_trend": candle_trend,
        "structure_trend": structure_trend,
        "momentum_shape": momentum_shape,
        "wick_rejection": wick_rejection,
        "exhaustion_risk": exhaustion_risk,
        "trend_quality": trend_quality,
        "candle_count": len(closes),
    }

    if len(closes) < 4:
        return True, "CANDLE INTELLIGENCE report only | insufficient candle history", info
    if decision.get("decision") != "TRADE":
        return True, "CANDLE INTELLIGENCE report only | not trade", info

    if market_mode == "TREND" and exhaustion_risk >= CANDLE_EXHAUSTION_BLOCK_LEVEL:
        return False, f"CANDLE BLOCK | exhaustion risk {exhaustion_risk} quality={trend_quality}", info
    if market_mode == "TREND" and trend_quality < CANDLE_LATE_CONTINUATION_BLOCK_QUALITY:
        return False, f"CANDLE BLOCK | weak candle trend_quality={trend_quality}", info
    if bias == "BUY" and candle_trend == "DOWN" and structure_trend == "LH_LL":
        return False, "CANDLE BLOCK BUY | candle trend/structure bearish", info
    if bias == "SELL" and candle_trend == "UP" and structure_trend == "HH_HL":
        return False, "CANDLE BLOCK SELL | candle trend/structure bullish", info

    return True, f"CANDLE APPROVED | quality={trend_quality} exhaustion={exhaustion_risk}", info


def apply_candle_intelligence_or_block(decision, data, market_mode, bb_state, bb_extreme, buy_score, sell_score):
    ok, reason, info = candle_intelligence_layer(data, decision, market_mode, bb_state, bb_extreme, buy_score, sell_score)
    if isinstance(decision, dict):
        decision.update(info)
        decision["candle_filter"] = "APPROVED" if ok else "BLOCKED"
        decision["candle_reason"] = reason

    if ok:
        if decision.get("decision") == "TRADE":
            decision["reason"] = f"{decision.get('reason', '')} | {reason}"
        return decision

    blocked = no_trade(reason, market_mode, bb_state)
    for key in (
        "buy_score", "sell_score", "buyScore", "sellScore", "score_gap", "dir_m15", "dir_m3",
        "rsi", "macd_hist", "bb_mid", "bb_upper2", "bb_lower2",
        "analysis_quality", "adaptive_gap", "learning_enabled", "learning_key",
        "learning_gap_adjust", "learning_note", "learning_stats", "bb_extreme",
        "dual_mode", "aggressive_mode", "dual_mode_reason", "trend_priority", "trend_priority_reason",
        "soft_lock_state", "soft_lock_direction", "soft_lock_allowed", "soft_lock_reason",
            "transition_decay_count", "transition_decay_required", "transition_decay_active", "transition_decay_reason",
            "soft_lock_counter_reset", "soft_lock_counter_reset_reason",
            "fresh_state_reset", "fresh_state_reset_reason", "market_state_fresh", "market_state_signature",
        "trend_walk_mode", "trend_walk_reason", "trend_walk_override",
        "trend_normal_mode", "trend_normal_reason", "trend_normal_override",
        "cooldown_override", "cooldown_override_reason",
        "trend_momentum_mode", "trend_momentum_reason", "trend_momentum_override",
        "candle_trend", "structure_trend", "momentum_shape", "wick_rejection",
        "exhaustion_risk", "trend_quality", "candle_count", "candle_filter", "candle_reason"
    ):
        if key in decision:
            blocked[key] = decision[key]
    blocked["entry_allowed"] = False
    return blocked


def trend_normal_momentum_override_signal(
    bias, market_mode, bb_state, bid, bb_upper, bb_middle, bb_lower,
    rsi, macd_hist, buy_score, sell_score, soft_lock_state, soft_lock_direction,
    learn_adjust, learn_stats, learn_note
):
    """
    V23_3 TREND NORMAL Momentum Override.

    Example allowed:
    MODE=TREND, BB=NORMAL, SELL=3 BUY=2, RSI=42.01, MACDHist=-2.05, SOFT=TREND_LOCK/SELL.
    This bypasses adaptive score gap only for strong trend continuation, not RANGE/SPIKE.
    """
    if not TREND_NORMAL_MOMENTUM_OVERRIDE_ENABLED:
        return False, "TREND NORMAL MOMENTUM disabled", ""

    if market_mode != "TREND" or bb_state != "NORMAL":
        return False, "not TREND+NORMAL", ""

    if is_learning_high_risk(learn_adjust, learn_stats, learn_note):
        return False, f"learning explicitly high risk | {learn_note}", ""

    soft_state = str(soft_lock_state or "").upper()
    soft_dir = str(soft_lock_direction or "").upper()
    near_middle = is_near_bb_middle(bid, bb_upper, bb_middle, bb_lower)

    if near_middle and not TREND_NORMAL_MOMENTUM_ALLOW_MIDDLE_IF_MACD_STRONG:
        return False, "price near BB middle"

    if bias == "SELL":
        soft_ok = soft_state in ("TREND_LOCK", "UNLOCKED", "") and soft_dir in ("SELL", "NONE", "")
        if (
            soft_ok
            and sell_score >= buy_score + TREND_NORMAL_MOMENTUM_MIN_EDGE
            and rsi <= TREND_NORMAL_MOMENTUM_SELL_RSI_MAX
            and macd_hist <= TREND_NORMAL_MOMENTUM_SELL_MACD_MAX
        ):
            reason = (
                f"TREND NORMAL MOMENTUM SELL | score={buy_score}:{sell_score} "
                f"RSI={rsi:.2f} MACDHist={macd_hist:.2f} soft={soft_state}/{soft_dir}"
            )
            return True, reason, "SELL_CONTINUATION"

    if bias == "BUY":
        soft_ok = soft_state in ("TREND_LOCK", "UNLOCKED", "") and soft_dir in ("BUY", "NONE", "")
        if (
            soft_ok
            and buy_score >= sell_score + TREND_NORMAL_MOMENTUM_MIN_EDGE
            and rsi >= TREND_NORMAL_MOMENTUM_BUY_RSI_MIN
            and macd_hist >= TREND_NORMAL_MOMENTUM_BUY_MACD_MIN
        ):
            reason = (
                f"TREND NORMAL MOMENTUM BUY | score={buy_score}:{sell_score} "
                f"RSI={rsi:.2f} MACDHist={macd_hist:.2f} soft={soft_state}/{soft_dir}"
            )
            return True, reason, "BUY_CONTINUATION"

    return False, "TREND NORMAL MOMENTUM not confirmed", ""


def trend_exhaustion_detection(data, decision, market_mode, bb_state, bb_extreme):
    """
    V23_3 Trend Exhaustion Detection.
    Detects late-continuation risk when trend is visible but may be exhausted.
    """
    if not TREND_EXHAUSTION_ENABLED:
        return {
            "trend_exhaustion": "DISABLED",
            "trend_exhaustion_score": 0,
            "trend_exhaustion_reason": "disabled",
            "late_continuation_risk": False,
        }

    if not isinstance(decision, dict):
        return {
            "trend_exhaustion": "UNKNOWN",
            "trend_exhaustion_score": 0,
            "trend_exhaustion_reason": "invalid decision",
            "late_continuation_risk": False,
        }

    bias = str(decision.get("bias", "NEUTRAL")).upper()
    rsi = safe_float(data.get("rsi", decision.get("rsi", 50)), 50)
    macd_hist = safe_float(data.get("macd_hist", decision.get("macd_hist", 0)), 0)
    wick_rejection = str(decision.get("wick_rejection", "NONE")).upper()
    momentum_shape = str(decision.get("momentum_shape", "UNKNOWN")).upper()
    candle_trend = str(decision.get("candle_trend", "UNKNOWN")).upper()
    structure_trend = str(decision.get("structure_trend", "UNKNOWN")).upper()
    soft_state = str(decision.get("soft_lock_state", "")).upper()
    transition_decay_active = bool(decision.get("transition_decay_active", False))

    score = 0
    reasons = []

    if market_mode != "TREND":
        return {
            "trend_exhaustion": "LOW",
            "trend_exhaustion_score": 0,
            "trend_exhaustion_reason": "not trend mode",
            "late_continuation_risk": False,
        }

    if bias == "BUY":
        if bb_extreme == "DEV4_UPPER":
            score += TREND_EXHAUSTION_DEV4_WEIGHT
            reasons.append("DEV4_UPPER")
        if wick_rejection == "UPPER_REJECTION":
            score += TREND_EXHAUSTION_WICK_WEIGHT
            reasons.append("upper wick rejection")
        if rsi >= TREND_EXHAUSTION_RSI_BUY_HIGH:
            score += TREND_EXHAUSTION_RSI_WEIGHT
            reasons.append(f"RSI high {rsi:.2f}")
        if 0 <= macd_hist <= TREND_EXHAUSTION_MACD_FADE_ABS:
            score += TREND_EXHAUSTION_MACD_FADE_WEIGHT
            reasons.append(f"MACD fading {macd_hist:.2f}")
        if momentum_shape == "FADING":
            score += TREND_EXHAUSTION_CANDLE_FADE_WEIGHT
            reasons.append("candle momentum fading")
        if candle_trend == "DOWN" or structure_trend == "LH_LL":
            score += TREND_EXHAUSTION_CANDLE_FADE_WEIGHT
            reasons.append("candle/structure against BUY")

    elif bias == "SELL":
        if bb_extreme == "DEV4_LOWER":
            score += TREND_EXHAUSTION_DEV4_WEIGHT
            reasons.append("DEV4_LOWER")
        if wick_rejection == "LOWER_REJECTION":
            score += TREND_EXHAUSTION_WICK_WEIGHT
            reasons.append("lower wick rejection")
        if rsi <= TREND_EXHAUSTION_RSI_SELL_LOW:
            score += TREND_EXHAUSTION_RSI_WEIGHT
            reasons.append(f"RSI low {rsi:.2f}")
        if -TREND_EXHAUSTION_MACD_FADE_ABS <= macd_hist <= 0:
            score += TREND_EXHAUSTION_MACD_FADE_WEIGHT
            reasons.append(f"MACD fading {macd_hist:.2f}")
        if momentum_shape == "FADING":
            score += TREND_EXHAUSTION_CANDLE_FADE_WEIGHT
            reasons.append("candle momentum fading")
        if candle_trend == "UP" or structure_trend == "HH_HL":
            score += TREND_EXHAUSTION_CANDLE_FADE_WEIGHT
            reasons.append("candle/structure against SELL")

    if soft_state == "TRANSITION_WAIT" or transition_decay_active:
        score += TREND_EXHAUSTION_TRANSITION_WEIGHT
        reasons.append("soft transition/decay active")

    score = clamp_int(score, 0, 100)
    if score >= TREND_EXHAUSTION_BLOCK_LEVEL:
        level = "HIGH"
    elif score >= TREND_EXHAUSTION_WARN_LEVEL:
        level = "MEDIUM"
    else:
        level = "LOW"

    return {
        "trend_exhaustion": level,
        "trend_exhaustion_score": score,
        "trend_exhaustion_reason": "; ".join(reasons) if reasons else "no exhaustion",
        "late_continuation_risk": score >= TREND_EXHAUSTION_WARN_LEVEL,
    }


def apply_trend_exhaustion_or_block(decision, data, market_mode, bb_state, bb_extreme):
    """
    Applies Trend Exhaustion Detection after Candle Intelligence.
    Blocks only high-risk late continuation trades.
    """
    info = trend_exhaustion_detection(data, decision, market_mode, bb_state, bb_extreme)
    if isinstance(decision, dict):
        decision.update(info)

    if not isinstance(decision, dict) or decision.get("decision") != "TRADE":
        return decision

    if info.get("trend_exhaustion_score", 0) >= TREND_EXHAUSTION_BLOCK_LEVEL:
        reason = (
            f"TREND EXHAUSTION BLOCK | score={info.get('trend_exhaustion_score')} "
            f"level={info.get('trend_exhaustion')} | {info.get('trend_exhaustion_reason')}"
        )
        blocked = no_trade(reason, market_mode, bb_state)
        for key in (
            "buy_score", "sell_score", "buyScore", "sellScore", "score_gap",
            "rsi", "macd_hist", "bb_mid", "bb_upper2", "bb_lower2",
            "soft_lock_state", "soft_lock_direction", "soft_lock_allowed", "soft_lock_reason",
            "transition_decay_count", "transition_decay_required", "transition_decay_active", "transition_decay_reason",
            "soft_lock_counter_reset", "soft_lock_counter_reset_reason",
            "fresh_state_reset", "fresh_state_reset_reason", "market_state_fresh", "market_state_signature",
            "candle_trend", "structure_trend", "momentum_shape", "wick_rejection",
            "exhaustion_risk", "trend_quality", "candle_filter", "candle_reason",
            "trend_exhaustion", "trend_exhaustion_score", "trend_exhaustion_reason", "late_continuation_risk",
            "trend_walk_mode", "trend_walk_reason", "trend_walk_override",
            "trend_normal_mode", "trend_normal_reason", "trend_normal_override",
            "trend_momentum_mode", "trend_momentum_reason", "trend_momentum_override",
        ):
            if key in decision:
                blocked[key] = decision[key]
        blocked["entry_allowed"] = False
        return blocked

    if decision.get("decision") == "TRADE":
        decision["reason"] = (
            f"{decision.get('reason', '')} | TREND EXHAUSTION CHECK "
            f"{info.get('trend_exhaustion')} score={info.get('trend_exhaustion_score')}"
        )
    return decision


def _series_from_data_for_ms(data, names, lookback=MS_LOOKBACK_DEFAULT):
    for name in names:
        value = data.get(name)
        if isinstance(value, list) and value:
            return [safe_float(v, 0.0) for v in value[:lookback] if safe_float(v, 0.0) != 0.0]
    result = []
    for i in range(1, lookback + 1):
        for base in names:
            key = f"{base}{i}"
            if key in data:
                val = safe_float(data.get(key), 0.0)
                if val != 0.0:
                    result.append(val)
                break
    return result


def get_market_structure_series(data, lookback=MS_LOOKBACK_DEFAULT):
    highs = _series_from_data_for_ms(data, ["highs", "high"], lookback)
    lows = _series_from_data_for_ms(data, ["lows", "low"], lookback)
    closes = _series_from_data_for_ms(data, ["closes", "close"], lookback)
    opens = _series_from_data_for_ms(data, ["opens", "open"], lookback)
    if not opens:
        opens = closes[:]
    n = min(len(highs), len(lows), len(closes), len(opens), lookback)
    return opens[:n], highs[:n], lows[:n], closes[:n]


def detect_market_structure(highs, lows, closes):
    if len(highs) < 4 or len(lows) < 4:
        return "UNKNOWN", "INSUFFICIENT_DATA"
    hh = sum(1 for i in range(len(highs)-1) if highs[i] > highs[i+1])
    hl = sum(1 for i in range(len(lows)-1) if lows[i] > lows[i+1])
    lh = sum(1 for i in range(len(highs)-1) if highs[i] < highs[i+1])
    ll = sum(1 for i in range(len(lows)-1) if lows[i] < lows[i+1])
    needed = max(2, int((len(highs)-1) * 0.55))
    if hh >= needed and hl >= needed:
        return "HH_HL", "BULLISH_STRUCTURE"
    if lh >= needed and ll >= needed:
        return "LH_LL", "BEARISH_STRUCTURE"
    if hh >= needed and ll >= needed:
        return "EXPANDING", "VOLATILE_EXPANSION"
    return "MIXED", "MIXED_STRUCTURE"


def detect_bos_choch(bias, highs, lows, closes):
    if len(highs) < 4 or len(lows) < 4 or len(closes) < 2:
        return "NONE", "NONE"
    latest_close = closes[0]
    prev_high = max(highs[1:4])
    prev_low = min(lows[1:4])
    bos = "BOS_UP" if latest_close > prev_high else "BOS_DOWN" if latest_close < prev_low else "NONE"
    choch = "NONE"
    if bias == "BUY" and latest_close < prev_low:
        choch = "CHOCH_DOWN"
    elif bias == "SELL" and latest_close > prev_high:
        choch = "CHOCH_UP"
    return bos, choch


def detect_liquidity_sweep(bias, opens, highs, lows, closes):
    if len(highs) < 3 or len(lows) < 3 or len(closes) < 1:
        return "NONE"
    high1, low1, close1 = highs[0], lows[0], closes[0]
    prior_high = max(highs[1:4]) if len(highs) >= 4 else max(highs[1:])
    prior_low = min(lows[1:4]) if len(lows) >= 4 else min(lows[1:])
    if high1 > prior_high and close1 < prior_high:
        return "SWEEP_HIGH"
    if low1 < prior_low and close1 > prior_low:
        return "SWEEP_LOW"
    return "NONE"


def detect_distribution_accumulation(highs, lows, closes, rsi, macd_hist):
    if len(highs) < 5 or len(lows) < 5 or len(closes) < 5:
        return False, False
    recent_range = max(highs[:5]) - min(lows[:5])
    full_range = max(highs) - min(lows)
    range_compression = full_range > 0 and recent_range <= full_range * 0.45
    cmax, cmin = max(closes), min(closes)
    near_high = closes[0] >= cmin + (cmax - cmin) * 0.65 if cmax > cmin else False
    near_low = closes[0] <= cmin + (cmax - cmin) * 0.35 if cmax > cmin else False
    distribution = near_high and range_compression and (rsi < 58 or macd_hist <= 0.35)
    accumulation = near_low and range_compression and (rsi > 42 or macd_hist >= -0.35)
    return distribution, accumulation


def detect_momentum_decay(bias, highs, lows, closes, rsi, macd_hist):
    if len(highs) < 4 or len(lows) < 4 or len(closes) < 4:
        return False, "insufficient data"
    if bias == "BUY":
        makes_new_high = highs[0] >= max(highs[1:4])
        weak_momentum = rsi < 55 or macd_hist <= 0.35
        close_not_strong = closes[0] <= max(closes[1:4])
        if makes_new_high and (weak_momentum or close_not_strong):
            return True, "BUY momentum decay: new high without strong RSI/MACD/close"
    elif bias == "SELL":
        makes_new_low = lows[0] <= min(lows[1:4])
        weak_momentum = rsi > 45 or macd_hist >= -0.35
        close_not_strong = closes[0] >= min(closes[1:4])
        if makes_new_low and (weak_momentum or close_not_strong):
            return True, "SELL momentum decay: new low without strong RSI/MACD/close"
    return False, "no momentum decay"


def detect_late_entry_risk(bias, bid, bb_upper, bb_middle, bb_lower, bb_extreme, market_mode, bb_state):
    if bb_upper <= bb_lower or bb_upper <= 0 or bb_lower <= 0:
        return False, "bb unavailable"
    width = bb_upper - bb_lower
    if width <= 0:
        return False, "bb width unavailable"
    if bias == "BUY":
        if bb_extreme == "DEV4_UPPER":
            return True, "BUY late entry risk: DEV4 upper"
        if (bid - bb_middle) >= width * MS_PRICE_EXTENSION_BB_WIDTH_RATIO and bb_state in ("WALK_UP", "NORMAL"):
            return True, "BUY late entry risk: extended above BB mid"
    elif bias == "SELL":
        if bb_extreme == "DEV4_LOWER":
            return True, "SELL late entry risk: DEV4 lower"
        if (bb_middle - bid) >= width * MS_PRICE_EXTENSION_BB_WIDTH_RATIO and bb_state in ("WALK_DOWN", "NORMAL"):
            return True, "SELL late entry risk: extended below BB mid"
    return False, "not late extension"


def market_structure_exhaustion_master_gate(decision, data, market_mode, bb_state, bb_extreme):
    if not MS_EXHAUSTION_MASTER_GATE_ENABLED:
        return True, {"master_gate": "DISABLED", "master_gate_score": 0, "master_gate_reason": "disabled"}
    if not isinstance(decision, dict):
        return True, {"master_gate": "INVALID", "master_gate_score": 0, "master_gate_reason": "invalid decision"}

    bias = str(decision.get("bias", "NEUTRAL")).upper()
    rsi = safe_float(data.get("rsi", decision.get("rsi", 50)), 50)
    macd_hist = safe_float(data.get("macd_hist", decision.get("macd_hist", 0)), 0)
    bid = safe_float(data.get("bid", 0))
    bb_upper = safe_float(data.get("bb_upper", decision.get("bb_upper2", 0)), 0)
    bb_middle = safe_float(data.get("bb_middle", decision.get("bb_mid", 0)), 0)
    bb_lower = safe_float(data.get("bb_lower", decision.get("bb_lower2", 0)), 0)
    wick_rejection = str(decision.get("wick_rejection", "NONE")).upper()
    trend_exhaustion_score = safe_int(decision.get("trend_exhaustion_score", 0), 0)

    opens, highs, lows, closes = get_market_structure_series(data)
    market_structure, structure_signal = detect_market_structure(highs, lows, closes)
    bos_signal, choch_signal = detect_bos_choch(bias, highs, lows, closes)
    liquidity_sweep = detect_liquidity_sweep(bias, opens, highs, lows, closes)
    distribution_phase, accumulation_phase = detect_distribution_accumulation(highs, lows, closes, rsi, macd_hist)
    momentum_decay, momentum_decay_reason = detect_momentum_decay(bias, highs, lows, closes, rsi, macd_hist)
    late_entry_risk, late_entry_reason = detect_late_entry_risk(bias, bid, bb_upper, bb_middle, bb_lower, bb_extreme, market_mode, bb_state)

    score = 0
    reasons = []
    if bias == "BUY":
        if market_structure == "LH_LL":
            score += MS_STRUCTURE_CONFLICT_WEIGHT; reasons.append("BUY conflict: LH/LL")
        if choch_signal == "CHOCH_DOWN":
            score += MS_CHOCH_WEIGHT; reasons.append("CHOCH_DOWN against BUY")
        if liquidity_sweep == "SWEEP_HIGH":
            score += MS_LIQUIDITY_SWEEP_WEIGHT; reasons.append("sweep high")
        if distribution_phase:
            score += MS_DISTRIBUTION_WEIGHT; reasons.append("distribution phase")
        if wick_rejection == "UPPER_REJECTION":
            score += MS_WICK_REJECTION_WEIGHT; reasons.append("upper rejection")
    elif bias == "SELL":
        if market_structure == "HH_HL":
            score += MS_STRUCTURE_CONFLICT_WEIGHT; reasons.append("SELL conflict: HH/HL")
        if choch_signal == "CHOCH_UP":
            score += MS_CHOCH_WEIGHT; reasons.append("CHOCH_UP against SELL")
        if liquidity_sweep == "SWEEP_LOW":
            score += MS_LIQUIDITY_SWEEP_WEIGHT; reasons.append("sweep low")
        if accumulation_phase:
            score += MS_ACCUMULATION_WEIGHT; reasons.append("accumulation phase")
        if wick_rejection == "LOWER_REJECTION":
            score += MS_WICK_REJECTION_WEIGHT; reasons.append("lower rejection")

    if momentum_decay:
        score += MS_MOMENTUM_DECAY_WEIGHT; reasons.append(momentum_decay_reason)
    if late_entry_risk:
        score += MS_LATE_EXPANSION_WEIGHT; reasons.append(late_entry_reason)
    if trend_exhaustion_score >= TREND_EXHAUSTION_WARN_LEVEL:
        score += MS_EXHAUSTION_WEIGHT; reasons.append(f"trend exhaustion score={trend_exhaustion_score}")

    score = clamp_int(score, 0, 100)
    gate = "BLOCKED" if score >= MS_MASTER_BLOCK_SCORE else "WARNING" if score >= MS_MASTER_WARN_SCORE else "APPROVED"
    info = {
        "market_structure": market_structure,
        "structure_signal": structure_signal,
        "bos_signal": bos_signal,
        "choch_signal": choch_signal,
        "liquidity_sweep": liquidity_sweep,
        "distribution_phase": distribution_phase,
        "accumulation_phase": accumulation_phase,
        "momentum_decay": momentum_decay,
        "late_entry_risk": late_entry_risk,
        "master_gate_score": score,
        "master_gate": gate,
        "master_gate_reason": "; ".join(reasons) if reasons else "structure/exhaustion ok",
    }
    return gate != "BLOCKED", info


def apply_market_structure_exhaustion_master_gate(decision, data, market_mode, bb_state, bb_extreme):
    ok, info = market_structure_exhaustion_master_gate(decision, data, market_mode, bb_state, bb_extreme)
    if isinstance(decision, dict):
        decision.update(info)
    if not isinstance(decision, dict) or decision.get("decision") != "TRADE":
        return decision
    if not ok:
        reason = f"MASTER GATE BLOCK | score={info.get('master_gate_score')} | {info.get('master_gate_reason')}"
        blocked = no_trade(reason, market_mode, bb_state)
        for key in (
            "buy_score", "sell_score", "buyScore", "sellScore", "score_gap",
            "rsi", "macd_hist", "bb_mid", "bb_upper2", "bb_lower2",
            "soft_lock_state", "soft_lock_direction", "soft_lock_allowed", "soft_lock_reason",
            "transition_decay_count", "transition_decay_required", "transition_decay_active", "transition_decay_reason",
            "soft_lock_counter_reset", "soft_lock_counter_reset_reason",
            "fresh_state_reset", "fresh_state_reset_reason", "market_state_fresh", "market_state_signature",
            "candle_trend", "structure_trend", "momentum_shape", "wick_rejection",
            "exhaustion_risk", "trend_quality", "candle_filter", "candle_reason",
            "trend_exhaustion", "trend_exhaustion_score", "trend_exhaustion_reason", "late_continuation_risk",
            "market_structure", "structure_signal", "bos_signal", "choch_signal", "liquidity_sweep",
            "distribution_phase", "accumulation_phase", "momentum_decay",
            "master_gate_score", "master_gate", "master_gate_reason",
            "trend_walk_mode", "trend_walk_reason", "trend_walk_override",
            "trend_normal_mode", "trend_normal_reason", "trend_normal_override",
            "trend_momentum_mode", "trend_momentum_reason", "trend_momentum_override",
        ):
            if key in decision:
                blocked[key] = decision[key]
        blocked["entry_allowed"] = False
        return blocked

    if decision.get("decision") == "TRADE":
        decision["reason"] = f"{decision.get('reason', '')} | MASTER GATE {info.get('master_gate')} score={info.get('master_gate_score')}"
    return decision

def determine_dual_mode(bias, market_mode, bb_state, bb_extreme, score_gap, rsi, macd_hist):
    """
    V19.8 Dual Mode Auto Switch.

    SAFE mode:
    - DEV4 extremes
    - BB compression
    - spike exhaustion
    - weak/no edge

    AGGRESSIVE mode:
    - clean TRANSITION/RANGE/NORMAL conditions
    - score_gap >= 2
    - RSI/MACD not strongly opposite

    This only changes entry gate strictness. It does not change EA order fields.
    """
    if not DUAL_MODE_ENABLED:
        return "SAFE", "dual mode disabled"

    if bb_extreme in ("DEV4_UPPER", "DEV4_LOWER"):
        return "SAFE", f"safe: bb_extreme={bb_extreme}"
    if bb_state == "COMPRESSION":
        return "SAFE", "safe: compression wait breakout"
    if score_gap <= 0:
        return "SAFE", "safe: no score edge"
    if market_mode == "SPIKE":
        if rsi <= DUAL_SAFE_SPIKE_RSI_LOW or rsi >= DUAL_SAFE_SPIKE_RSI_HIGH:
            return "SAFE", f"safe: spike exhaustion RSI={rsi:.2f}"

    if market_mode in ("TRANSITION", "RANGE") and bb_state in ("NORMAL", "REVERSAL_UP", "REVERSAL_DOWN"):
        if score_gap >= DUAL_AGGRESSIVE_MIN_GAP and dual_direction_confirm(bias, rsi, macd_hist):
            return "AGGRESSIVE", f"aggressive: {market_mode}+{bb_state} gap={score_gap} RSI={rsi:.2f} MACDHist={macd_hist:.2f}"

    if market_mode == "TREND" and score_gap >= 3 and bb_state == "NORMAL" and dual_direction_confirm(bias, rsi, macd_hist):
        return "AGGRESSIVE", f"aggressive: trend normal continuation gap={score_gap}"

    return "SAFE", "safe: default quality control"


def entry_quality_gate(decision, data, market_mode, bb_state, bb_extreme, buy_score, sell_score):
    """
    V18 Entry Quality Gate
    Runs before the final decision is written. Daily Loss Guard should remain
    an emergency brake; this gate attempts to prevent weak entries first.
    """
    if decision.get("decision") != "TRADE":
        return True, "ENTRY QUALITY: not a trade decision"

    bias = decision.get("bias", "NEUTRAL")
    management = decision.get("management", "SCALP_TP")
    entry_type = decision.get("entry_type", "")

    bid = safe_float(data.get("bid", 0))
    ma50 = safe_float(data.get("ma50", 0))
    ma90 = safe_float(data.get("ma90", 0))
    ma200 = safe_float(data.get("ma200", 0))
    rsi = safe_float(data.get("rsi", 50))
    macd_hist = safe_float(data.get("macd_hist", 0))
    bb_upper = safe_float(data.get("bb_upper", 0))
    bb_middle = safe_float(data.get("bb_middle", 0))
    bb_lower = safe_float(data.get("bb_lower", 0))

    score_gap = abs(buy_score - sell_score)
    trend_priority = is_trend_priority_setup(bias, bid, ma50, ma90, ma200, bb_state, bb_extreme, rsi, macd_hist, buy_score, sell_score)
    dual_mode, dual_mode_reason = determine_dual_mode(bias, market_mode, bb_state, bb_extreme, score_gap, rsi, macd_hist)

    learning_state = update_learning_from_trade_results()
    learning_key = make_learning_key(bias, market_mode, bb_state, management, entry_type)
    base_gap = base_adaptive_gap_requirement(market_mode, bb_state, rsi, macd_hist, management, entry_type)
    learn_adjust, learn_stats, learn_note = learning_gap_adjustment(learning_state, learning_key)
    learn_adjust = max(-LEARNING_MAX_GAP_ADJUST, min(LEARNING_MAX_GAP_ADJUST, learn_adjust))
    adaptive_gap = max(ADAPTIVE_GAP_MIN, min(ADAPTIVE_GAP_MAX, base_gap + learn_adjust))

    # V19.8: Dual Mode Auto Switch. Aggressive mode reduces gate strictness by 1,
    # while still respecting DEV4, compression, and momentum-confirmation blocks.
    if dual_mode == "AGGRESSIVE":
        adaptive_gap = max(ADAPTIVE_GAP_MIN, adaptive_gap - 1)

    # V20: trend priority lowers strictness on clear trend continuation,
    # but never below 2 and never bypasses DEV4/compression safety.
    if trend_priority:
        adaptive_gap = min(adaptive_gap, TREND_PRIORITY_MAX_GAP_REQUIRED)
        decision["trend_priority"] = True
        decision["trend_priority_reason"] = f"V20 trend priority | gap={score_gap} RSI={rsi:.2f} MACDHist={macd_hist:.2f}"
    else:
        decision["trend_priority"] = False
        decision["trend_priority_reason"] = "not trend priority"

    is_range_reversal = is_selective_range_reversal_entry(entry_type)

    # V19.3: loosen strong TREND setups by one gap level.
    # Goal: avoid over-blocking good continuation trades while keeping DEV4/compression safety intact.
    if market_mode == "TREND" and score_gap >= 3 and bb_state != "COMPRESSION":
        adaptive_gap = max(ADAPTIVE_GAP_MIN, adaptive_gap - 1)

    # V19.5: selective BB edge reversal is allowed with smaller/equal score only when RSI/MACD confirm bounce.
    if is_range_reversal and market_mode == "RANGE" and bb_state in ("REVERSAL_DOWN", "REVERSAL_UP"):
        adaptive_gap = 0 if score_gap == 0 else min(adaptive_gap, RANGE_REVERSAL_MIN_GAP)

    # V19.1/V19.3: TRANSITION + BB NORMAL is allowed only for strong setups.
    # If strong, use gap=3 instead of the stricter transition default gap=4.
    transition_strong_ok = False
    transition_reasons = []
    if market_mode == "TRANSITION" and bb_state == "NORMAL":
        transition_strong_ok, transition_reasons = is_strong_transition_normal_setup(
            bias, score_gap, rsi, macd_hist, bid, bb_upper, bb_middle, bb_lower
        )
        if transition_strong_ok:
            adaptive_gap = min(adaptive_gap, TRANSITION_NORMAL_ALLOW_GAP)

    enrich_decision_for_entry_gate(
        decision, data, market_mode, bb_state, bb_extreme, buy_score, sell_score,
        adaptive_gap=adaptive_gap, learning_key=learning_key,
        learning_stats=learn_stats, learning_adjust=learn_adjust, learning_note=learn_note,
    )
    decision["dual_mode"] = dual_mode
    decision["aggressive_mode"] = (dual_mode == "AGGRESSIVE")
    decision["dual_mode_reason"] = dual_mode_reason
    decision["trend_priority"] = bool(decision.get("trend_priority", trend_priority))
    decision["trend_priority_reason"] = decision.get("trend_priority_reason", "not trend priority")

    # V23_3 TREND WALK OVERRIDE
    # Do not use score_gap alone for TREND + BB WALK continuation.
    # This runs before the adaptive score-gap block.
    trend_walk_ok, trend_walk_reason, trend_walk_mode = trend_walk_override_signal(
        bias, market_mode, bb_state, bid, bb_upper, bb_middle, bb_lower,
        rsi, macd_hist, buy_score, sell_score, learn_adjust, learn_stats, learn_note
    )
    decision["trend_walk_mode"] = trend_walk_mode
    decision["trend_walk_reason"] = trend_walk_reason
    if trend_walk_ok:
        decision["trend_walk_override"] = True
        return True, trend_walk_reason

    # V23_3 TREND NORMAL CONTINUATION OVERRIDE
    # Do not use adaptive score gap alone for TREND + BB NORMAL continuation
    # when Soft Lock + RSI + MACD confirm direction.
    trend_normal_ok, trend_normal_reason, trend_normal_mode = trend_normal_continuation_signal(
        bias, market_mode, bb_state, bid, bb_upper, bb_middle, bb_lower,
        rsi, macd_hist, buy_score, sell_score,
        decision.get("soft_lock_state", ""), decision.get("soft_lock_direction", ""),
        learn_adjust, learn_stats, learn_note
    )
    decision["trend_normal_mode"] = trend_normal_mode
    decision["trend_normal_reason"] = trend_normal_reason
    if trend_normal_ok:
        decision["trend_normal_override"] = True
        return True, trend_normal_reason

    # V21.2 SPIKE CONTINUATION MODE
    # SPIKE is not a full block anymore. Only allow confirmed continuation,
    # and block fake spike / overextension. This runs after enrichment so EA receives schema fields.
    if market_mode == "SPIKE":
        bb4_upper = safe_float(data.get("bb4_upper", 0))
        bb4_lower = safe_float(data.get("bb4_lower", 0))
        overextended, over_reason = is_spike_bb_overextended(bb_upper, bb_lower, bb4_upper, bb4_lower)
        if overextended:
            decision["spike_mode"] = "BLOCK_OVEREXTENSION"
            return False, f"SPIKE BLOCK | overextension {over_reason}"

        if abs(macd_hist) < SPIKE_NO_FOLLOW_MACD_ABS_MAX:
            decision["spike_mode"] = "BLOCK_NO_FOLLOW_THROUGH"
            return False, f"SPIKE BLOCK | no follow-through MACDHist={macd_hist:.2f}"

        spike_ok, spike_reason = spike_continuation_signal(data, bias, bid, rsi, macd_hist, buy_score, sell_score)
        wick_block, wick_reason = has_extreme_wick_without_followthrough(data, bias, bid, rsi, macd_hist)
        if wick_block and not spike_ok:
            decision["spike_mode"] = "BLOCK_WICK_NO_FOLLOW"
            return False, f"SPIKE BLOCK | extreme wick without follow-through | {wick_reason}"

        if spike_ok and "SPIKE_CONTINUATION" in str(entry_type).upper():
            decision["spike_mode"] = "CONTINUATION"
            decision["spike_reason"] = spike_reason
            return True, spike_reason

        decision["spike_mode"] = "WAIT_CONFIRMATION"
        return False, f"SPIKE BLOCK | continuation not confirmed | {spike_reason}"

    # V19.1: TRANSITION + BB NORMAL must explicitly pass the balanced transition gate.
    if market_mode == "TRANSITION" and bb_state == "NORMAL" and not transition_strong_ok:
        # V19.8: Aggressive mode can pass transition-normal with a selective setup.
        # It still requires score_gap >= 2 and RSI/MACD not strongly opposite.
        if not (dual_mode == "AGGRESSIVE" and score_gap >= DUAL_AGGRESSIVE_MIN_GAP and dual_direction_confirm(bias, rsi, macd_hist)):
            return False, (
                f"ENTRY BLOCK | TRANSITION+NORMAL not strong enough "
                f"gap={score_gap} need={TRANSITION_NORMAL_ALLOW_GAP} "
                f"reasons={transition_reasons} | dual={dual_mode} | {learn_note}"
            )
        decision["transition_aggressive_override"] = True
        decision["transition_aggressive_reason"] = dual_mode_reason

    # V23_3 TREND NORMAL MOMENTUM OVERRIDE
    # Runs before adaptive score-gap block. Fixes TREND+NORMAL undertrade when
    # Soft Lock + strong MACD confirm continuation but score_gap is only 1.
    trend_momentum_ok, trend_momentum_reason, trend_momentum_mode = trend_normal_momentum_override_signal(
        bias, market_mode, bb_state, bid, bb_upper, bb_middle, bb_lower,
        rsi, macd_hist, buy_score, sell_score,
        decision.get("soft_lock_state", ""), decision.get("soft_lock_direction", ""),
        learn_adjust, learn_stats, learn_note
    )
    decision["trend_momentum_mode"] = trend_momentum_mode
    decision["trend_momentum_reason"] = trend_momentum_reason
    if trend_momentum_ok:
        decision["trend_momentum_override"] = True
        return True, trend_momentum_reason

    # V19 Adaptive Entry Score: one dynamic score gate replaces fixed score-gap rules.
    if score_gap < adaptive_gap:
        return False, f"ENTRY BLOCK | adaptive score gap {score_gap} < {adaptive_gap} mode={market_mode} bb={bb_state} | {learn_note}"

    # 3) Block entry near BB middle when no clear trend.
    # V19.7: For TRANSITION+NORMAL, allow near BB middle only when RSI + MACD confirm direction.
    if bb_state == "NORMAL" and market_mode != "TREND" and is_near_bb_middle(bid, bb_upper, bb_middle, bb_lower):
        if trend_priority:
            decision["middle_zone_override"] = True
            decision["middle_zone_override_reason"] = "V20 trend priority bypasses BB middle block"
        elif market_mode == "TRANSITION" and transition_rsi_macd_confirm(bias, rsi, macd_hist):
            decision["middle_zone_override"] = True
            decision["middle_zone_override_reason"] = "V19.7 transition normal RSI+MACD confirm direction"
        elif dual_mode == "AGGRESSIVE" and score_gap >= DUAL_AGGRESSIVE_MIN_GAP and dual_direction_confirm(bias, rsi, macd_hist):
            decision["middle_zone_override"] = True
            decision["middle_zone_override_reason"] = "V19.8 aggressive mode score+RSI/MACD confirm direction"
        elif is_strong_normal_direction_setup(bias, score_gap, rsi, macd_hist):
            decision["middle_zone_override"] = True
            decision["middle_zone_override_reason"] = "V19.6 strong score + RSI + MACD confirms direction"
        else:
            return False, "ENTRY BLOCK | near BB middle without clear trend"

    # 2) Block SCALP_TP if M15 and M3 are not aligned.
    if ENTRY_SCALP_REQUIRE_ALIGNMENT and management == "SCALP_TP" and not is_range_reversal:
        m3_dir = infer_m3_direction(rsi, macd_hist, buy_score, sell_score)
        m15_dir = infer_m15_direction(data, bid, ma50, ma90, ma200)
        if m3_dir != "NEUTRAL" and m15_dir != "NEUTRAL" and m3_dir != m15_dir:
            return False, f"ENTRY BLOCK | M15/M3 not aligned m15={m15_dir} m3={m3_dir}"
        if bias in ("BUY", "SELL"):
            if m3_dir != "NEUTRAL" and bias != m3_dir:
                return False, f"ENTRY BLOCK | trade bias conflicts with M3 direction bias={bias} m3={m3_dir}"
            if m15_dir != "NEUTRAL" and bias != m15_dir:
                return False, f"ENTRY BLOCK | trade bias conflicts with M15 direction bias={bias} m15={m15_dir}"

    # 4) Require momentum confirmation before trade.
    ok, reason = has_momentum_confirmation(bias, market_mode, bb_state, rsi, macd_hist, buy_score, sell_score, entry_type)
    if not ok:
        return False, reason

    return True, "ENTRY QUALITY APPROVED"


def apply_entry_quality_or_block(decision, data, market_mode, bb_state, bb_extreme, buy_score, sell_score):
    ok, gate_reason = entry_quality_gate(decision, data, market_mode, bb_state, bb_extreme, buy_score, sell_score)
    if not ok:
        print(gate_reason)
        blocked = no_trade(gate_reason, market_mode, bb_state)
        for key in (
            "buy_score", "sell_score", "score_gap", "dir_m15", "dir_m3",
            "rsi", "macd_hist", "bb_mid", "bb_upper2", "bb_lower2",
            "analysis_quality", "adaptive_gap", "learning_enabled", "learning_key",
            "learning_gap_adjust", "learning_note", "learning_stats", "bb_extreme",
            "dual_mode", "aggressive_mode", "dual_mode_reason", "trend_priority", "trend_priority_reason",
            "transition_aggressive_override", "transition_aggressive_reason",
            "soft_lock_state", "soft_lock_direction", "soft_lock_allowed", "soft_lock_reason",
            "transition_decay_count", "transition_decay_required", "transition_decay_active", "transition_decay_reason",
            "soft_lock_counter_reset", "soft_lock_counter_reset_reason",
            "fresh_state_reset", "fresh_state_reset_reason", "market_state_fresh", "market_state_signature",
            "trend_walk_mode", "trend_walk_reason", "trend_walk_override",
            "trend_normal_mode", "trend_normal_reason", "trend_normal_override"
        ):
            if key in decision:
                blocked[key] = decision[key]
        blocked["entry_allowed"] = False
        blocked["entry_quality"] = "BLOCKED"
        blocked["entry_quality_reason"] = gate_reason
        return blocked
    decision["entry_allowed"] = True
    decision["entry_quality"] = "APPROVED"
    decision["entry_quality_reason"] = gate_reason
    decision["reason"] = f"{decision.get('reason', '')} | {gate_reason}"
    return decision


def is_trend_pullback_buy(bid, ma50, ma90, ma200, bb_middle, bb_state, bb_extreme, rsi, macd_hist, buy_score, sell_score, h1_bias, h4_bias):
    if not ENABLE_TREND_PULLBACK_ALLOW:
        return False
    if buy_score - sell_score < TREND_PULLBACK_MIN_EDGE:
        return False
    if not is_bullish_context(h1_bias, h4_bias, ma50, ma90, ma200):
        return False
    if bb_extreme == "DEV4_UPPER":
        return False
    if bb_state in ("WALK_DOWN", "COMPRESSION"):
        return False
    if not (TREND_PULLBACK_BUY_MIN_RSI <= rsi <= TREND_PULLBACK_BUY_MAX_RSI):
        return False
    if macd_hist < -TREND_PULLBACK_MACD_TOLERANCE:
        return False
    return bid > ma50 or is_near_ma_zone(bid, ma50, ma90, bb_middle) or bb_state == "REVERSAL_DOWN"


def is_trend_pullback_sell(bid, ma50, ma90, ma200, bb_middle, bb_state, bb_extreme, rsi, macd_hist, buy_score, sell_score, h1_bias, h4_bias):
    if not ENABLE_TREND_PULLBACK_ALLOW:
        return False
    if sell_score - buy_score < TREND_PULLBACK_MIN_EDGE:
        return False
    if not is_bearish_context(h1_bias, h4_bias, ma50, ma90, ma200):
        return False
    if bb_extreme == "DEV4_LOWER":
        return False
    if bb_state in ("WALK_UP", "COMPRESSION"):
        return False
    if not (TREND_PULLBACK_SELL_MIN_RSI <= rsi <= TREND_PULLBACK_SELL_MAX_RSI):
        return False
    if macd_hist > TREND_PULLBACK_MACD_TOLERANCE:
        return False
    return bid < ma50 or is_near_ma_zone(bid, ma50, ma90, bb_middle) or bb_state == "REVERSAL_UP"

def classify_market(bid, ma50, rsi, macd_hist, buy_score, sell_score, bb_state, ma90=0.0, ma200=0.0, bb_extreme="NONE"):
    if bb_state in ("WALK_UP", "WALK_DOWN"):
        return "TREND"
    if bb_state == "COMPRESSION":
        return "TRANSITION"

    # V20: clear trend continuation should be TREND, not TRANSITION/RANGE,
    # even when BB is NORMAL. This fixes undertrading on obvious trend days.
    if trend_priority_bias(bid, ma50, ma90, ma200, bb_state, bb_extreme, rsi, macd_hist, buy_score, sell_score):
        return "TREND"

    macd_abs = abs(macd_hist)
    if rsi >= SPIKE_BUY_RSI or rsi <= SPIKE_SELL_RSI or macd_abs >= SPIKE_MACD_ABS_MIN:
        return "SPIKE"

    if RANGE_RSI_LOW <= rsi <= RANGE_RSI_HIGH and macd_abs <= RANGE_MACD_ABS_MAX and abs(buy_score - sell_score) <= 1:
        return "RANGE"

    if buy_score > sell_score and bid > ma50 and rsi >= TREND_BUY_RSI:
        return "TREND"
    if sell_score > buy_score and bid < ma50 and rsi <= TREND_SELL_RSI:
        return "TREND"

    # V19.6: classify strong directional NORMAL setups as TREND instead of TRANSITION.
    # This fixes cases like BUY 5:0, RSI > 56, MACD positive, price above MA50.
    score_gap = abs(buy_score - sell_score)
    if buy_score > sell_score and bid > ma50 and is_strong_normal_direction_setup("BUY", score_gap, rsi, macd_hist):
        return "TREND"
    if sell_score > buy_score and bid < ma50 and is_strong_normal_direction_setup("SELL", score_gap, rsi, macd_hist):
        return "TREND"

    if buy_score > sell_score or sell_score > buy_score:
        return "TRANSITION"
    return "RANGE"


def risk_points_for_mode(market_mode):
    if market_mode == "TREND":
        return SL_POINTS_TREND, TP_POINTS_TREND
    if market_mode == "RANGE":
        return SL_POINTS_RANGE, TP_POINTS_RANGE
    if market_mode == "SPIKE":
        return SL_POINTS_SPIKE, TP_POINTS_SPIKE
    return SL_POINTS_TRANSITION, TP_POINTS_TRANSITION


def is_buy_runner(market_mode, bb_state, bid, ma50, rsi, macd_hist, buy_score, sell_score):
    return (
        ENABLE_SLOT3_RUNNER and market_mode == "TREND" and bb_state == "WALK_UP"
        and buy_score >= BUY_SLOT3_MIN_SCORE and sell_score == 0
        and bid > ma50 and rsi >= BUY_SLOT3_MIN_RSI and macd_hist >= BUY_SLOT3_MIN_MACD_HIST
    )


def is_sell_runner(market_mode, bb_state, bid, ma50, rsi, macd_hist, buy_score, sell_score):
    return (
        ENABLE_SLOT3_RUNNER and market_mode == "TREND" and bb_state == "WALK_DOWN"
        and sell_score >= SELL_SLOT3_MIN_SCORE and buy_score == 0
        and bid < ma50 and rsi <= SELL_SLOT3_MAX_RSI and macd_hist <= SELL_SLOT3_MAX_MACD_HIST
    )


def choose_range_tp(bias, bid, bb_middle, bb_upper, bb_lower, fallback_tp):
    if bb_middle > 0:
        if bias == "BUY" and bb_middle > bid:
            return bb_middle
        if bias == "SELL" and bb_middle < bid:
            return bb_middle
    return bid + fallback_tp if bias == "BUY" else bid - fallback_tp


def clamp_int(value, min_value=0, max_value=100):
    try:
        return max(min_value, min(max_value, int(round(value))))
    except Exception:
        return min_value


def build_manual_trend_report(data, decision):
    """
    Manual Trend Report Layer V1
    This is a reporting layer only. It does not approve/block/modify trade execution.

    Output fields:
    - trend_bias: BUY / SELL / NEUTRAL
    - confidence: 0-100
    - manual_action: practical manual-trading instruction
    - danger_zone: risk context, especially BB dev4/extreme zones
    """
    bid = safe_float(data.get("bid", 0))
    ma50 = safe_float(data.get("ma50", 0))
    ma90 = safe_float(data.get("ma90", 0))
    ma200 = safe_float(data.get("ma200", 0))
    rsi = safe_float(data.get("rsi", 50))
    macd_hist = safe_float(data.get("macd_hist", 0))
    bb_upper = safe_float(data.get("bb_upper", 0))
    bb_middle = safe_float(data.get("bb_middle", 0))
    bb_lower = safe_float(data.get("bb_lower", 0))
    bb4_upper = safe_float(data.get("bb4_upper", 0))
    bb4_lower = safe_float(data.get("bb4_lower", 0))
    h1_bias = data.get("h1_bias", "")
    h4_bias = data.get("h4_bias", "")
    buy_score, sell_score = get_scores(data)

    bb_state = decision.get("bb_state", "UNKNOWN")
    market_mode = decision.get("market_mode", "UNKNOWN")
    bb_extreme = classify_bb_extreme(bid, bb4_upper, bb4_lower)

    bull_ctx = is_bullish_context(h1_bias, h4_bias, ma50, ma90, ma200)
    bear_ctx = is_bearish_context(h1_bias, h4_bias, ma50, ma90, ma200)

    buy_conf = 0
    sell_conf = 0

    # Score edge contribution
    buy_conf += max(0, buy_score - sell_score) * 12
    sell_conf += max(0, sell_score - buy_score) * 12

    # HTF/MA context contribution
    if bull_ctx:
        buy_conf += 18
    if bear_ctx:
        sell_conf += 18

    # Price vs MA contribution
    if bid > ma50 > 0:
        buy_conf += 10
    if bid < ma50 and ma50 > 0:
        sell_conf += 10
    if ma50 > ma90 > 0:
        buy_conf += 8
    if ma50 < ma90 and ma90 > 0:
        sell_conf += 8
    if ma90 > ma200 > 0:
        buy_conf += 6
    if ma90 < ma200 and ma200 > 0:
        sell_conf += 6

    # RSI / MACD contribution
    if rsi >= 55:
        buy_conf += 10
    elif rsi <= 45:
        sell_conf += 10
    if macd_hist > 0:
        buy_conf += 8
    elif macd_hist < 0:
        sell_conf += 8

    # BB state contribution
    if bb_state == "WALK_UP":
        buy_conf += 16
    elif bb_state == "WALK_DOWN":
        sell_conf += 16
    elif bb_state == "REVERSAL_UP":
        sell_conf += 8
    elif bb_state == "REVERSAL_DOWN":
        buy_conf += 8
    elif bb_state == "COMPRESSION":
        buy_conf -= 12
        sell_conf -= 12

    buy_conf = clamp_int(buy_conf)
    sell_conf = clamp_int(sell_conf)

    if buy_conf >= sell_conf + 10:
        trend_bias = "BUY"
        confidence = buy_conf
    elif sell_conf >= buy_conf + 10:
        trend_bias = "SELL"
        confidence = sell_conf
    else:
        trend_bias = "NEUTRAL"
        confidence = max(buy_conf, sell_conf)

    # Danger zone
    if bb_extreme == "DEV4_UPPER":
        danger_zone = "DEV4_UPPER_OVEREXTENDED"
    elif bb_extreme == "DEV4_LOWER":
        danger_zone = "DEV4_LOWER_OVEREXTENDED"
    elif bb_state == "COMPRESSION":
        danger_zone = "BB_COMPRESSION_WAIT_BREAKOUT"
    elif bb_state == "REVERSAL_UP":
        danger_zone = "BB_UPPER_REVERSAL_ZONE"
    elif bb_state == "REVERSAL_DOWN":
        danger_zone = "BB_LOWER_REVERSAL_ZONE"
    elif bb_state in ("WALK_UP", "WALK_DOWN"):
        danger_zone = "BB_WALK_TREND_EXPANSION"
    elif bb_upper > 0 and bb_lower > 0 and bb_middle > 0:
        if bid > bb_middle and abs(bid - bb_middle) < (bb_upper - bb_lower) * 0.12:
            danger_zone = "BB_MIDDLE_DECISION_ZONE"
        else:
            danger_zone = "NONE"
    else:
        danger_zone = "UNKNOWN"

    # Manual action instruction
    if danger_zone == "BB_COMPRESSION_WAIT_BREAKOUT":
        manual_action = "WAIT_FOR_BREAKOUT"
    elif trend_bias == "BUY":
        if danger_zone == "DEV4_UPPER_OVEREXTENDED":
            manual_action = "DO_NOT_CHASE_BUY_WAIT_PULLBACK"
        elif bb_state == "WALK_UP":
            manual_action = "HOLD_BUY_OR_LOOK_FOR_PULLBACK_BUY"
        elif is_near_ma_zone(bid, ma50, ma90, bb_middle):
            manual_action = "LOOK_FOR_BUY_PULLBACK_CONFIRM"
        elif bb_state == "REVERSAL_DOWN":
            manual_action = "LOOK_FOR_BUY_REJECTION_CONFIRM"
        else:
            manual_action = "BUY_BIAS_WAIT_CONFIRM"
    elif trend_bias == "SELL":
        if danger_zone == "DEV4_LOWER_OVEREXTENDED":
            manual_action = "DO_NOT_CHASE_SELL_WAIT_PULLBACK"
        elif bb_state == "WALK_DOWN":
            manual_action = "HOLD_SELL_OR_LOOK_FOR_PULLBACK_SELL"
        elif is_near_ma_zone(bid, ma50, ma90, bb_middle):
            manual_action = "LOOK_FOR_SELL_PULLBACK_CONFIRM"
        elif bb_state == "REVERSAL_UP":
            manual_action = "LOOK_FOR_SELL_REJECTION_CONFIRM"
        else:
            manual_action = "SELL_BIAS_WAIT_CONFIRM"
    else:
        manual_action = "WAIT"

    # Keep manual report conservative when current automated decision is NO_TRADE.
    if decision.get("decision") == "NO_TRADE" and confidence < 65:
        manual_action = "WAIT"

    return {
        "trend_bias": trend_bias,
        "confidence": confidence,
        "manual_action": manual_action,
        "danger_zone": danger_zone,
        "manual_report": {
            "buy_confidence": buy_conf,
            "sell_confidence": sell_conf,
            "market_mode": market_mode,
            "bb_state": bb_state,
            "bb_extreme": bb_extreme,
            "note": "Manual report only; does not change automated trade decision."
        }
    }


def attach_manual_trend_report(decision, data):
    if not isinstance(decision, dict):
        return decision
    if not isinstance(data, dict):
        decision["trend_bias"] = decision.get("trend_bias", "NEUTRAL")
        decision["confidence"] = decision.get("confidence", 0)
        decision["manual_action"] = decision.get("manual_action", "WAIT")
        decision["danger_zone"] = decision.get("danger_zone", "UNKNOWN")
        return decision

    report = build_manual_trend_report(data, decision)
    decision.update(report)
    return decision


def build_decision(data):
    bid = safe_float(data.get("bid", 0))
    ma50 = safe_float(data.get("ma50", 0))
    ma90 = safe_float(data.get("ma90", 0))
    ma200 = safe_float(data.get("ma200", 0))
    h1_bias = data.get("h1_bias", "")
    h4_bias = data.get("h4_bias", "")
    rsi = safe_float(data.get("rsi", 50))
    macd_hist = safe_float(data.get("macd_hist", 0))
    bb_upper = safe_float(data.get("bb_upper", 0))
    bb_middle = safe_float(data.get("bb_middle", 0))
    bb_lower = safe_float(data.get("bb_lower", 0))
    bb4_upper = safe_float(data.get("bb4_upper", 0))
    bb4_lower = safe_float(data.get("bb4_lower", 0))
    bar_time = data.get("bar_time", now())

    buy_score, sell_score = get_scores(data)
    base_key = f"{bar_time}-XAU-V21_2"

    if bid <= 0:
        return base_key, bar_time, no_trade("invalid bid price")
    if ma50 <= 0:
        return base_key, bar_time, no_trade("invalid ma50")

    bb_state = classify_bb_state(bid, ma50, bb_upper, bb_middle, bb_lower, rsi, macd_hist, buy_score, sell_score)
    bb_extreme = classify_bb_extreme(bid, bb4_upper, bb4_lower)
    market_mode = classify_market(bid, ma50, rsi, macd_hist, buy_score, sell_score, bb_state, ma90, ma200, bb_extreme)

    range_reversal_bias, range_reversal_reason = get_selective_range_reversal_bias(
        bb_state, rsi, macd_hist, buy_score, sell_score
    )

    if buy_score == sell_score and not range_reversal_bias:
        reason = f"NO TRADE | equal score without reversal momentum | buyScore {buy_score} = sellScore {sell_score}"
        print(f"MODE:{market_mode} BB:{bb_state} EXT:{bb_extreme} SCORE BUY:{buy_score} SELL:{sell_score} RSI:{rsi:.2f} MACDHist:{macd_hist:.2f} ACTION:NO_TRADE")
        return base_key, bar_time, no_trade(reason, market_mode, bb_state)

    # Dev4 over-extension filter: do not open new trend/chasing trades at red BB dev4 extremes
    if bb_extreme == "DEV4_UPPER" and buy_score > sell_score:
        return base_key, bar_time, no_trade("BLOCK BUY | BB DEV4 upper extreme - wait pullback/reversal", market_mode, bb_state)
    if bb_extreme == "DEV4_LOWER" and sell_score > buy_score:
        return base_key, bar_time, no_trade("BLOCK SELL | BB DEV4 lower extreme - wait pullback/reversal", market_mode, bb_state)

    # V21 Soft Direction Lock replaces the old hard BB-walk direction block.
    # Opposite direction is handled later by soft_direction_lock_v2():
    # TREND_LOCK / TRANSITION_WAIT / REVERSAL_ALLOW.

    sl_points, tp_points = risk_points_for_mode(market_mode)
    key = f"{bar_time}-XAU-V21_2-{market_mode}-{bb_state}"

    action = "NO_TRADE"
    entry_type = ""
    entry_slot = 0
    management = "SCALP_TP"
    reason = f"no setup | mode={market_mode} bb={bb_state} buyScore={buy_score} sellScore={sell_score}"

    if market_mode == "TRANSITION" and bb_state == "COMPRESSION":
        return key, bar_time, no_trade("COMPRESSION no trade | wait for breakout", market_mode, bb_state)

    # V21.2 SPIKE CONTINUATION MODE
    # Do not fully block SPIKE. Allow only confirmed breakout continuation; otherwise
    # let the quality gate reject weak/no-follow-through spike setups.
    if market_mode == "SPIKE":
        if buy_score > sell_score:
            spike_ok, spike_reason = spike_continuation_signal(data, "BUY", bid, rsi, macd_hist, buy_score, sell_score)
            if spike_ok:
                action = "BUY"
                entry_slot = 2
                entry_type = "XAU_SPIKE_CONTINUATION_BUY_SLOT2"
                management = "SCALP_TP"
                reason = spike_reason
        elif sell_score > buy_score:
            spike_ok, spike_reason = spike_continuation_signal(data, "SELL", bid, rsi, macd_hist, buy_score, sell_score)
            if spike_ok:
                action = "SELL"
                entry_slot = 2
                entry_type = "XAU_SPIKE_CONTINUATION_SELL_SLOT2"
                management = "SCALP_TP"
                reason = spike_reason

    if action == "NO_TRADE" and (market_mode == "RANGE" or bb_state in ("REVERSAL_UP", "REVERSAL_DOWN", "NORMAL")):
        edge = abs(buy_score - sell_score)

        # V19.5: selective range-reversal bounce/rejection at BB edge.
        # Allows score_gap 0 only when RSI/MACD clearly confirm bounce; otherwise requires score_gap >= 1.
        if range_reversal_bias == "BUY":
            action = "BUY"; entry_slot = 1; entry_type = "XAU_RANGE_REVERSAL_BUY_SLOT1"
            market_mode = "RANGE"
            reason = range_reversal_reason
        elif range_reversal_bias == "SELL":
            action = "SELL"; entry_slot = 1; entry_type = "XAU_RANGE_REVERSAL_SELL_SLOT1"
            market_mode = "RANGE"
            reason = range_reversal_reason
        else:
            if edge < RANGE_MIN_SCORE_EDGE:
                return key, bar_time, no_trade(f"RANGE no trade | weak edge {buy_score}-{sell_score}", market_mode, bb_state)

            if buy_score > sell_score:
                # Do not buy upper band unless true walk, already handled above
                if bb_state == "REVERSAL_UP":
                    return key, bar_time, no_trade("BLOCK BUY | near BB upper reversal zone", market_mode, bb_state)
                action = "BUY"; entry_slot = 1; entry_type = "XAU_BB_SCALP_BUY_SLOT1"
                reason = f"BB SCALP BUY | bb={bb_state} buyScore {buy_score}>{sell_score}"
            elif sell_score > buy_score:
                if bb_state == "REVERSAL_DOWN":
                    return key, bar_time, no_trade("BLOCK SELL | near BB lower reversal zone", market_mode, bb_state)
                action = "SELL"; entry_slot = 1; entry_type = "XAU_BB_SCALP_SELL_SLOT1"
                reason = f"BB SCALP SELL | bb={bb_state} sellScore {sell_score}>{buy_score}"

    if market_mode == "TREND":
        if buy_score > sell_score:
            action = "BUY"
            if is_buy_runner(market_mode, bb_state, bid, ma50, rsi, macd_hist, buy_score, sell_score):
                entry_slot = 3; entry_type = "XAU_BB_WALK_BUY_SLOT3_RUNNER"; management = "HOLD_TRAIL"
                reason = f"BB WALK BUY RUNNER | score {buy_score}>{sell_score} RSI {rsi:.2f} MACDHist {macd_hist:.2f}"
            elif bid > ma50:
                entry_slot = 2; entry_type = "XAU_TREND_BUY_SLOT2"; management = "HOLD_TRAIL" if bb_state == "WALK_UP" else "SCALP_TP"
                reason = f"TREND BUY | bb={bb_state} buyScore {buy_score}>{sell_score}"
            else:
                action = "NO_TRADE"
                reason = "TREND BUY waiting for pullback allow | price below MA50"
        elif sell_score > buy_score:
            action = "SELL"
            if is_sell_runner(market_mode, bb_state, bid, ma50, rsi, macd_hist, buy_score, sell_score):
                entry_slot = 3; entry_type = "XAU_BB_WALK_SELL_SLOT3_RUNNER"; management = "HOLD_TRAIL"
                reason = f"BB WALK SELL RUNNER | score {sell_score}>{buy_score} RSI {rsi:.2f} MACDHist {macd_hist:.2f}"
            elif bid < ma50:
                entry_slot = 2; entry_type = "XAU_TREND_SELL_SLOT2"; management = "HOLD_TRAIL" if bb_state == "WALK_DOWN" else "SCALP_TP"
                reason = f"TREND SELL | bb={bb_state} sellScore {sell_score}>{buy_score}"
            else:
                action = "NO_TRADE"
                reason = "TREND SELL waiting for pullback allow | price above MA50"

    # V17 Trend Pullback Allow: if normal TREND logic did not qualify because price is around MA50/MA90/BB middle,
    # allow a controlled continuation entry when HTF/MA context and score edge are strong.
    if action == "NO_TRADE" or entry_slot == 0:
        if is_trend_pullback_buy(bid, ma50, ma90, ma200, bb_middle, bb_state, bb_extreme, rsi, macd_hist, buy_score, sell_score, h1_bias, h4_bias):
            market_mode = "TREND"
            action = "BUY"
            entry_slot = 2
            entry_type = "XAU_TREND_PULLBACK_BUY_SLOT2"
            management = "SCALP_TP"
            sl_points, tp_points = risk_points_for_mode(market_mode)
            reason = f"TREND PULLBACK BUY ALLOW | score {buy_score}>{sell_score} bb={bb_state} RSI {rsi:.2f} MACDHist {macd_hist:.2f}"
        elif is_trend_pullback_sell(bid, ma50, ma90, ma200, bb_middle, bb_state, bb_extreme, rsi, macd_hist, buy_score, sell_score, h1_bias, h4_bias):
            market_mode = "TREND"
            action = "SELL"
            entry_slot = 2
            entry_type = "XAU_TREND_PULLBACK_SELL_SLOT2"
            management = "SCALP_TP"
            sl_points, tp_points = risk_points_for_mode(market_mode)
            reason = f"TREND PULLBACK SELL ALLOW | score {sell_score}>{buy_score} bb={bb_state} RSI {rsi:.2f} MACDHist {macd_hist:.2f}"

    soft_lock = soft_direction_lock_v2(action, market_mode, bb_state, bb_extreme, data, buy_score, sell_score)
    if action in ("BUY", "SELL") and not soft_lock.get("soft_lock_allowed", True):
        print(f"SOFT LOCK BLOCK | state={soft_lock.get('soft_lock_state')} dir={soft_lock.get('soft_lock_direction')} reason={soft_lock.get('soft_lock_reason')}")
        blocked = no_trade(f"SOFT LOCK BLOCK | {soft_lock.get('soft_lock_state')} | {soft_lock.get('soft_lock_reason')}", market_mode, bb_state)
        blocked = attach_soft_lock_fields(blocked, soft_lock)
        return key, bar_time, blocked

    print(f"MODE:{market_mode} BB:{bb_state} EXT:{bb_extreme} SCORE BUY:{buy_score} SELL:{sell_score} RSI:{rsi:.2f} MACDHist:{macd_hist:.2f} ACTION:{action} SLOT:{entry_slot} MGMT:{management} SOFT={soft_lock.get('soft_lock_state')}")

    if action == "BUY":
        sl = bid - sl_points
        tp = 0 if management == "HOLD_TRAIL" else choose_range_tp("BUY", bid, bb_middle, bb_upper, bb_lower, tp_points)
        decision_data = trade("BUY", entry_type, sl, tp, reason, entry_slot, market_mode, bb_state, management)
        decision_data = attach_soft_lock_fields(decision_data, soft_lock)
        decision_data = apply_entry_quality_or_block(
            decision_data, data, market_mode, bb_state, bb_extreme, buy_score, sell_score
        )
        decision_data = apply_nova_brain_or_block(
            decision_data, market_mode, bb_state, bb_extreme, rsi, macd_hist, buy_score, sell_score
        )
        decision_data = apply_candle_intelligence_or_block(
            decision_data, data, market_mode, bb_state, bb_extreme, buy_score, sell_score
        )
        decision_data = apply_trend_exhaustion_or_block(
            decision_data, data, market_mode, bb_state, bb_extreme
        )
        decision_data = apply_market_structure_exhaustion_master_gate(
            decision_data, data, market_mode, bb_state, bb_extreme
        )
        return key, bar_time, decision_data

    if action == "SELL":
        sl = bid + sl_points
        tp = 0 if management == "HOLD_TRAIL" else choose_range_tp("SELL", bid, bb_middle, bb_upper, bb_lower, tp_points)
        decision_data = trade("SELL", entry_type, sl, tp, reason, entry_slot, market_mode, bb_state, management)
        decision_data = attach_soft_lock_fields(decision_data, soft_lock)
        decision_data = apply_entry_quality_or_block(
            decision_data, data, market_mode, bb_state, bb_extreme, buy_score, sell_score
        )
        decision_data = apply_nova_brain_or_block(
            decision_data, market_mode, bb_state, bb_extreme, rsi, macd_hist, buy_score, sell_score
        )
        decision_data = apply_candle_intelligence_or_block(
            decision_data, data, market_mode, bb_state, bb_extreme, buy_score, sell_score
        )
        decision_data = apply_trend_exhaustion_or_block(
            decision_data, data, market_mode, bb_state, bb_extreme
        )
        decision_data = apply_market_structure_exhaustion_master_gate(
            decision_data, data, market_mode, bb_state, bb_extreme
        )
        return key, bar_time, decision_data

    decision_data = no_trade(reason, market_mode, bb_state)
    decision_data = apply_candle_intelligence_or_block(
        decision_data, data, market_mode, bb_state, bb_extreme, buy_score, sell_score
    )
    return key, bar_time, decision_data


def run():
    print("RP AI Decision Engine XAUUSD V21.2 SOFT DIRECTION LOCK + SPIKE CONTINUATION + EA SCHEMA FIX started")
    print(f"BASE_PATH = {BASE_PATH}")
    print("Modes: TREND / RANGE / SPIKE / TRANSITION + BB adaptive state")
    print("Management: SCALP_TP / HOLD_TRAIL")
    print("Trend Priority: clear trend overrides transition/BB-middle hesitation when safe")
    print("Soft Direction Lock V2: TREND_LOCK / TRANSITION_WAIT / REVERSAL_ALLOW")
    print("Spike Continuation: confirmed breakout after SPIKE, fake wick/overextension blocked")
    print("Manual Report: trend_bias / confidence / manual_action / danger_zone")
    print("Entry Quality Gate: dual mode safe/aggressive / selective range reversal / balanced transition / adaptive score / M15-M3 alignment / BB middle block / momentum confirmation / learning")
    print(f"MAX_SIGNALS_PER_BAR = {MAX_SIGNALS_PER_BAR} | COOLDOWN_SECONDS = {COOLDOWN_SECONDS}")

    while True:
        data = read_market()
        if data is None:
            write_decision(no_trade("market_state read failed"))
            time.sleep(1)
            continue
        try:
            key, bar_time, decision = build_decision(data)
            decision = attach_manual_trend_report(decision, data)
            fire_ok, fire_reason = can_fire_or_strong_override(key, bar_time, decision, data)
            if fire_ok:
                write_decision(decision)
            else:
                print("COOLDOWN / MAX SIGNAL BLOCK:", key, "|", fire_reason)
        except Exception as e:
            print("LOGIC ERROR:", e)
            write_decision(no_trade(f"logic error: {e}"))
        time.sleep(1)


if __name__ == "__main__":
    run()
