import json
import os
import time
from datetime import datetime
from pathlib import Path

from trade_management_dashboard import load_trade_management_dashboard

# V25 Pullback Fallback Mode
# V25 RP TIME SYNC STANDARD V1
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
# - V25: TREND NORMAL Momentum Override (TREND_LOCK + strong MACD can pass even with score_gap=1)
# - V25: Transition Decay Logic V1 (Soft Lock waits for persistent weakening before TRANSITION_WAIT)
# - V25: Trend Exhaustion Detection (avoid late continuation when RSI/MACD/BB/wick show exhaustion)
# - V25: Market Structure + Exhaustion Master Gate (HH/HL, LH/LL, BOS/CHOCH, liquidity sweep, distribution/accumulation, late-entry block)
# - V25.1: Soft Lock Counter Reset (reset stale persistent weakening counter when context/momentum/bar changes)
# - V25: Fresh Market State + Soft Lock Stale Reset (decision.json must follow latest market_state)
# - V25: Fresh Market State Read Fix (force fresh file read every loop + MARKET_STATE_READ log)
# - V25: Pullback Continuation Engine (healthy pullback + continuation return, avoid expansion chase)
# ============================================================

SYMBOL = "XAUUSD"
TIMEFRAME = "M15"

COMMON_SHARED_ROOT = Path(r"C:\Users\rp_fu\AppData\Roaming\MetaQuotes\Terminal\Common\Files\RP_AI_EA\shared")
BASE_PATH = COMMON_SHARED_ROOT / SYMBOL
FILE_PATH = BASE_PATH / "market_state.json"
OUTPUT_PATH = BASE_PATH / "decision.json"


RUNTIME_BRANCH = "codex-dev"
ARCH_VERSION = "V27"
BUILD_TAG = "trade-management-dashboard-architecture"
RUNTIME_SIGNATURE = f"{RUNTIME_BRANCH}|{ARCH_VERSION}|{BUILD_TAG}"

# V26 Execution Confidence Engine
V26_EXECUTION_CONFIDENCE_ENABLED = True
V26_WAIT_IS_NOT_NO_TRADE = True
V26_HARD_BLOCKS_ONLY_SAFETY = True

# V26.6.5A Executor Authority Enforcement Hotfix
# The MT5 executor may still contain historical V15/V16/V17 strategy gates.
# Under AI authority, these fields are compatibility/telemetry only; hard
# execution veto authority is restricted to invalid/stale payload/schema, broker
# safety, duplicate protection, insufficient margin, market closed, and
# catastrophic risk states. Strategy arbitration belongs exclusively to AI.
LEGACY_EXECUTOR_MIN_COMPAT_ANALYSIS_QUALITY = 60
LEGACY_EXECUTOR_VETO_AUDIT = (
    {"gate": "V17_AI_QUALITY_BLOCK", "classification": "SOFT_DIAGNOSTIC_PENALTY", "terminal_veto_allowed": False},
    {"gate": "V17_HARD_BLOCK", "classification": "SOFT_DIAGNOSTIC_PENALTY", "terminal_veto_allowed": False},
    {"gate": "V16_ENTRY_BLOCK_LOW_MOMENTUM", "classification": "SOFT_DIAGNOSTIC_PENALTY", "terminal_veto_allowed": False},
    {"gate": "V15_ENTRY_BLOCK", "classification": "SOFT_DIAGNOSTIC_PENALTY", "terminal_veto_allowed": False},
    {"gate": "analysis_quality_filters", "classification": "SOFT_DIAGNOSTIC_PENALTY", "terminal_veto_allowed": False},
    {"gate": "alignment_vetoes", "classification": "SOFT_DIAGNOSTIC_PENALTY", "terminal_veto_allowed": False},
    {"gate": "M15_M3_alignment_diagnostics", "classification": "SOFT_DIAGNOSTIC_PENALTY", "terminal_veto_allowed": False},
    {"gate": "legacy_participation_gates", "classification": "SOFT_DIAGNOSTIC_PENALTY", "terminal_veto_allowed": False},
    {"gate": "stale_decision", "classification": "HARD_SAFETY_BLOCK", "terminal_veto_allowed": True},
    {"gate": "invalid_payload_or_schema", "classification": "HARD_SAFETY_BLOCK", "terminal_veto_allowed": True},
    {"gate": "abnormal_spread_liquidity_broker_freeze", "classification": "HARD_SAFETY_BLOCK", "terminal_veto_allowed": True},
    {"gate": "duplicate_order_protection", "classification": "HARD_SAFETY_BLOCK", "terminal_veto_allowed": True},
    {"gate": "daily_risk_limit", "classification": "HARD_SAFETY_BLOCK", "terminal_veto_allowed": True},
    {"gate": "insufficient_margin", "classification": "HARD_SAFETY_BLOCK", "terminal_veto_allowed": True},
    {"gate": "market_closed", "classification": "HARD_SAFETY_BLOCK", "terminal_veto_allowed": True},
    {"gate": "catastrophic_risk_state", "classification": "HARD_SAFETY_BLOCK", "terminal_veto_allowed": True},
)


V26_EXECUTE_AGGRESSIVE_SCORE = 82
V26_EXECUTE_NORMAL_SCORE = 65
V26_EXECUTE_CAUTIOUS_SCORE = 45
V26_WAIT_SCORE = 26

# V26.4.7 Participation Restoration Program
# Governance hesitation remains visible as penalties/lifecycle fields, but valid
# directional authority may not be trapped in recursive WAIT/NO_TRADE forever.
WAIT_TIMEOUT_CYCLES = 4
TRANSITION_WAIT_MAX_CYCLES = 6
WEAK_MOMENTUM_CONFIDENCE_PENALTY = 15
WEAK_MOMENTUM_EXECUTE_MIN_GAP = 2
INTENT_PAYLOAD_MIN_SCORE_GAP = 2
STRONG_TRANSITION_NORMAL_SCORE_GAP = 4

# V26.5 Execution Quality Core Upgrade
# Direction is no longer enough; every directional idea must pass location,
# leg construction, and profit-extraction quality checks before execution.
V26_5_ENTRY_LOCATION_MIN_EXECUTE = 50
V26_5_ENTRY_LOCATION_MIN_CONFIRMATION = 62
V26_5_ENTRY_LOCATION_MIN_CONTINUATION = 70
V26_5_ENTRY_LOCATION_POOR_CAP = V26_WAIT_SCORE
V26_5_ENTRY_LOCATION_WEAK_PENALTY = 18
V26_5_ENTRY_LOCATION_GOOD_BONUS = 10
V26_5_ENTRY_LOCATION_EXCELLENT_BONUS = 16
V26_5_PROFIT_LOCK_LADDER_POINTS = [
    {"profit_points": 100, "lock_points": 50},
    {"profit_points": 200, "lock_points": 100},
    {"profit_points": 300, "lock_points": 200},
]
V26_5_DAILY_METRICS_ENABLED = True

V26_M3_MAX_NEGATIVE_PENALTY = -15
V26_FORCE_SCALP_FOR_CAUTIOUS = False
V26_LEGACY_ALIGNMENT_PENALTY = 15
V26_LEGACY_M3_CONFLICT_PENALTY = 10
V26_LEGACY_M15_CONFLICT_PENALTY = 15
V26_TREND_WALK_RUNNER_MIN_GAP = 4

# V26.6 Expectancy Repair Program
# Enforces runner preservation, compresses realized loss budget metadata,
# enters earlier with graded risk, and treats weak momentum as penalty-only.
V26_6_SCALP_DOWNGRADE_ALLOWED_FLAGS = {
    "EXPLICIT_SCALP_DOWNGRADE",
    "TREND_SCALP_DOWNGRADE",
    "RANGE_REVERSAL",
}
V26_6_LATE_ENTRY_WAIT_SCORE = 80
V26_6_LATE_ENTRY_SIZE_REDUCE_SCORE = 60
V26_6_MAX_REALIZED_LOSS_R_MULTIPLE = 1.05
V26_6_LOSS_GUARD_BUFFER_R = 0.05
V26_6_EARLY_PARTICIPATION_RISK_FRACTIONS = {2: 0.25, 3: 0.50, 4: 1.00}
V26_6_FULL_SIZE_GAP = 4
V26_6_MIN_PARTICIPATION_GAP = 2
V26_6_WEAK_MOMENTUM_PENALTY_ONLY = True

# V26.6.5 Execution Timing Layer
# Directional bias answers "which way?"; this layer answers "when?".
# It reuses existing candle/structure/BB/RSI/MACD telemetry to avoid buying
# into active M1/M3 selling or selling into active M1/M3 buying while preserving
# the HTF bias and participation cadence through WAIT_ENTRY_WINDOW.
V26_6_5_ENTRY_WINDOW_MIN_SCORE = 55
V26_6_5_ACTIVE_COUNTERTREND_SCORE = 45
V26_6_5_STRONG_MACD_COUNTER = 0.80
V26_6_5_RSI_BUY_RECOVERY = 48.0
V26_6_5_RSI_SELL_RECOVERY = 52.0
V26_6_5_RSI_STRONG_COUNTER_BUY = 45.0
V26_6_5_RSI_STRONG_COUNTER_SELL = 55.0

# V26.6.2 Profit/Loss Asymmetry Emergency Fix
# This layer repairs expectancy distribution without adding indicators or new
# strategy branches. It compresses loss size, protects open profit, blocks weak
# marginal gaps, replaces pause-based session brakes with diagnosis, thesis revalidation, and adaptive risk reduction after loss clusters.
V26_6_2_MAX_REALIZED_LOSS_USD_001_LOT = 1.00
V26_6_2_FLOATING_FORCE_EXIT_USD_001_LOT = 0.80
V26_6_2_USD_PER_PRICE_UNIT_001_LOT = 1.00
V26_6_2_MAX_SL_POINTS = round(V26_6_2_MAX_REALIZED_LOSS_USD_001_LOT / V26_6_2_USD_PER_PRICE_UNIT_001_LOT, 3)
# V26 post-entry BE / SL / profit-lock / runner constants are not defined; V27 dashboard owns them.
V26_6_2_EARLY_DAMAGE_CUT_USD_001_LOT = 0.80
V26_6_2_MIN_SCORE_GAP = 3
V26_6_2_TRANSITION_NORMAL_MIN_GAP = 4
V26_6_2_STRONG_MIDDLE_BUY_RSI = 58.0
V26_6_2_STRONG_MIDDLE_SELL_RSI = 42.0
V26_6_2_STRONG_MIDDLE_MACD_ABS = 0.80
V26_6_2_LOSS_CLUSTER_DIAGNOSTIC_SECONDS = 30 * 60
V26_6_2_DAILY_DRAWDOWN_CAUTION_USD = -5.00
V26_6_2_CATASTROPHIC_DAILY_STOP_USD = -5.00
V26_6_2_ADAPTIVE_SIZE_DOWN_FRACTION = 0.25
EMERGENCY_GAP2_PARTICIPATION_SIZE_FACTOR = 0.25
EMERGENCY_GAP2_STRONG_OPPOSITE_MACD = 1.20
V26_6_2_DRAWDOWN_CAUTION_MIN_ENTRY_SCORE = 62
V26_6_3_EXTREME_CAUTION_LOSS_STREAK = 3
V26_6_3_EXTREME_CAUTION_LOSS_CAP_USD_001_LOT = 1.00
V26_6_2_EXPECTANCY_TARGET_AVG_WIN = 1.20
V26_6_2_EXPECTANCY_TARGET_AVG_LOSS = 1.00
V26_6_2_EXPECTANCY_TARGET_PROFIT_FACTOR = 1.30
V26_6_4_EXIT_AUTHORITY_PRIORITY = (
    "EMERGENCY_EXIT",
    "HARD_LOSS_CAP",
    "PROFIT_LOCK",
    "BREAKEVEN",
    "TRAILING",
    "RUNNER",
    "TIME_EXIT",
)
TRADE_MEMORY_PATH = BASE_PATH / "trade_memory.csv"
LOCAL_TRADE_MEMORY_PATH = Path(__file__).resolve().parents[1] / "analysis" / "trade_memory.csv"
LOCAL_SHADOW_AUDIT_PATH = Path(__file__).resolve().parents[1] / "analysis" / "shadow_opposite_audit.json"
V26_6_6_SHADOW_AUDIT_HORIZON_SEC = 15 * 60
V26_6_6_DIRECTION_LOSS_PAUSE_STREAK = 3
V26_6_6_EXHAUSTION_WAIT_SCORE = 80
V26_6_6_EXHAUSTION_SCALP_ONLY_SCORE = 65

# V26.6.1 Protection Authority Manager
# Only one protection state may be ACTIVE at once. Other detected protections are
# PENDING so protective recursion cannot recreate participation starvation.
PROTECTION_AUTHORITY_STATES = (
    "SESSION_PROFIT_PROTECTION",
    "DAILY_PEAK_DRAWDOWN_PROTECTION",
    "THESIS_REVALIDATION_AFTER_LOSS",
    "THESIS_DECAY_WAIT",
    "POST_RUNNER_COOLDOWN",
    "WAIT_ENTRY_LOCATION",
)
PROTECTION_RELEASE_CONDITIONS = {
    "SESSION_PROFIT_PROTECTION": {
        "entry_condition": "session profit lock or profit-protection flag active",
        "exit_condition": "session reset, profit lock released, or maximum duration reached",
        "maximum_duration_sec": 60 * 60,
        "maximum_cycles": 60,
        "recovery_path": "resume normal eligibility on next fresh setup after session protection release",
    },
    "DAILY_PEAK_DRAWDOWN_PROTECTION": {
        "entry_condition": "daily drawdown caution threshold exceeded",
        "exit_condition": "drawdown recovers below threshold, daily reset, or catastrophic hard-risk state is reached",
        "maximum_duration_sec": 60 * 60,
        "maximum_cycles": 60,
        "recovery_path": "continue cautious Leg A-only participation with reduced size and higher entry-quality threshold",
    },
    "THESIS_REVALIDATION_AFTER_LOSS": {
        "entry_condition": "loss cluster or repeated same-direction losses detected",
        "exit_condition": "bias/mode/BB/RSI/MACD/location/exhaustion thesis is revalidated or invalidated",
        "maximum_duration_sec": 3 * 60,
        "maximum_cycles": 3,
        "recovery_path": "valid thesis continues cautiously with reduced risk; invalid thesis switches to WAIT_ENTRY_LOCATION or opposite-thesis evaluation",
    },
    "THESIS_DECAY_WAIT": {
        "entry_condition": "failed continuation threshold, WAIT_VALID, or transition thesis decay",
        "exit_condition": "new directional dominance or wait timeout release",
        "maximum_duration_sec": 10 * 60,
        "maximum_cycles": 10,
        "recovery_path": "release to EXECUTE_CAUTIOUS when directional authority remains valid",
    },
    "POST_RUNNER_COOLDOWN": {
        "entry_condition": "runner/continuation re-entry cooldown active after prior participation",
        "exit_condition": "cooldown timer expires",
        "maximum_duration_sec": 8 * 60,
        "maximum_cycles": 8,
        "recovery_path": "resume continuation evaluation after cooldown expiry",
    },
    "WAIT_ENTRY_LOCATION": {
        "entry_condition": "entry/location score below threshold or late-entry location wait active",
        "exit_condition": "location score recovery to executable threshold",
        "maximum_duration_sec": 6 * 60,
        "maximum_cycles": 6,
        "recovery_path": "release to EXECUTE_CAUTIOUS if directional authority persists after max cycles",
    },
}
PROTECTION_PRIORITY = {state: i for i, state in enumerate(PROTECTION_AUTHORITY_STATES)}
protection_authority_state = {
    "active_state": "NONE",
    "active_since_ts": 0,
    "active_cycles": 0,
    "activation_counts": {state: 0 for state in PROTECTION_AUTHORITY_STATES},
    "opportunity_block_count": 0,
    "recovery_started_ts": 0,
    "last_recovery_sec": 0,
}


V26_FAST_PARTICIPATION_OVERRIDE_ENABLED = True
V26_FAST_PARTICIPATION_MIN_SCORE_GAP = 4
V26_FAST_PARTICIPATION_MAX_MARKET_AGE_SEC = 20
V26_FAST_PARTICIPATION_MIN_BB_CONFIDENCE = 70
V26_DIRECTIONAL_DOMINANCE_ENABLED = True
V26_DOMINANCE_MACD_STRONG_POS = 1.2
V26_DOMINANCE_MACD_STRONG_NEG = -1.2

# V25.6 Spike Pullback Re-entry Logic
SPIKE_PULLBACK_REENTRY_ENABLED = True
SPIKE_REENTRY_TO_MA_POINTS = 3.0
SPIKE_REENTRY_TO_BB_MID_POINTS = 3.0
SPIKE_MIN_SCORE_GAP = 2
SPIKE_REENTRY_MAX_EXHAUSTION_SCORE = 65
spike_pullback_state = {"waiting": False, "bias": "NEUTRAL", "started_ts": 0, "reason": ""}

# V25.5 Structure-Aware Hold Intelligence
STRUCTURE_HOLD_ENABLED = True
DEFAULT_EXIT_STYLE = "STRUCTURE_BE"
DEFAULT_BE_AGGRESSIVENESS = "LOW"
DEFAULT_SWING_ROOM_REQUIRED = True
DEFAULT_MIN_BE_ATR_MULTIPLE = 1.2
DEFAULT_TRAIL_WIDTH_MODE = "WIDE"

# V25.4 BB State Smoothing
BB_SMOOTHING_ENABLED = True
BB_CONFIRM_MIN_SECONDS = 20
BB_CONFIRM_MIN_SAME_RAW_COUNT = 2
BB_REVERSAL_IS_QUALITY_PENALTY_ONLY = True
BB_NORMAL_IS_NOT_HARD_BLOCK = True

bb_smoothing_state = {
    "raw_bb_state": "NORMAL",
    "confirmed_bb_state": "NORMAL",
    "last_raw_bb_state": "NORMAL",
    "raw_state_started_ts": int(time.time()),
    "same_raw_count": 0,
    "flip_count": 0,
    "last_update_ts": int(time.time()),
}

# V25.3 RSI Soft Penalty / Transition Scalp Allow
V25_3_RSI_SOFT_PENALTY_MODE = True
V25_3_ALLOW_TRANSITION_NORMAL_SCALP = True
V25_3_RSI_STRONGLY_OPPOSITE_BUY = 42.0
V25_3_RSI_STRONGLY_OPPOSITE_SELL = 58.0

# V25.2 Final Decision Gate Trace + Strong Signal Override
FINAL_GATE_TRACE_ENABLED = True
STRONG_SIGNAL_OVERRIDE_ENABLED = True
STRONG_SIGNAL_MIN_GAP = 5
STRONG_SIGNAL_MAX_MARKET_AGE_SEC = 20
FINAL_NO_TRADE_ALLOWED_REASONS = [
    "STALE", "COOLDOWN", "SOFT_LOCK", "LOW_RR", "LATE_ENTRY",
    "EXHAUSTION", "SUPPORT_RESISTANCE_BLOCK", "INVALID_SCHEMA",
    "WAIT_PULLBACK", "COMPRESSION", "TRANSITION_WAIT",
    "SR_ENTRY_LOCATION_BLOCK", "EXECUTION_TIMING_BLOCK",
    "EXHAUSTION_COOLDOWN", "TIME_SYNC_STALE"
]

# V25.1 TEMP LIVE EXECUTION MODE
TEMP_LIVE_EXECUTION_MODE = True
TEMP_MARKET_STATE_STALE_LIMIT_SEC = 20
TEMP_DECISION_STALE_TARGET_SEC = 45  # EA side should also be changed 15 -> 45 sec.
TEMP_FORCE_SCALP_ONLY = False
TEMP_RELAX_STYLE_WAIT_BLOCK = True
TEMP_RELAX_SR_RR_BLOCK = True

# V25 Adaptive Market-Style AI — No AO / No ATR
V25_ADAPTIVE_MARKET_STYLE = True
AO_ENABLED = False
ATR_ENABLED = False
DISABLED_INDICATORS = ["AO", "ATR"]

# V25 / EA V20.2 Decision Schema Consistency Fix
VALID_MARKET_MODES = {"TREND", "RANGE", "SPIKE", "TRANSITION"}
VALID_BB_STATES = {"NORMAL", "WALK_UP", "WALK_DOWN", "REVERSAL_UP", "REVERSAL_DOWN", "COMPRESSION", "EXPANSION", "DEV4_UPPER", "DEV4_LOWER"}
VALID_DECISIONS = {"TRADE", "NO_TRADE"}
VALID_BIASES = {"BUY", "SELL", "NEUTRAL"}
VALID_MANAGEMENT = {"SCALP_TP", "HOLD_TRAIL", "TREND_RUNNER", "NO_TRADE", "NORMAL"}
VALID_ACTIONS = {"BUY", "SELL", "WAIT", "NO_TRADE", "NEUTRAL"}
VALID_EXECUTION_STATES = {"EXECUTE_AGGRESSIVE", "EXECUTE_NORMAL", "EXECUTE_CAUTIOUS", "WAIT", "NO_TRADE"}


FINAL_TRACE_PASS = "PASS"
FINAL_TRACE_FAIL = "FAIL"
FINAL_TRACE_SKIPPED = "SKIPPED"
FINAL_TRACE_NA = "NOT_APPLICABLE"
FINAL_TRACE_OVERRIDDEN = "OVERRIDDEN"
FINAL_TRACE_RECOVERED = "RECOVERED"
FINAL_TRACE_EXECUTABLE_STATES = {"TRADE", "TRADE_CAUTIOUS", "EXECUTE_CAUTIOUS", "EXECUTE_NORMAL", "EXECUTE_AGGRESSIVE"}


def _final_trace_decision_state(decision):
    if not isinstance(decision, dict):
        return "INVALID_PAYLOAD"
    published = str(decision.get("decision", "")).upper()
    output = str(decision.get("decision_output_state", "")).upper()
    execution = str(decision.get("execution_state", "")).upper()
    if published == "TRADE":
        return "TRADE"
    if output:
        return output
    if published:
        return published
    return execution or "UNKNOWN"


def _final_trace_is_executable_state(decision):
    if not isinstance(decision, dict):
        return False
    published = str(decision.get("decision", "")).upper()
    execution = str(decision.get("execution_state", "")).upper()
    output = str(decision.get("decision_output_state", "")).upper()
    return published == "TRADE" or execution in FINAL_TRACE_EXECUTABLE_STATES or output in FINAL_TRACE_EXECUTABLE_STATES


def initialize_final_decision_trace(decision):
    """Initialize observability-only final gate trace before late publication gates run."""
    if not isinstance(decision, dict):
        return decision
    buy_score = safe_int(decision.get("buy_score", decision.get("buyScore", 0)), 0)
    sell_score = safe_int(decision.get("sell_score", decision.get("sellScore", 0)), 0)
    dominant = "BUY" if buy_score > sell_score else "SELL" if sell_score > buy_score else "TIE"
    trace = {
        "action": str(decision.get("action", decision.get("intended_action", "UNKNOWN"))).upper(),
        "bias": str(decision.get("bias", "UNKNOWN")).upper(),
        "mode": str(decision.get("market_mode", decision.get("mode", "UNKNOWN"))).upper(),
        "bb_state": str(decision.get("bb_state", decision.get("bb", "UNKNOWN"))).upper(),
        "buy_score": buy_score,
        "sell_score": sell_score,
        "score_gap": abs(buy_score - sell_score),
        "dominant_direction": dominant,
        "initial_decision": _final_trace_decision_state(decision),
        "emergency_gap2_check": str(decision.get("EMERGENCY_GAP2_PARTICIPATION_CHECK", "SKIPPED")).upper(),
        "emergency_gap2_result": "APPROVED" if bool(decision.get("EMERGENCY_GAP2_APPROVED", False)) else (FINAL_TRACE_FAIL if bool(decision.get("EMERGENCY_GAP2_REJECTED", False)) else FINAL_TRACE_SKIPPED),
        "emergency_gap2_reject_reason": str(decision.get("EMERGENCY_GAP2_REJECTED_REASON", "")),
        "trade_cautious_candidate": bool(decision.get("TRADE_CAUTIOUS_FROM_WEAK_GAP", False) or str(decision.get("execution_state", "")).upper() == "EXECUTE_CAUTIOUS" or str(decision.get("decision_output_state", "")).upper() == "TRADE_CAUTIOUS"),
        "transition_gate_result": FINAL_TRACE_NA,
        "entry_location_result": FINAL_TRACE_NA,
        "exhaustion_result": FINAL_TRACE_NA,
        "bb_middle_chop_result": FINAL_TRACE_NA,
        "macd_opposite_result": FINAL_TRACE_NA,
        "soft_lock_result": FINAL_TRACE_NA,
        "wait_entry_window_result": FINAL_TRACE_NA,
        "protection_authority_result": FINAL_TRACE_NA,
        "payload_validation_result": FINAL_TRACE_NA,
        "risk_payload_invariant_result": FINAL_TRACE_NA,
        "executor_contract_result": FINAL_TRACE_NA,
        "final_veto_owner": str(decision.get("final_veto_owner", "NONE") or "NONE"),
        "effective_veto_code": str(decision.get("effective_veto_code", "NONE") or "NONE"),
        "supporting_vetoes": list(decision.get("supporting_vetoes", [])) if isinstance(decision.get("supporting_vetoes", []), list) else [str(decision.get("supporting_vetoes"))],
        "decision_before_final_publish": _final_trace_decision_state(decision),
        "final_published_decision": str(decision.get("decision", "UNKNOWN")).upper(),
        "final_output_state": _final_trace_decision_state(decision),
        "last_executable_candidate": _final_trace_decision_state(decision) if _final_trace_is_executable_state(decision) else "NONE",
        "first_non_executable_stage": "NONE",
        "schema_trade_cautious_compatible": "NOT_NEEDED" if str(decision.get("decision", "")).upper() == "TRADE" and (bool(decision.get("TRADE_CAUTIOUS_FROM_WEAK_GAP", False)) or str(decision.get("execution_state", "")).upper() == "EXECUTE_CAUTIOUS") else ("TRADE_CAUTIOUS" in VALID_DECISIONS),
        "downstream_executable_states": sorted(VALID_DECISIONS),
        "downstream_trade_cautious_recognized": "NOT_NEEDED" if str(decision.get("decision", "")).upper() == "TRADE" and (bool(decision.get("TRADE_CAUTIOUS_FROM_WEAK_GAP", False)) or str(decision.get("execution_state", "")).upper() == "EXECUTE_CAUTIOUS") else ("TRADE_CAUTIOUS" in VALID_DECISIONS),
        "stage_events": [],
    }
    decision["FINAL_DECISION_TRACE"] = trace
    return decision


def record_final_decision_trace_stage(decision, stage_name, before=None):
    """Record one publication gate outcome without changing decision logic."""
    if not isinstance(decision, dict):
        return decision
    trace = decision.setdefault("FINAL_DECISION_TRACE", {})
    before_state = _final_trace_decision_state(before) if isinstance(before, dict) else "UNKNOWN"
    after_state = _final_trace_decision_state(decision)
    before_exec = _final_trace_is_executable_state(before) if isinstance(before, dict) else False
    after_exec = _final_trace_is_executable_state(decision)
    status = FINAL_TRACE_PASS
    if before_exec and not after_exec:
        status = FINAL_TRACE_OVERRIDDEN
        if not trace.get("first_non_executable_stage") or trace.get("first_non_executable_stage") == "NONE":
            trace["first_non_executable_stage"] = stage_name
            trace["first_non_executable_state"] = after_state
    elif (not before_exec) and after_exec:
        status = FINAL_TRACE_RECOVERED
    elif not after_exec and str(decision.get("decision", "")).upper() in ("NO_TRADE", "WAIT_VALID"):
        status = FINAL_TRACE_FAIL
    if after_exec:
        trace["last_executable_candidate"] = after_state
    event = {
        "stage": stage_name,
        "result": status,
        "before": before_state,
        "after": after_state,
        "decision": str(decision.get("decision", "UNKNOWN")).upper(),
        "execution_state": str(decision.get("execution_state", "UNKNOWN")).upper(),
        "decision_output_state": str(decision.get("decision_output_state", "UNKNOWN")).upper(),
        "veto_owner": str(decision.get("final_veto_owner", decision.get("blocking_module", "NONE")) or "NONE"),
        "veto_code": str(decision.get("effective_veto_code", decision.get("no_trade_reason", "NONE")) or "NONE"),
        "reason": str(decision.get("wait_reason", decision.get("payload_validation_reason", decision.get("final_veto_reason", ""))) or ""),
    }
    trace.setdefault("stage_events", []).append(event)
    field_map = {
        "transition_gate": "transition_gate_result",
        "entry_location": "entry_location_result",
        "exhaustion_protection": "exhaustion_result",
        "expectancy_entry_filter": "bb_middle_chop_result",
        "execution_timing_layer": "wait_entry_window_result",
        "protection_authority_manager": "protection_authority_result",
        "payload_validation": "payload_validation_result",
        "risk_payload_invariant": "risk_payload_invariant_result",
        "executor_authority_contract": "executor_contract_result",
    }
    key = field_map.get(stage_name)
    if key:
        trace[key] = status
    trace["soft_lock_result"] = FINAL_TRACE_FAIL if str(decision.get("soft_lock_state", "")).upper() in ("TREND_LOCK", "TRANSITION_WAIT") else trace.get("soft_lock_result", FINAL_TRACE_NA)
    trace["macd_opposite_result"] = FINAL_TRACE_FAIL if "MACD" in str(decision.get("EMERGENCY_GAP2_REJECTED_REASON", decision.get("reason", ""))).upper() and "OPPOSITE" in str(decision.get("EMERGENCY_GAP2_REJECTED_REASON", decision.get("reason", ""))).upper() else trace.get("macd_opposite_result", FINAL_TRACE_NA)
    trace["final_veto_owner"] = str(decision.get("final_veto_owner", decision.get("blocking_module", "NONE")) or "NONE")
    trace["effective_veto_code"] = str(decision.get("effective_veto_code", decision.get("no_trade_reason", "NONE")) or "NONE")
    sv = decision.get("supporting_vetoes", trace.get("supporting_vetoes", []))
    trace["supporting_vetoes"] = sv if isinstance(sv, list) else [str(sv)]
    trace["final_published_decision"] = str(decision.get("decision", "UNKNOWN")).upper()
    trace["final_output_state"] = after_state
    print("FINAL_DECISION_TRACE", json.dumps(trace, sort_keys=True))
    return decision
decision_sequence_counter = int(time.time())

# V25 RP TIME SYNC STANDARD V1
TIME_SYNC_STANDARD = "RP_TIME_SYNC_STANDARD_V1"
MARKET_STATE_STALE_LIMIT_SEC = TEMP_MARKET_STATE_STALE_LIMIT_SEC

# V25 Fresh Market State Read Fix
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
SOFT_LOCK_BUY_RSI_WEAK = 51.0
SOFT_LOCK_SELL_RSI_WEAK = 49.0
SOFT_LOCK_MACD_WEAK_BUFFER = 0.08
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

# V25 TREND WALK Override
# Goal: BB WALK continuation should not be blocked by score_gap alone.
TREND_WALK_OVERRIDE_ENABLED = True
TREND_WALK_SELL_MIN_EDGE = 1
TREND_WALK_BUY_MIN_EDGE = 1
TREND_WALK_SELL_RSI_MAX = 45.0
TREND_WALK_BUY_RSI_MIN = 55.0
TREND_WALK_SELL_MACD_MAX = -1.5
TREND_WALK_BUY_MACD_MIN = 1.5

# V25 TREND NORMAL Continuation Override
# Goal: TREND + BB NORMAL continuation should not be blocked by adaptive score gap alone
# when RSI/MACD and Soft Direction Lock confirm the trend direction.
TREND_NORMAL_CONTINUATION_ENABLED = True
TREND_NORMAL_SELL_MIN_EDGE = 1
TREND_NORMAL_BUY_MIN_EDGE = 1
TREND_NORMAL_SELL_RSI_MAX = 42.0
TREND_NORMAL_BUY_RSI_MIN = 58.0
TREND_NORMAL_SELL_MACD_MAX = -1.0
TREND_NORMAL_BUY_MACD_MIN = 1.0

# V25 Strong Trend Continuation Cooldown Override
# Allows one strong BB WALK continuation signal per new bar even if normal cooldown/max gate blocks.
STRONG_CONTINUATION_COOLDOWN_OVERRIDE_ENABLED = True
STRONG_CONTINUATION_MIN_GAP = 5
STRONG_CONTINUATION_BUY_MIN_RSI = 55.0
STRONG_CONTINUATION_SELL_MAX_RSI = 45.0
STRONG_CONTINUATION_BUY_MIN_MACD = 0.0
STRONG_CONTINUATION_SELL_MAX_MACD = 0.0
strong_continuation_bar_used = {}

# V25 Candle Intelligence Layer V1
CANDLE_INTELLIGENCE_ENABLED = True
CANDLE_LOOKBACK_DEFAULT = 8
CANDLE_MIN_TREND_QUALITY = 45
CANDLE_LATE_CONTINUATION_BLOCK_QUALITY = 40
CANDLE_EXHAUSTION_BLOCK_LEVEL = 70
CANDLE_WICK_REJECTION_RATIO = 0.55
CANDLE_SMALL_BODY_RATIO = 0.35
CANDLE_BODY_MOMENTUM_RATIO = 0.55

# V25 TREND NORMAL Momentum Override
TREND_NORMAL_MOMENTUM_OVERRIDE_ENABLED = True
TREND_NORMAL_MOMENTUM_MIN_EDGE = 1
TREND_NORMAL_MOMENTUM_SELL_RSI_MAX = 43.0
TREND_NORMAL_MOMENTUM_BUY_RSI_MIN = 57.0
TREND_NORMAL_MOMENTUM_SELL_MACD_MAX = -1.50
TREND_NORMAL_MOMENTUM_BUY_MACD_MIN = 1.50
TREND_NORMAL_MOMENTUM_ALLOW_MIDDLE_IF_MACD_STRONG = True

# V25 Transition Decay Logic V1
# Soft Lock should not flip to TRANSITION_WAIT on one weak tick/candle.
TRANSITION_DECAY_ENABLED = True
TRANSITION_DECAY_REQUIRED_COUNT = 4
TRANSITION_DECAY_RESET_ON_STRONG_SCORE = True
TRANSITION_DECAY_STRONG_SCORE_GAP = 4
TRANSITION_DECAY_BUY_RSI_RECOVER = 53.0
TRANSITION_DECAY_SELL_RSI_RECOVER = 47.0
TRANSITION_DECAY_BUY_MACD_RECOVER = 0.25
TRANSITION_DECAY_SELL_MACD_RECOVER = -0.25
transition_decay_state = {}
transition_wait_release_state = {}
wait_valid_state = {}

# V25.1 Soft Lock Counter Reset
SOFT_LOCK_COUNTER_RESET_ENABLED = True
SOFT_LOCK_COUNTER_MAX_KEEP = 12
SOFT_LOCK_COUNTER_EXPIRE_SECONDS = 180
SOFT_LOCK_RESET_ON_NEW_BAR = True
transition_decay_meta = {}

# V25 Fresh Market State + Soft Lock Stale Reset
FRESH_STATE_RESET_ENABLED = True
FRESH_STATE_TS_CHANGE_SECONDS = 60
FRESH_STATE_MACD_FLIP_EPS = 0.05
fresh_state_snapshot = {}

# V25 Trend Exhaustion Detection
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

# V25 Market Structure + Exhaustion Master Gate
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

# V25 Pullback Continuation Engine
PULLBACK_ENGINE_ENABLED = True
PULLBACK_LOOKBACK = 8
PULLBACK_MIN_QUALITY = 55
PULLBACK_ALLOW_RUNNER_QUALITY = 75
# V25 Pullback Fallback Mode
PULLBACK_FALLBACK_ALLOW_IF_NO_CANDLES = True
PULLBACK_MIN_CANDLE_HISTORY = 4

# V25 Execution Timing Intelligence
EXEC_TIMING_ENABLED = True
DISABLE_RUNNER_TEMPORARILY = False
LATE_ENTRY_BLOCK_SCORE = 70
EXHAUSTION_BLOCK_SCORE = 75
EXHAUSTION_COOLDOWN_SECONDS = 20 * 60
CONTINUATION_REENTRY_COOLDOWN_SECONDS = 8 * 60
DIST_MA50_EXTREME_PCT = 0.0025
DIST_BB_MID_EXTREME_RATIO = 0.70
RSI_BUY_BLOWOFF = 72
RSI_SELL_BLOWOFF = 28
MACD_DECAY_ABS_WEAK = 0.35
VERTICAL_BB_EDGE_RATIO = 0.82
execution_timing_state = {"cooldown_until": 0, "cooldown_reason": "", "last_continuation_entry_ts": 0, "last_bias": "NEUTRAL"}

# V25 Support/Resistance + Entry Location Intelligence
SR_ENTRY_LOCATION_ENABLED = True
SR_REPORT_MODE_ONLY = False
SR_MIN_REWARD_RISK_RATIO = 1.20
SR_NEAR_LEVEL_POINTS = 2.5
SR_DANGER_LEVEL_POINTS = 1.2
ENTRY_LOCATION_BLOCK_SCORE = 35
REMAINING_REWARD_LOW_POINTS = 2.5
DEFAULT_RISK_POINTS = 3.5
PULLBACK_MAX_DEPTH_PCT = 0.62
PULLBACK_SHALLOW_DEPTH_PCT = 0.28
PULLBACK_MEDIUM_DEPTH_PCT = 0.45
PULLBACK_CONTINUATION_MIN_QUALITY = 60
PULLBACK_BLOCK_LATE_EXPANSION = True
PULLBACK_EXPANSION_BODY_RATIO = 0.62
PULLBACK_EXPANSION_COUNT_BLOCK = 3
PULLBACK_REJECTION_WICK_RATIO = 0.45
PULLBACK_MOMENTUM_BODY_RATIO = 0.55

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
    V25 helper.
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


def _fast_participation_override_allowed(decision, data):
    if not V26_FAST_PARTICIPATION_OVERRIDE_ENABLED:
        return False, "FAST_PARTICIPATION_DISABLED"
    decision_state = str(decision.get("decision", "")).upper()
    intended = str(decision.get("action", decision.get("bias", decision.get("intended_action", "")))).upper()
    if decision_state != "TRADE" and intended not in ("BUY", "SELL"):
        return False, "FAST_PARTICIPATION_NO_DIRECTIONAL_INTENT"
    if str(decision.get("market_mode", "")).upper() not in ("TREND", "TRANSITION"):
        return False, "FAST_PARTICIPATION_NOT_TREND_OR_TRANSITION"

    bb_state = str(decision.get("bb_state", "")).upper()
    if bb_state not in ("WALK_UP", "WALK_DOWN", "NORMAL"):
        return False, f"FAST_PARTICIPATION_BB_INVALID:{bb_state}"

    buy_score = safe_int(decision.get("buy_score", decision.get("buyScore", 0)), 0)
    sell_score = safe_int(decision.get("sell_score", decision.get("sellScore", 0)), 0)
    score_gap = abs(buy_score - sell_score)
    if score_gap < V26_FAST_PARTICIPATION_MIN_SCORE_GAP:
        return False, f"FAST_PARTICIPATION_WEAK_GAP:{score_gap}"

    bb_confidence = safe_int(decision.get("bb_confidence", data.get("bb_confidence", 0)), 0)
    if bb_confidence < V26_FAST_PARTICIPATION_MIN_BB_CONFIDENCE:
        return False, f"FAST_PARTICIPATION_LOW_BB_CONF:{bb_confidence}"

    if not bool(decision.get("market_state_fresh", True)):
        return False, "FAST_PARTICIPATION_STALE_MARKET_STATE"

    market_age = safe_int(data.get("market_state_age_sec", decision.get("market_state_age_sec", 9999)), 9999)
    if market_age > V26_FAST_PARTICIPATION_MAX_MARKET_AGE_SEC:
        return False, f"FAST_PARTICIPATION_MARKET_AGE:{market_age}"

    if not bool(decision.get("payload_valid", True)):
        return False, "FAST_PARTICIPATION_INVALID_PAYLOAD"

    if str(decision.get("hard_block", "")).upper() in ("TRUE", "1", "YES"):
        return False, "FAST_PARTICIPATION_HARD_BLOCK"

    return True, f"FAST_PARTICIPATION_OK gap={score_gap} bb_conf={bb_confidence} age={market_age}s"


def detect_directional_dominance(data, decision=None):
    """
    V26.4.4 directional dominance classifier dilution fix.
    Detect strong directional context so weak opposite micro-signals cannot collapse to NEUTRAL/NO_TRADE.
    """
    if not V26_DIRECTIONAL_DOMINANCE_ENABLED or not isinstance(data, dict):
        return None, ""

    mode = str(data.get("market_mode", data.get("mode", "") if isinstance(data, dict) else "")).upper()
    bb = str(data.get("bb_state", data.get("bb", "") if isinstance(data, dict) else "")).upper()
    rsi = safe_float(data.get("rsi", 50), 50)
    macd_hist = safe_float(data.get("macd_hist", 0), 0)
    fresh = bool(data.get("market_state_fresh", True))
    market_age = safe_int(data.get("market_state_age_sec", 0), 0)
    hard_block = str(data.get("hard_block", "")).upper() in ("TRUE", "1", "YES")

    buy_score = safe_int(data.get("buy_score", data.get("buyScore", 0)), 0)
    sell_score = safe_int(data.get("sell_score", data.get("sellScore", 0)), 0)
    if isinstance(decision, dict):
        buy_score = safe_int(decision.get("buy_score", decision.get("buyScore", buy_score)), buy_score)
        sell_score = safe_int(decision.get("sell_score", decision.get("sellScore", sell_score)), sell_score)

    if mode not in ("SPIKE", "TREND"):
        return None, "mode not dominance"
    if not fresh or market_age > TEMP_MARKET_STATE_STALE_LIMIT_SEC:
        return None, f"market not fresh age={market_age}"
    if hard_block:
        return None, "hard safety block active"

    if (
        bb in ("REVERSAL_DOWN", "WALK_DOWN")
        and rsi <= 30.0
        and macd_hist <= V26_DOMINANCE_MACD_STRONG_NEG
        and sell_score >= buy_score
    ):
        return "SELL", f"DOMINANCE_SELL mode={mode} bb={bb} rsi={rsi:.2f} macd={macd_hist:.2f} scores={buy_score}/{sell_score}"

    if (
        bb in ("REVERSAL_UP", "WALK_UP")
        and rsi >= 70.0
        and macd_hist >= V26_DOMINANCE_MACD_STRONG_POS
        and buy_score >= sell_score
    ):
        return "BUY", f"DOMINANCE_BUY mode={mode} bb={bb} rsi={rsi:.2f} macd={macd_hist:.2f} scores={buy_score}/{sell_score}"

    return None, "no dominance"


def can_fire_or_strong_override(key, bar_time, decision, data):
    """
    V26.4.2 cooldown/max-signal gate.
    If normal fire blocks, allow controlled continuation participation via strong/fast overrides.
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
    fast_ok, fast_reason = _fast_participation_override_allowed(decision, data)
    if not ok and not fast_ok:
        return False, f"{reason} | {fast_reason}"

    override_type = "STRONG_CONTINUATION" if ok else "FAST_PARTICIPATION"
    override_reason = reason if ok else fast_reason
    override_key = f"{bar_time}|{decision.get('bias','')}|{bb_state}|{override_type}"
    if strong_continuation_bar_used.get(override_key, False):
        return False, f"{override_type} already used this bar | {override_key}"

    strong_continuation_bar_used.clear()
    strong_continuation_bar_used[override_key] = True
    decision["cooldown_override"] = True
    decision["cooldown_override_reason"] = override_reason
    decision["fast_participation_override"] = bool(fast_ok)
    decision["fast_participation_override_reason"] = fast_reason if fast_ok else ""
    decision["reason"] = f"{decision.get('reason', '')} | {override_reason}".strip()
    return True, override_reason


def build_cooldown_wait_decision(decision, data, fire_reason, cycle_start):
    """
    Build a cooldown/max-signal blocked decision that preserves directional context.
    Cooldown suppression is represented as WAIT governance, not generic NEUTRAL collapse.
    """
    blocked_decision = no_trade(f"COOLDOWN_MAX_SIGNAL_BLOCK | {fire_reason}")
    blocked_decision["decision"] = "TRADE"
    blocked_decision["market_mode"] = decision.get("market_mode", "UNKNOWN")
    blocked_decision["bb_state"] = decision.get("bb_state", "UNKNOWN")
    blocked_decision["heartbeat_unix"] = safe_int(data.get("heartbeat_unix", 0), 0)
    blocked_decision["sequence_id"] = safe_int(data.get("sequence_id", 0), 0)
    blocked_decision["market_state_sequence_id"] = safe_int(data.get("sequence_id", 0), 0)
    blocked_decision["market_state_age_sec"] = safe_int(data.get("market_state_age_sec", -1), -1)
    blocked_decision["decision_age_sec"] = 0
    blocked_decision["time_sync_standard"] = TIME_SYNC_STANDARD
    blocked_decision["cooldown_wait_active"] = True
    blocked_decision["cooldown_active"] = True
    blocked_decision["suppression_active"] = True
    blocked_decision["cooldown_wait_reason"] = str(fire_reason)
    blocked_decision["directional_dominance_active"] = bool(decision.get("directional_dominance_active", False))
    blocked_decision["directional_dominance_bias"] = str(decision.get("directional_dominance_bias", "NONE"))
    blocked_decision["directional_dominance_reason"] = str(decision.get("directional_dominance_reason", ""))

    src_bias = str(decision.get("bias", "NEUTRAL")).upper()
    src_action = str(decision.get("action", src_bias)).upper()
    buy_score = safe_int(decision.get("buy_score", decision.get("buyScore", 0)), 0)
    sell_score = safe_int(decision.get("sell_score", decision.get("sellScore", 0)), 0)
    score_gap = abs(buy_score - sell_score)

    if src_action in ("BUY", "SELL") and src_bias in ("BUY", "SELL"):
        blocked_decision["bias"] = src_bias
        blocked_decision["action"] = src_action
        blocked_decision["intended_action"] = src_action
        blocked_decision["manual_action"] = f"{src_bias}_BIAS_WAIT_COOLDOWN"
    blocked_decision["buy_score"] = buy_score
    blocked_decision["sell_score"] = sell_score
    blocked_decision["buyScore"] = buy_score
    blocked_decision["sellScore"] = sell_score
    blocked_decision["score_gap"] = score_gap
    entry_price = safe_float(decision.get("entry_price", decision.get("price", decision.get("bid", data.get("bid", 0)))), 0.0)
    if entry_price > 0:
        blocked_decision["entry_price"] = round(entry_price, 3)
        blocked_decision["price"] = round(entry_price, 3)
        blocked_decision["bid"] = round(entry_price, 3)
    blocked_decision["entry_timing"] = "WAIT_COOLDOWN_CONTINUATION"
    blocked_decision["pullback_state"] = "REPORT_ONLY"
    blocked_decision["execution_state"] = "WAIT"
    blocked_decision["reason"] = (str(blocked_decision.get("reason", "")) + " | COOLDOWN_WAIT_BIAS_PRESERVED").strip()
    blocked_decision["loop_duration_sec"] = round(time.time() - cycle_start, 6)
    blocked_decision["stale_prevention_timing_sec"] = blocked_decision["loop_duration_sec"]
    return blocked_decision


def read_market():
    """
    V25 Fresh Market State Read Fix.

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
            data = apply_time_sync_fields(data)
            data = apply_v25_indicator_minimalism(data)
            data = apply_bb_state_smoothing_v25_4(data)

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
                    f"heartbeat_unix={data.get('heartbeat_unix', 0)}",
                    f"sequence_id={data.get('sequence_id', 0)}",
                    f"market_state_age_sec={data.get('market_state_age_sec', -1)}",
                    f"time_sync={data.get('time_sync_standard', '')}",
                    f"raw_bb_state={data.get('raw_bb_state', '')}",
                    f"confirmed_bb_state={data.get('confirmed_bb_state', '')}",
                    f"bb_state_age_sec={data.get('bb_state_age_sec', 0)}",
                    f"bb_flip_count={data.get('bb_flip_count', 0)}",
                    f"bb_confidence={data.get('bb_confidence', 0)}",
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



def apply_time_sync_fields(data):
    """
    RP TIME SYNC STANDARD V1:
    Reads heartbeat_unix and sequence_id from market_state.json and adds freshness fields.
    """
    now_unix = int(time.time())
    heartbeat_unix = safe_int(data.get("heartbeat_unix", 0), 0)
    sequence_id = safe_int(data.get("sequence_id", 0), 0)

    # If heartbeat is missing, use -1 as unknown. This avoids breaking old Writer builds.
    if heartbeat_unix > 0:
        market_state_age_sec = max(0, now_unix - heartbeat_unix)
    else:
        market_state_age_sec = -1

    data["heartbeat_unix"] = heartbeat_unix
    data["sequence_id"] = sequence_id
    data["market_state_sequence_id"] = sequence_id
    data["market_state_age_sec"] = market_state_age_sec
    data["decision_age_sec"] = 0
    data["time_sync_standard"] = TIME_SYNC_STANDARD
    return data


def is_market_state_stale_by_time_sync(data):
    heartbeat_unix = safe_int(data.get("heartbeat_unix", 0), 0)
    age = safe_int(data.get("market_state_age_sec", -1), -1)
    return heartbeat_unix > 0 and age > MARKET_STATE_STALE_LIMIT_SEC


def time_sync_no_trade(data, market_mode="UNKNOWN", bb_state="UNKNOWN"):
    age = safe_int(data.get("market_state_age_sec", -1), -1)
    sequence_id = safe_int(data.get("sequence_id", 0), 0)
    decision_data = no_trade(f"MARKET_STATE_STALE | age={age}s sequence_id={sequence_id}", market_mode, bb_state)
    decision_data["entry_allowed"] = False
    decision_data["heartbeat_unix"] = safe_int(data.get("heartbeat_unix", 0), 0)
    decision_data["sequence_id"] = sequence_id
    decision_data["market_state_sequence_id"] = sequence_id
    decision_data["market_state_age_sec"] = age
    decision_data["decision_age_sec"] = 0
    decision_data["time_sync_standard"] = TIME_SYNC_STANDARD
    return decision_data


def _schema_clean_str(value, default=""):
    if value is None:
        return default
    s = str(value).strip().upper()
    return s if s else default



def apply_v25_indicator_minimalism(data):
    """
    Disable AO and ATR as active decision inputs.
    Keep raw values for audit only.
    """
    if not isinstance(data, dict):
        return data
    data["v25_adaptive_market_style"] = True
    data["ao_enabled"] = False
    data["atr_enabled"] = False
    data["disabled_indicators"] = DISABLED_INDICATORS
    if "ao" in data and "ao_raw" not in data:
        data["ao_raw"] = data.get("ao")
    if "ao_value" in data and "ao_value_raw" not in data:
        data["ao_value_raw"] = data.get("ao_value")
    if "atr" in data and "atr_raw" not in data:
        data["atr_raw"] = data.get("atr")
    if "atr_value" in data and "atr_value_raw" not in data:
        data["atr_value_raw"] = data.get("atr_value")
    data["ao"] = 0
    data["ao_value"] = 0
    data["atr"] = 0
    data["atr_value"] = 0
    data["indicator_minimalism_note"] = "AO/ATR disabled; use PA/Structure/SR/BB/RSI/MACD/TickVolume"
    return data


def attach_v25_adaptive_style_fields(decision):
    """
    V25 adaptive market-style diagnostic + safety layer.
    Does not add AO/ATR logic.
    Runner remains disabled until timing/location is stable.
    """
    if not isinstance(decision, dict):
        decision = {}

    decision["v25_adaptive_market_style"] = True
    decision["ao_enabled"] = False
    decision["atr_enabled"] = False
    decision["disabled_indicators"] = DISABLED_INDICATORS
    decision["temp_live_execution_mode"] = TEMP_LIVE_EXECUTION_MODE
    decision["temp_market_state_stale_limit_sec"] = TEMP_MARKET_STATE_STALE_LIMIT_SEC
    decision["temp_decision_stale_target_sec"] = TEMP_DECISION_STALE_TARGET_SEC

    mode = str(decision.get("market_mode", decision.get("mode", "TRANSITION"))).upper()
    bb = str(decision.get("bb_state", decision.get("bb", "NORMAL"))).upper()
    timing = str(decision.get("execution_timing_state", "")).upper()
    location = str(decision.get("entry_location_state", "")).upper()
    exhaustion = str(decision.get("exhaustion_state", "")).upper()

    if exhaustion == "HIGH" or timing == "LATE_CONTINUATION":
        regime = "EXHAUSTION"
    elif mode == "SPIKE":
        regime = "MOMENTUM_BURST"
    elif mode == "TREND":
        regime = "TREND"
    elif mode == "RANGE":
        regime = "RANGE"
    elif mode == "TRANSITION":
        regime = "TRANSITION"
    else:
        regime = "TRANSITION"

    if regime in ("EXHAUSTION", "REVERSAL_RISK", "COMPRESSION") or location == "BAD_LOCATION":
        style = "WAIT"
    elif regime == "MOMENTUM_BURST":
        style = "MOMENTUM_TRADING"
    elif regime == "TREND":
        style = "INTRADAY_SWING"
    elif regime == "RANGE":
        style = "SCALP"
    else:
        style = "WAIT"

    decision["market_regime_v25"] = regime
    decision["market_style"] = style
    decision["style_selector_reason"] = (
        f"regime={regime}; mode={mode}; bb={bb}; timing={timing}; "
        f"location={location}; exhaustion={exhaustion}; AO/ATR disabled"
    )

    if str(decision.get("management", "")).upper() in ("HOLD_TRAIL", "TREND_RUNNER"):
        decision["runner_disabled"] = False
        decision["runner_disable_reason"] = ""
        decision["runner_preserved_reason"] = "V26.5 expectancy repair: trend runner management is no longer downgraded to SCALP_TP"

    if style == "WAIT" and decision.get("decision") == "TRADE":
        high_risk_wait = (
            str(decision.get("entry_location_state", "")).upper() == "BAD_LOCATION"
            or str(decision.get("exhaustion_state", "")).upper() == "HIGH"
            or str(decision.get("execution_timing_state", "")).upper() == "LATE_CONTINUATION"
        )
        if high_risk_wait or not TEMP_RELAX_STYLE_WAIT_BLOCK:
            decision["decision"] = "NO_TRADE"
            decision["entry_allowed"] = False
            decision["management"] = "NO_TRADE"
            decision["mgmt"] = "NO_TRADE"
            decision["reason"] = (str(decision.get("reason", "")) + " | V25_1_STYLE_WAIT_HIGH_RISK_BLOCK").strip()
        else:
            decision["market_style"] = "SCALP"
            decision["management"] = "SCALP_TP"
            decision["mgmt"] = "SCALP_TP"
            decision["reason"] = (str(decision.get("reason", "")) + " | V25_1_WAIT_RELAXED_TO_SCALP").strip()


    if TEMP_FORCE_SCALP_ONLY and decision.get("decision") == "TRADE":
        decision["management"] = "SCALP_TP"
        decision["mgmt"] = "SCALP_TP"
        decision["runner_disabled"] = True
        decision["runner_disable_reason"] = "V25.1 temp live mode: runner disabled for dataset collection"
        decision["V25_1_TEMP_FORCE_SCALP_ONLY"] = True

    return decision


def _v25_2_int(v, default=0):
    try:
        return int(v)
    except Exception:
        return default


def _v25_2_float(v, default=0.0):
    try:
        return float(v)
    except Exception:
        return default


def get_signal_snapshot_v25_2(decision):
    buy = _v25_2_int(decision.get("buy_score", decision.get("buyScore", 0)), 0)
    sell = _v25_2_int(decision.get("sell_score", decision.get("sellScore", 0)), 0)
    action = str(decision.get("action", decision.get("bias", "NEUTRAL"))).upper()
    bias = str(decision.get("bias", action)).upper()
    mode = str(decision.get("market_mode", decision.get("mode", "TRANSITION"))).upper()
    bb = str(decision.get("bb_state", decision.get("bb", "NORMAL"))).upper()
    gap = abs(buy - sell)
    inferred = "BUY" if buy > sell else "SELL" if sell > buy else "NEUTRAL"
    return {
        "buy_score": buy,
        "sell_score": sell,
        "score_gap": gap,
        "action": action,
        "bias": bias,
        "inferred_bias": inferred,
        "market_mode": mode,
        "bb_state": bb,
    }


def has_specific_no_trade_reason_v25_2(decision):
    reason = str(decision.get("reason", "") or decision.get("final_gate_reason", "")).upper()
    if not reason.strip():
        return False, "GENERIC_NO_TRADE_EMPTY_REASON"
    for key in FINAL_NO_TRADE_ALLOWED_REASONS:
        if key in reason:
            return True, key
    return False, "GENERIC_NO_TRADE_UNCLASSIFIED_REASON"


def is_strong_signal_v25_2(decision):
    s = get_signal_snapshot_v25_2(decision)
    age = _v25_2_int(decision.get("market_state_age_sec", 999), 999)
    mode_valid = s["market_mode"] in VALID_MARKET_MODES if "VALID_MARKET_MODES" in globals() else s["market_mode"] not in ("UNKNOWN", "")
    bb_valid = s["bb_state"] in VALID_BB_STATES if "VALID_BB_STATES" in globals() else s["bb_state"] not in ("UNKNOWN", "")
    strong_bias = s["inferred_bias"] in ("BUY", "SELL")
    action_match = s["bias"] == s["inferred_bias"] or s["action"] == s["inferred_bias"] or s["bias"] in ("BUY", "SELL")
    return (
        strong_bias
        and s["score_gap"] >= STRONG_SIGNAL_MIN_GAP
        and age <= STRONG_SIGNAL_MAX_MARKET_AGE_SEC
        and mode_valid
        and bb_valid
        and action_match
    ), s




def _bb_clean_state_v25_4(value):
    s = str(value or "NORMAL").strip().upper()
    if s in ("", "UNKNOWN", "NONE", "NULL"):
        return "NORMAL"
    return s




def _v25_6_bias_from_scores(decision):
    buy = safe_int(decision.get("buy_score", decision.get("buyScore", 0)), 0)
    sell = safe_int(decision.get("sell_score", decision.get("sellScore", 0)), 0)
    if buy > sell:
        return "BUY", buy, sell, buy - sell
    if sell > buy:
        return "SELL", buy, sell, sell - buy
    return str(decision.get("bias", "NEUTRAL")).upper(), buy, sell, 0


def _v25_6_reentry_zone_distance(data, decision):
    bid = safe_float(data.get("bid", decision.get("price", 0)), 0)
    levels = [
        ("MA30", safe_float(data.get("ma30", decision.get("ma30", 0)), 0), SPIKE_REENTRY_TO_MA_POINTS),
        ("MA50", safe_float(data.get("ma50", decision.get("ma50", 0)), 0), SPIKE_REENTRY_TO_MA_POINTS),
        ("BB_MID", safe_float(data.get("bb_middle", data.get("bb_mid", decision.get("bb_mid", 0))), 0), SPIKE_REENTRY_TO_BB_MID_POINTS),
    ]
    best = ("NONE", 999999.0, 0)
    for name, level, threshold in levels:
        if bid > 0 and level > 0:
            dist = abs(bid - level)
            if dist < best[1]:
                best = (name, dist, threshold)
    return best



def _v26_safe_upper(v, default=""):
    s = str(v if v is not None else default).strip().upper()
    return s if s else default


def _v26_clamp_score(x):
    return clamp_int(int(x), 0, 100)


def _v26_score_from_direction(decision):
    buy = safe_int(decision.get("buy_score", decision.get("buyScore", 0)), 0)
    sell = safe_int(decision.get("sell_score", decision.get("sellScore", 0)), 0)
    if buy > sell:
        return "BUY", buy, sell, buy - sell
    if sell > buy:
        return "SELL", buy, sell, sell - buy
    bias = _v26_safe_upper(decision.get("bias", "NEUTRAL"), "NEUTRAL")
    return bias, buy, sell, abs(buy - sell)


def _v26_has_hard_block(decision):
    """
    V26 keeps only true safety hard blocks.
    Strategy/timing concerns should become score penalties.
    """
    reason = _v26_safe_upper(decision.get("reason", "") + " " + decision.get("final_gate_reason", ""), "")
    hard_terms = [
        "TIME_SYNC_STALE",
        "MARKET_STATE_STALE",
        "INVALID_SCHEMA",
        "INVALID_DECISION_JSON",
        "CORRUPT",
        "FILE",
        "ABNORMAL_SPREAD",
        "NO_LIQUIDITY",
        "BROKER_FREEZE",
        "INVALID_MARKET_DATA",
        "DAILY_LOSS",
        "HARD_RISK",
        "DUPLICATE_ORDER",
        "INSUFFICIENT_MARGIN",
        "MARKET_CLOSED",
        "CATASTROPHIC_RISK",
    ]
    for term in hard_terms:
        if term in reason:
            return True, term

    age = safe_int(decision.get("market_state_age_sec", 999), 999)
    if age > TEMP_MARKET_STATE_STALE_LIMIT_SEC:
        return True, f"MARKET_STATE_STALE age={age}"

    mode = _v26_safe_upper(decision.get("market_mode", decision.get("mode", "")), "")
    bb = _v26_safe_upper(decision.get("bb_state", decision.get("bb", "")), "")
    if mode in ("", "UNKNOWN", "NONE") or bb in ("", "UNKNOWN", "NONE"):
        return True, "INVALID_SCHEMA_MODE_BB"

    return False, ""


def _ai_authority_valid(decision, buy_score=None, sell_score=None):
    """
    V26.5 expectancy repair authority check.

    Once AI publishes a valid directional TRADE intent and hard safety is clear,
    legacy quality paths may add penalties but must not silently convert the idea
    into NO_TRADE. Final hard stops remain infrastructure/risk only.
    """
    if not isinstance(decision, dict):
        return False, "AI_AUTHORITY_INVALID_PAYLOAD"
    if str(decision.get("decision", "")).upper() != "TRADE":
        return False, "AI_AUTHORITY_NOT_TRADE"
    bias = str(decision.get("action", decision.get("bias", "NEUTRAL"))).upper()
    if bias not in ("BUY", "SELL"):
        return False, "AI_AUTHORITY_NO_DIRECTION"
    mode = str(decision.get("market_mode", decision.get("mode", ""))).upper()
    bb_state = str(decision.get("bb_state", decision.get("bb", ""))).upper()
    if mode not in VALID_MARKET_MODES or bb_state not in VALID_BB_STATES:
        return False, "AI_AUTHORITY_INVALID_MODE_BB"
    if not bool(decision.get("market_state_fresh", True)):
        return False, "AI_AUTHORITY_STALE_MARKET_STATE"
    hard_block, hard_reason = _v26_has_hard_block(decision)
    if hard_block:
        return False, f"AI_AUTHORITY_HARD_BLOCK:{hard_reason}"
    buy = safe_int(buy_score if buy_score is not None else decision.get("buy_score", decision.get("buyScore", 0)), 0)
    sell = safe_int(sell_score if sell_score is not None else decision.get("sell_score", decision.get("sellScore", 0)), 0)
    if abs(buy - sell) <= 0:
        return False, "AI_AUTHORITY_NO_SCORE_EDGE"
    return True, "AI_AUTHORITY_VALID"


def add_confidence_penalty(decision, penalty, reason):
    if not isinstance(decision, dict):
        return decision
    penalty = max(0, safe_int(penalty, 0))
    reason_text = str(reason)
    sources = decision.get("penalty_sources", [])
    if not isinstance(sources, list):
        sources = []
    if any(str(item.get("reason", "")) == reason_text and bool(item.get("effective", False)) for item in sources if isinstance(item, dict)):
        sources.append({
            "module": "CONFIDENCE_PENALTY_CONSOLIDATOR",
            "penalty": 0,
            "reason": reason_text,
            "effective": False,
            "duplicate_of": "existing_effective_penalty",
        })
        decision["penalty_sources"] = sources
        decision["duplicate_veto_consolidation"] = "ACTIVE"
        return decision
    existing = safe_int(decision.get("confidence_penalty_total", 0), 0)
    decision["confidence_penalty_total"] = existing + penalty
    penalties = decision.get("confidence_penalties", [])
    if not isinstance(penalties, list):
        penalties = [str(penalties)] if penalties else []
    penalties.append(f"-{penalty}: {reason_text}")
    decision["confidence_penalties"] = penalties
    sources.append({
        "module": "CONFIDENCE_PENALTY_CONSOLIDATOR",
        "penalty": penalty,
        "reason": reason_text,
        "effective": True,
    })
    decision["penalty_sources"] = sources
    base_confidence = safe_int(decision.get("confidence", 65), 65)
    decision["confidence"] = max(0, base_confidence - penalty)
    decision["legacy_veto_converted_to_penalty"] = True
    return decision


def _legacy_executor_veto_policy_fields():
    return [dict(item) for item in LEGACY_EXECUTOR_VETO_AUDIT]


def _soften_legacy_veto_if_ai_authority_valid(decision, reason, source, penalty=V26_LEGACY_ALIGNMENT_PENALTY, buy_score=None, sell_score=None):
    """Convert legacy strategy/quality vetoes to telemetry when AI authority is valid."""
    ai_valid, ai_reason = _ai_authority_valid(decision, buy_score, sell_score)
    if not ai_valid:
        return None

    softened = dict(decision)
    softened = add_confidence_penalty(softened, penalty, f"{source}: {reason}")
    softened["decision"] = "TRADE"
    softened["entry_allowed"] = True
    softened["legacy_executor_veto_converted"] = True
    softened["legacy_veto_source"] = source
    softened["legacy_veto_reason"] = str(reason)
    softened["legacy_veto_classification"] = "SOFT_DIAGNOSTIC_PENALTY"
    softened["legacy_veto_terminal_block"] = False
    softened["legacy_veto_authority"] = ai_reason
    softened["legacy_executor_veto_policy"] = _legacy_executor_veto_policy_fields()
    softened["reason"] = (
        str(softened.get("reason", ""))
        + f" | {source}_PENALTY_ONLY: {reason}; {ai_reason}"
    ).strip()
    return softened


def apply_executor_authority_contract_v26_6_1(decision):
    """Publish the single AI->payload->executor->market authority contract."""
    if not isinstance(decision, dict):
        return decision

    ai_valid, ai_reason = _ai_authority_valid(decision)
    hard_block, hard_reason = _v26_has_hard_block(decision)
    is_trade = str(decision.get("decision", "")).upper() == "TRADE"
    allowed = bool(decision.get("allowed", is_trade))
    entry_allowed = bool(decision.get("entry_allowed", is_trade))
    payload_valid = bool(decision.get("payload_valid", is_trade)) and not bool(decision.get("payload_validation_failed", False))
    schema_valid = bool(decision.get("schema_valid", decision.get("schema_validation_ok", is_trade)))
    executable_ai_trade = is_trade and allowed and payload_valid and schema_valid and ai_valid and not hard_block

    decision["ai_decision_authority"] = "PRIMARY"
    decision["executor_authority_chain"] = "AI_DECISION -> PAYLOAD_VALIDATION -> BROKER_SAFETY -> ORDER_SEND -> MARKET"
    decision["executor_hard_block_scope"] = (
        "invalid payload; invalid schema; stale decision; broker freeze; abnormal spread; "
        "duplicate order; insufficient margin; market closed; catastrophic risk state"
    )
    decision["legacy_executor_veto_policy"] = _legacy_executor_veto_policy_fields()
    decision["legacy_quality_terminal_veto_enabled"] = False
    decision["v17_ai_quality_block_classification"] = "SOFT_DIAGNOSTIC_PENALTY"
    decision["v15_entry_block_classification"] = "SOFT_DIAGNOSTIC_PENALTY"
    decision["v16_entry_block_classification"] = "SOFT_DIAGNOSTIC_PENALTY"
    decision["v17_hard_block_classification"] = "SOFT_DIAGNOSTIC_PENALTY"
    decision["analysis_quality_terminal_veto_enabled"] = False
    decision["alignment_terminal_veto_enabled"] = False
    decision["legacy_participation_terminal_veto_enabled"] = False
    decision["executor_ai_authority_valid"] = bool(ai_valid)
    decision["executor_ai_authority_reason"] = ai_reason if ai_valid else (hard_reason or ai_reason)

    raw_quality = safe_int(decision.get("analysis_quality", 0), 0)
    decision.setdefault("analysis_quality_diagnostic", raw_quality)
    decision.setdefault("v17_quality_score_diagnostic", raw_quality)

    if executable_ai_trade:
        decision["allowed"] = True
        decision["entry_allowed"] = True
        decision["executor_order_send_required"] = True
        decision["legacy_executor_override_allowed"] = False
        decision["legacy_v17_quality_veto_result"] = "BYPASSED_DIAGNOSTIC_ONLY"
        decision["legacy_v15_entry_veto_result"] = "BYPASSED_DIAGNOSTIC_ONLY"
        decision["legacy_v16_entry_veto_result"] = "BYPASSED_DIAGNOSTIC_ONLY"
        decision["legacy_v17_hard_block_result"] = "BYPASSED_DIAGNOSTIC_ONLY"
        decision["executor_final_gate_required_log"] = "EXECUTOR_FINAL_GATE_PASS"
        decision["executor_order_send_attempt_required_log"] = "ORDER_SEND_ATTEMPT"
        decision["executor_order_send_result_required_logs"] = ["ORDER_SEND_OK", "ORDER_SEND_FAIL"]
        decision["executor_no_ordersend_after_trade_bug_log"] = "EXECUTOR_BUG_NO_ORDERSEND_AFTER_TRADE"
        if raw_quality < LEGACY_EXECUTOR_MIN_COMPAT_ANALYSIS_QUALITY:
            decision["analysis_quality_compat_floor_applied"] = True
            decision["analysis_quality_compat_floor_reason"] = (
                f"raw analysis_quality={raw_quality} retained as diagnostic; "
                "compatibility floor prevents legacy V17 terminal veto under valid AI authority"
            )
            decision["analysis_quality"] = LEGACY_EXECUTOR_MIN_COMPAT_ANALYSIS_QUALITY
        else:
            decision["analysis_quality_compat_floor_applied"] = False
            decision["analysis_quality"] = raw_quality
    else:
        decision["allowed"] = False if not is_trade else entry_allowed
        decision["executor_order_send_required"] = False
        decision["legacy_executor_override_allowed"] = bool(hard_block)

    return decision


def _management_prefers_runner(bias, market_mode, bb_state, score_gap):
    if market_mode != "TREND" or score_gap < V26_TREND_WALK_RUNNER_MIN_GAP:
        return False
    return (bias == "BUY" and bb_state == "WALK_UP") or (bias == "SELL" and bb_state == "WALK_DOWN")


def align_management_with_trend_context(decision):
    if not isinstance(decision, dict):
        return decision
    if str(decision.get("decision", "")).upper() != "TRADE":
        return decision
    bias = str(decision.get("action", decision.get("bias", "NEUTRAL"))).upper()
    mode = str(decision.get("market_mode", decision.get("mode", ""))).upper()
    bb_state = str(decision.get("bb_state", decision.get("bb", ""))).upper()
    score_gap = safe_int(decision.get("score_gap", 0), 0)
    current = str(decision.get("management", decision.get("mgmt", "SCALP_TP"))).upper()
    if _management_prefers_runner(bias, mode, bb_state, score_gap) and current == "SCALP_TP":
        decision["management"] = "HOLD_TRAIL"
        decision["mgmt"] = "HOLD_TRAIL"
        decision["market_style"] = "INTRADAY_SWING"
        decision["management_alignment"] = "TREND_WALK_PREFERS_HOLD_TRAIL"
        decision["management_alignment_reason"] = f"mode={mode} bb={bb_state} gap={score_gap}; SCALP_TP demoted to secondary"
    else:
        decision.setdefault("management_alignment", "UNCHANGED")
        decision.setdefault("management_alignment_reason", "")
    return decision


def minimum_rr_for_management(mode, management):
    mgmt = str(management).upper()
    if mgmt in ("HOLD_TRAIL", "TREND_RUNNER"):
        return 1.5
    if str(mode).upper() == "TREND":
        return 1.5
    return 1.2


def planned_rr(decision):
    entry = _trade_entry_price(decision)
    sl = safe_float(decision.get("sl", decision.get("stop_loss", 0)), 0.0)
    tp = safe_float(decision.get("tp", decision.get("tp1", 0)), 0.0)
    bias = str(decision.get("action", decision.get("bias", ""))).upper()
    if entry <= 0 or sl <= 0 or tp <= 0 or bias not in ("BUY", "SELL"):
        return 0.0
    risk = abs(entry - sl)
    reward = (tp - entry) if bias == "BUY" else (entry - tp)
    if risk <= 0 or reward <= 0:
        return 0.0
    return round(reward / risk, 3)


def enforce_expectancy_rr_structure(decision):
    if not isinstance(decision, dict) or str(decision.get("decision", "")).upper() != "TRADE":
        return decision
    bias = str(decision.get("action", decision.get("bias", ""))).upper()
    if bias not in ("BUY", "SELL"):
        return decision
    mode = str(decision.get("market_mode", decision.get("mode", "TRANSITION"))).upper()
    management = str(decision.get("management", decision.get("mgmt", "SCALP_TP"))).upper()
    entry = _trade_entry_price(decision)
    sl = safe_float(decision.get("sl", decision.get("stop_loss", 0)), 0.0)
    if entry <= 0 or sl <= 0:
        decision["planned_rr"] = 0.0
        decision["rr_enforcement"] = "WAIT_VALID_MISSING_ENTRY_OR_SL"
        return decision
    risk = abs(entry - sl)
    min_rr = minimum_rr_for_management(mode, management)
    current_rr = planned_rr(decision)
    if risk <= 0:
        decision["planned_rr"] = 0.0
        decision["rr_enforcement"] = "WAIT_VALID_ZERO_RISK"
        return decision
    if current_rr < min_rr:
        target_tp = entry + (risk * min_rr) if bias == "BUY" else entry - (risk * min_rr)
        decision["tp"] = round(target_tp, 3)
        decision["tp1"] = round(target_tp, 3)
        decision["rr_enforcement"] = "TP_EXTENDED_TO_MIN_EXPECTANCY_RR"
        decision["rr_enforcement_reason"] = f"{management}/{mode} planned_rr={current_rr:.2f} < min_rr={min_rr:.2f}"
    else:
        decision["rr_enforcement"] = "RR_OK"
        decision["rr_enforcement_reason"] = f"planned_rr={current_rr:.2f} >= min_rr={min_rr:.2f}"
    decision["planned_rr"] = planned_rr(decision)
    decision["minimum_required_rr"] = min_rr
    decision["expectancy_structure_valid"] = decision["planned_rr"] >= min_rr
    if management in ("HOLD_TRAIL", "TREND_RUNNER"):
        decision["runner_tp_policy"] = "NO_MICRO_TP_STRUCTURE_TRAIL_WITH_MIN_RR_PROTECTIVE_TARGET"
    return decision



def _v26_6_has_explicit_scalp_downgrade(decision):
    """Return True only when a trend trade was intentionally downgraded to scalp."""
    haystack = " ".join(
        str(decision.get(k, ""))
        for k in (
            "management_downgrade", "management_alignment", "management_alignment_reason",
            "runner_disable_reason", "final_gate_reason", "entry_type", "reason"
        )
    ).upper()
    return any(flag in haystack for flag in V26_6_SCALP_DOWNGRADE_ALLOWED_FLAGS)


def _force_scalp_tp_active_v26_6_4(decision):
    """Detect executor/AI conditions where V20.2 forced scalp mode owns management."""
    if not isinstance(decision, dict):
        return False
    haystack = " ".join(
        str(decision.get(k, ""))
        for k in (
            "management_downgrade", "management_downgrade_reason", "final_gate_reason",
            "runner_disable_reason", "adaptive_size_down_reason", "execution_state", "reason"
        )
    ).upper()
    return (
        str(decision.get("management", decision.get("mgmt", ""))).upper() == "SCALP_TP"
        and (
            "FORCE_SCALP" in haystack
            or "V20.2" in haystack
            or "EXPLICIT_SCALP_DOWNGRADE" in haystack
            or bool(decision.get("force_scalp_tp_active", False))
        )
    )


def enforce_trend_management_v26_6(decision):
    """V26.6: MODE=TREND must not silently publish MGMT=SCALP_TP."""
    if not isinstance(decision, dict) or str(decision.get("decision", "")).upper() != "TRADE":
        return decision
    if _force_scalp_tp_active_v26_6_4(decision):
        decision.setdefault("original_management_mode", str(decision.get("original_management_mode", decision.get("management", "SCALP_TP"))).upper())
        decision["effective_management_mode"] = "SCALP_TP"
        decision["management"] = "SCALP_TP"
        decision["mgmt"] = "SCALP_TP"
        decision["forced_management_reason"] = decision.get("forced_management_reason", "V20.2/FORCE_SCALP_TP active; lower runner/trail management cannot override")
        decision["management_authority_owner"] = "FORCE_SCALP_TP"
        decision["trend_management_enforcement"] = "FORCE_SCALP_TP_AUTHORITY_LOCK"
        decision["trend_management_reason"] = "Forced scalp mode owns management; TREND_RUNNER/HOLD_TRAIL override suppressed"
        return decision
    mode = str(decision.get("market_mode", decision.get("mode", ""))).upper()
    current = str(decision.get("management", decision.get("mgmt", "SCALP_TP"))).upper()
    if mode != "TREND" or current != "SCALP_TP":
        decision.setdefault("trend_management_enforcement", "NOT_REQUIRED" if mode != "TREND" else "UNCHANGED")
        return decision

    bias = str(decision.get("action", decision.get("bias", "NEUTRAL"))).upper()
    bb_state = str(decision.get("confirmed_bb_state", decision.get("bb_state", decision.get("bb", "NORMAL")))).upper()
    score_gap = safe_int(decision.get("score_gap", 0), 0)
    active_leg = str(decision.get("active_execution_leg", "")).upper()
    runner_candidate = (
        active_leg == "C"
        or score_gap >= V26_TREND_WALK_RUNNER_MIN_GAP
        or (bias == "BUY" and bb_state == "WALK_UP")
        or (bias == "SELL" and bb_state == "WALK_DOWN")
    )

    if _v26_6_has_explicit_scalp_downgrade(decision):
        decision["trend_management_enforcement"] = "SCALP_TP_EXPLICITLY_DOWNGRADED"
        decision["trend_management_reason"] = "TREND scalp allowed only because explicit downgrade metadata exists"
        decision["runner_preservation_required"] = False
        return decision

    replacement = "TREND_RUNNER" if runner_candidate else "HOLD_TRAIL"
    decision["management"] = replacement
    decision["mgmt"] = replacement
    decision["market_style"] = "INTRADAY_SWING"
    decision["trend_management_enforcement"] = "SCALP_TP_PROHIBITED_FOR_TREND"
    decision["trend_management_reason"] = (
        f"MODE=TREND forbids silent SCALP_TP; upgraded to {replacement} "
        f"(bias={bias} bb={bb_state} gap={score_gap})"
    )
    decision["runner_preservation_required"] = True
    decision["runner_tp_policy"] = "TREND_PARTICIPATION_TRAIL_OR_RUNNER_NO_SCALP_TP"
    decision["reason"] = (str(decision.get("reason", "")) + f" | V26_6_TREND_MGMT_{replacement}").strip()
    return decision


def apply_early_participation_sizing_v26_6(decision):
    """Publish graded risk fractions so gap=2/3 can participate without full-size risk."""
    if not isinstance(decision, dict):
        return decision
    gap = safe_int(decision.get("score_gap", 0), 0)
    fraction = 0.0
    if gap >= V26_6_FULL_SIZE_GAP:
        fraction = 1.0
    elif gap >= 3:
        fraction = V26_6_EARLY_PARTICIPATION_RISK_FRACTIONS[3]
    elif gap >= 2:
        fraction = V26_6_EARLY_PARTICIPATION_RISK_FRACTIONS[2]
    decision["early_participation_enabled"] = gap >= V26_6_MIN_PARTICIPATION_GAP
    decision["early_participation_gap"] = gap
    decision["risk_fraction"] = round(fraction, 2)
    decision["position_size_multiplier"] = round(fraction, 2)
    decision["graded_sizing_policy"] = "gap2=25pct gap3=50pct gap4plus=100pct; total risk not increased"
    if str(decision.get("decision", "")).upper() == "TRADE" and gap in (2, 3):
        decision["execution_state"] = "EXECUTE_CAUTIOUS" if gap == 2 else decision.get("execution_state", "EXECUTE_CAUTIOUS")
        decision["early_participation_reason"] = f"early participation gap={gap}; risk_fraction={fraction:.2f}"
    return decision


def apply_max_realized_loss_guard_v26_6(decision):
    """Add per-trade max realized loss budget metadata derived from planned SL risk."""
    if not isinstance(decision, dict):
        return decision
    bias = str(decision.get("action", decision.get("bias", ""))).upper()
    entry = _trade_entry_price(decision)
    sl = safe_float(decision.get("sl", decision.get("stop_loss", 0)), 0.0)
    risk_points = abs(entry - sl) if entry > 0 and sl > 0 and bias in ("BUY", "SELL") else 0.0
    fraction = safe_float(decision.get("risk_fraction", decision.get("position_size_multiplier", 1.0)), 1.0)
    if str(decision.get("decision", "")).upper() != "TRADE" or risk_points <= 0:
        decision.setdefault("max_realized_loss_guard", "NOT_ACTIVE")
        return decision
    compressed_risk_points = min(risk_points, V26_6_2_MAX_SL_POINTS)
    max_loss_points = min(
        compressed_risk_points * V26_6_MAX_REALIZED_LOSS_R_MULTIPLE,
        V26_6_2_MAX_REALIZED_LOSS_USD_001_LOT / V26_6_2_USD_PER_PRICE_UNIT_001_LOT,
    )
    decision["planned_sl_risk_points"] = round(compressed_risk_points, 3)
    decision["raw_planned_sl_risk_points"] = round(risk_points, 3)
    decision["planned_loss_r"] = 1.0
    decision["max_realized_loss_guard"] = "ACTIVE"
    decision["max_realized_loss_r"] = round(max_loss_points / compressed_risk_points, 3) if compressed_risk_points > 0 else 0
    decision["max_realized_loss_points"] = round(max_loss_points, 3)
    decision["max_realized_loss_usd_001_lot"] = round(V26_6_2_MAX_REALIZED_LOSS_USD_001_LOT, 2)
    decision["floating_force_exit_usd_001_lot"] = round(V26_6_2_FLOATING_FORCE_EXIT_USD_001_LOT, 2)
    decision["floating_force_exit_points"] = round(V26_6_2_FLOATING_FORCE_EXIT_USD_001_LOT / V26_6_2_USD_PER_PRICE_UNIT_001_LOT, 3)
    decision["max_realized_loss_buffer_r"] = round(V26_6_LOSS_GUARD_BUFFER_R, 3)
    decision["risk_budget_fraction"] = round(fraction, 2)
    decision["loss_compression_policy"] = "V26.6.2 hard cap: 0.01 lot XAUUSD realized loss <= $1.20; force exit as floating loss approaches cap"
    return decision


def _v26_6_2_usd_to_points(usd_value):
    return round(safe_float(usd_value, 0.0) / V26_6_2_USD_PER_PRICE_UNIT_001_LOT, 3)



def _dashboard_v27():
    return load_trade_management_dashboard(Path(__file__).resolve().parents[1])


def _dashboard_section_v27(dashboard, section):
    value = dashboard.get(section, {}) if isinstance(dashboard, dict) else {}
    return value if isinstance(value, dict) else {}


def apply_trade_management_dashboard_v27(decision):
    """Attach runtime post-entry dashboard configuration without touching AI entry logic."""
    if not isinstance(decision, dict):
        return decision

    dashboard = _dashboard_v27()
    risk = _dashboard_section_v27(dashboard, "risk")
    breakeven = _dashboard_section_v27(dashboard, "breakeven")
    trailing = _dashboard_section_v27(dashboard, "trailing")
    locks = _dashboard_section_v27(dashboard, "profit_locks")
    runner = _dashboard_section_v27(dashboard, "runner")
    fixed_take_profit = _dashboard_section_v27(dashboard, "fixed_take_profit")
    time_exits = _dashboard_section_v27(dashboard, "time_exits")
    partials = _dashboard_section_v27(dashboard, "partial_exits")

    decision["trade_management_dashboard"] = "V27_RUNTIME_CONFIG_ACTIVE"
    decision["trade_management_dashboard_enabled"] = bool(dashboard.get("enabled", True))
    decision["trade_management_dashboard_schema"] = dashboard.get("schema_version", "")
    decision["dashboard_active_profile"] = dashboard.get("active_profile", "Balanced")
    decision["dashboard_load_sources"] = dashboard.get("load_sources", [])
    decision["dashboard_load_warnings"] = dashboard.get("load_warnings", [])
    decision["dashboard_fallback_defaults_used"] = bool(dashboard.get("fallback_defaults_used", False))
    decision["dashboard_runtime_config_contract"] = "SINGLE_SOURCE_OF_TRUTH: dashboard owns every post-entry SL/close control; AI owns direction and may only consume dashboard initial OrderSend risk"
    decision["initial_order_send_sl_tp_source"] = "DASHBOARD_RISK_INITIAL_SL_AND_OPTIONAL_TP; no hidden AI post-entry override"

    be_enabled = bool(breakeven.get("enable", False))
    trailing_enabled = bool(trailing.get("enable", trailing.get("dynamic_trail", False)))
    profit_lock_enabled = bool(locks.get("enable", False))
    runner_enabled = bool(runner.get("enable_runner", False))
    partial_enabled = bool(partials.get("enable", False))
    time_exit_enabled = bool(
        safe_int(time_exits.get("maximum_seconds", 0), 0) > 0
        or safe_int(time_exits.get("maximum_bars", 0), 0) > 0
        or bool(time_exits.get("session_exit", False))
        or bool(time_exits.get("news_exit", False))
        or bool(time_exits.get("position_aging_exit", False))
    )

    hard_cap = safe_float(risk.get("hard_loss_cap_usd_001_lot", V26_6_2_MAX_REALIZED_LOSS_USD_001_LOT), V26_6_2_MAX_REALIZED_LOSS_USD_001_LOT)
    floating_cap = safe_float(risk.get("max_floating_loss_usd_001_lot", V26_6_2_FLOATING_FORCE_EXIT_USD_001_LOT), V26_6_2_FLOATING_FORCE_EXIT_USD_001_LOT)
    decision["dashboard_risk"] = risk
    decision["dashboard_breakeven"] = breakeven
    decision["dashboard_trailing"] = trailing
    decision["dashboard_profit_locks"] = locks
    decision["dashboard_runner"] = runner
    decision["dashboard_fixed_take_profit"] = fixed_take_profit
    decision["dashboard_time_exits"] = time_exits
    decision["dashboard_partial_exits"] = partials
    decision["dynamic_risk_multiplier"] = safe_float(risk.get("dynamic_risk_multiplier", decision.get("dynamic_risk_multiplier", 1.0)), 1.0)
    decision["max_realized_loss_usd_001_lot"] = hard_cap
    decision["floating_force_exit_usd_001_lot"] = floating_cap
    decision["hard_loss_cap_usd_001_lot"] = hard_cap
    tp_only_profile = str(dashboard.get("active_profile", "")).upper() == "TP_ONLY_1USD_TEST"
    decision["tp_only_profile_active"] = tp_only_profile
    if tp_only_profile:
        decision["tp_only_profile_log"] = "TP_ONLY_PROFILE_ACTIVE"
        decision["ordersend_sl_suppression"] = "ORDERSEND_SL_SUPPRESSED_BY_PROFILE"
        risk["initial_sl_usd_001_lot"] = 0.0
        risk["dynamic_sl_enabled"] = False
        risk["atr_sl_enabled"] = False
        be_enabled = False
        trailing_enabled = False
        profit_lock_enabled = False
        runner_enabled = False
        fixed_take_profit["enable"] = True
        fixed_take_profit["close_profit_usd_001_lot"] = 1.0

    decision["initial_sl_usd_001_lot"] = 0.0 if tp_only_profile else safe_float(risk.get("initial_sl_usd_001_lot", 1.0), 1.0)
    decision["breakeven_enabled_by_dashboard"] = be_enabled
    decision["breakeven_trigger_usd_001_lot"] = safe_float(breakeven.get("trigger_usd_001_lot", 0.0), 0.0) if be_enabled else 0.0
    decision["breakeven_delay_seconds"] = safe_int(breakeven.get("delay_seconds", 0), 0) if be_enabled else 0
    decision["breakeven_lock_distance_usd_001_lot"] = safe_float(breakeven.get("be_lock_distance_usd_001_lot", 0.0), 0.0) if be_enabled else 0.0
    decision["trailing_enabled_by_dashboard"] = trailing_enabled
    decision["profit_lock_enabled_by_dashboard"] = profit_lock_enabled
    decision["fixed_take_profit_enabled_by_dashboard"] = bool(fixed_take_profit.get("enable", False))
    decision["fixed_take_profit_close_usd_001_lot"] = safe_float(fixed_take_profit.get("close_profit_usd_001_lot", 1.0), 1.0)
    decision["runner_enabled_by_dashboard"] = runner_enabled
    decision["runner_momentum_timeout_sec"] = safe_int(runner.get("runner_timeout_seconds", 0), 0) if runner_enabled else 0
    decision["runner_exit_mode"] = runner.get("runner_exit_mode", "DISABLED_BY_DASHBOARD") if runner_enabled else "DISABLED_BY_DASHBOARD"
    decision["time_exit_enabled_by_dashboard"] = time_exit_enabled
    decision["partial_exit_enabled_by_dashboard"] = partial_enabled
    decision["time_exit_policy"] = time_exits if time_exit_enabled else {"enabled": False, "status": "DISABLED_BY_DASHBOARD"}
    decision["partial_exit_policy"] = partials if partial_enabled else {"enabled": False, "status": "DISABLED_BY_DASHBOARD"}
    decision["exit_authority_priority"] = dashboard.get("exit_authority_priority", list(V26_6_4_EXIT_AUTHORITY_PRIORITY))
    decision["dashboard_single_source_of_truth_status"] = "DASHBOARD_SINGLE_SOURCE_OF_TRUTH_PASS"
    return decision

def apply_loss_cap_and_profit_lock_v26_6_2(decision):
    """Publish post-entry controls only from the V27 dashboard runtime config.

    V26 hardcoded BE/profit-lock/runner constants are intentionally not used here.
    Initial SL remains defined before OrderSend from the dashboard risk section;
    after entry, SL/close modules must honor the dashboard enable flags.
    """
    if not isinstance(decision, dict):
        return decision

    _log_risk_payload_event("RISK_BEFORE_DASHBOARD", decision)
    decision = apply_trade_management_dashboard_v27(decision)
    _log_risk_payload_event("RISK_AFTER_DASHBOARD", decision)
    if str(decision.get("decision", "")).upper() != "TRADE":
        decision.setdefault("profit_loss_asymmetry_guard", "NOT_ACTIVE")
        return decision

    be_enabled = bool(decision.get("breakeven_enabled_by_dashboard", False))
    trailing_enabled = bool(decision.get("trailing_enabled_by_dashboard", False))
    profit_lock_enabled = bool(decision.get("profit_lock_enabled_by_dashboard", False))
    runner_enabled = bool(decision.get("runner_enabled_by_dashboard", False))

    decision["profit_loss_asymmetry_guard"] = "DASHBOARD_OWNED"
    decision["reference_lot"] = 0.01
    decision["usd_per_price_unit_001_lot"] = V26_6_2_USD_PER_PRICE_UNIT_001_LOT
    decision["floating_force_exit_policy"] = "DASHBOARD_RISK_CONFIG_ONLY"
    decision["hard_loss_cap_policy"] = "DASHBOARD_RISK_CONFIG_ONLY"
    decision["sl_compression_applied"] = False
    decision["sl_compression_reason"] = "DISABLED: no AI-side V26 post-entry SL override; dashboard initial_sl_usd_001_lot defines OrderSend SL"

    if not be_enabled:
        decision["breakeven_trigger_usd_001_lot"] = 0.0
        decision["breakeven_trigger_points"] = 0.0
        decision["breakeven_lock_policy"] = "DISABLED_BY_DASHBOARD"
        decision["breakeven_triggered"] = False
    else:
        be_trigger = safe_float(decision.get("breakeven_trigger_usd_001_lot", 0.0), 0.0)
        decision["breakeven_trigger_points"] = _v26_6_2_usd_to_points(be_trigger)
        decision["breakeven_lock_policy"] = "DASHBOARD_RUNTIME_CONFIG"

    if not profit_lock_enabled:
        decision["lock_profit_trigger_usd_001_lot"] = 0.0
        decision["lock_profit_usd_001_lot"] = 0.0
        decision["lock_profit_trigger_points"] = 0.0
        decision["lock_profit_points"] = 0.0
        decision["profit_protection_ladder"] = []
        decision["profit_protection_triggered"] = False
        decision["profit_protection_goal"] = "DISABLED_BY_DASHBOARD"
    else:
        locks = decision.get("dashboard_profit_locks", {}) if isinstance(decision.get("dashboard_profit_locks", {}), dict) else {}
        ladder = []
        for key in ("lock_level_1_usd_001_lot", "lock_level_2_usd_001_lot", "lock_level_3_usd_001_lot", "runner_lock_usd_001_lot"):
            level = locks.get(key, {}) if isinstance(locks.get(key, {}), dict) else {}
            trigger = safe_float(level.get("trigger", 0.0), 0.0)
            lock = safe_float(level.get("lock", 0.0), 0.0)
            if trigger > 0:
                ladder.append({"trigger_usd_001_lot": trigger, "trigger_points": _v26_6_2_usd_to_points(trigger), "lock_usd_001_lot": lock, "lock_points": _v26_6_2_usd_to_points(lock)})
        decision["profit_protection_ladder"] = ladder
        decision["profit_protection_goal"] = "DASHBOARD_RUNTIME_CONFIG"
        decision["profit_protection_triggered"] = bool(
            ladder and safe_float(decision.get("max_floating_profit", decision.get("real_MFE", 0.0)), 0.0) >= safe_float(ladder[0].get("trigger_usd_001_lot", 0.0), 0.0)
        )

    if not trailing_enabled:
        decision["trailing_stop_active"] = False
        decision["structure_trail_active"] = False
        decision["trailing_policy"] = "DISABLED_BY_DASHBOARD"

    if not runner_enabled:
        decision["runner_timeout_triggered"] = False
        decision["runner_momentum_decay_triggered"] = False
        decision["runner_momentum_timeout_sec"] = 0
        decision["runner_timeout_policy"] = "DISABLED_BY_DASHBOARD"
        decision["protected_exit_mode_on_runner_timeout"] = False
        decision["runner_activation_rule"] = "DISABLED_BY_DASHBOARD"
    else:
        decision["runner_timeout_policy"] = "DASHBOARD_RUNTIME_CONFIG"
        decision["protected_exit_mode_on_runner_timeout"] = True

    decision["dashboard_single_source_of_truth_status"] = "DASHBOARD_SINGLE_SOURCE_OF_TRUTH_PASS"
    return decision


def _leg_type_v26_6_4(decision):
    active_leg = str(decision.get("active_execution_leg", decision.get("leg_type", ""))).upper()
    if active_leg in ("A", "LEG_A", "SCOUT", "SCALP"):
        return "LEG_A"
    if active_leg in ("B", "LEG_B", "CONFIRMATION"):
        return "LEG_B"
    if active_leg in ("C", "LEG_C", "RUNNER"):
        return "LEG_C"
    mgmt = str(decision.get("management", decision.get("mgmt", ""))).upper()
    if mgmt in ("HOLD_TRAIL", "TREND_RUNNER"):
        return "LEG_C"
    return "LEG_A" if mgmt == "SCALP_TP" else "LEG_B"


def _leg_aware_ladder_v26_6_4(leg_type):
    if leg_type == "LEG_A":
        return [
            {"trigger_usd_001_lot": 0.20, "lock_usd_001_lot": -0.05, "action": "SL_MAX_RISK_MINUS_0_05"},
            {"trigger_usd_001_lot": 0.40, "lock_usd_001_lot": 0.00, "action": "MOVE_SL_TO_BREAKEVEN"},
            {"trigger_usd_001_lot": 0.60, "lock_usd_001_lot": 0.20, "action": "LOCK_PROFIT_0_20"},
        ]
    if leg_type == "LEG_B":
        return [
            {"trigger_usd_001_lot": 0.40, "lock_usd_001_lot": 0.00, "action": "MOVE_SL_TO_BREAKEVEN"},
            {"trigger_usd_001_lot": 0.80, "lock_usd_001_lot": 0.30, "action": "LOCK_PROFIT_0_30"},
            {"trigger_usd_001_lot": 1.20, "lock_usd_001_lot": 0.60, "action": "LOCK_PROFIT_0_60"},
        ]
    return [
        {"trigger": "STRUCTURE_TRAIL", "action": "swing high/low protection"},
        {"trigger": "MOMENTUM_DECAY", "action": "protected exit when weak expansion evidence appears"},
        {"trigger": "BB_WALK_FAILURE", "action": "protect runner continuity"},
    ]


def apply_exit_authority_manager_v26_6_4(decision):
    """Publish the single owner of exit/management authority and leg-aware protection contract."""
    if not isinstance(decision, dict):
        return decision

    original = str(decision.get("original_management_mode", decision.get("management", decision.get("mgmt", "NO_TRADE")))).upper()
    effective = str(decision.get("management", decision.get("mgmt", original))).upper()
    leg_type = _leg_type_v26_6_4(decision)
    force_scalp = _force_scalp_tp_active_v26_6_4(decision)
    daily_guard = bool(decision.get("drawdown_caution_mode", False) or decision.get("session_stop_active", False) or decision.get("daily_guard_active", False))

    owner = "RUNNER" if leg_type == "LEG_C" else "TRAILING" if effective in ("HOLD_TRAIL", "TREND_RUNNER") else "BREAKEVEN"
    if force_scalp:
        owner = "PROFIT_LOCK"
        effective = "SCALP_TP"
    if safe_float(decision.get("profit_lock_level", 0.0), 0.0) > 0:
        owner = "PROFIT_LOCK"
    if bool(decision.get("breakeven_triggered", False) or decision.get("profit_protection_triggered", False)):
        owner = "BREAKEVEN"
    if bool(decision.get("trailing_stop_active", False) or decision.get("structure_trail_active", False)):
        owner = "TRAILING"
    if bool(decision.get("runner_timeout_triggered", False) or decision.get("runner_momentum_decay_triggered", False)):
        owner = "RUNNER"
    if bool(decision.get("time_exit_triggered", False) or decision.get("session_exit_triggered", False) or decision.get("position_aging_exit_triggered", False)):
        owner = "TIME_EXIT"
    if daily_guard and owner not in ("EMERGENCY_EXIT", "HARD_LOSS_CAP"):
        decision["daily_guard_risk_compression_active"] = True
    if bool(decision.get("hard_loss_cap_triggered", False)):
        owner = "HARD_LOSS_CAP"
    if bool(decision.get("emergency_exit_triggered", False)):
        owner = "EMERGENCY_EXIT"

    decision = apply_trade_management_dashboard_v27(decision)

    decision["exit_authority_manager"] = "V27_DASHBOARD_SINGLE_OWNER"
    decision["exit_authority_priority"] = decision.get("exit_authority_priority", list(V26_6_4_EXIT_AUTHORITY_PRIORITY))
    decision["leg_type"] = leg_type
    decision["original_management_mode"] = original
    decision["effective_management_mode"] = effective
    decision["management_authority_owner"] = owner
    decision["management_authority_lock"] = owner
    decision["lower_authority_reactivation_allowed"] = False
    decision["forced_management_reason"] = decision.get("forced_management_reason", "NONE" if not force_scalp else "FORCE_SCALP_TP active")
    decision["management"] = effective if str(decision.get("decision", "")).upper() == "TRADE" else "NO_TRADE"
    decision["mgmt"] = decision["management"]

    decision["max_floating_profit_per_position_required"] = True
    decision["max_floating_profit"] = safe_float(decision.get("max_floating_profit", decision.get("max_floating_profit_per_position", 0.0)), 0.0)
    decision["current_profit"] = safe_float(decision.get("current_profit", decision.get("floating_profit", 0.0)), 0.0)
    decision["profit_lock_level"] = decision.get("profit_lock_level", 0.0)
    decision["hard_loss_cap_triggered"] = bool(decision.get("hard_loss_cap_triggered", False))
    decision["runner_timeout_triggered"] = bool(decision.get("runner_timeout_triggered", False))
    decision["runner_momentum_decay_triggered"] = bool(decision.get("runner_momentum_decay_triggered", False))
    decision["exit_reason"] = decision.get("exit_reason", "")
    decision["realized_profit"] = safe_float(decision.get("realized_profit", 0.0), 0.0)
    decision["realized_R"] = safe_float(decision.get("realized_R", 0.0), 0.0)
    mfe = safe_float(decision.get("real_MFE", decision.get("max_floating_profit", 0.0)), 0.0)
    mae = safe_float(decision.get("real_MAE", decision.get("max_adverse_excursion", 0.0)), 0.0)
    realized = decision["realized_profit"]
    decision["MFE"] = round(mfe, 3)
    decision["MAE"] = round(mae, 3)
    decision["MFE_to_realized_ratio"] = round(mfe / realized, 3) if realized > 0 else 0.0
    decision["MAE_to_realized_loss_ratio"] = round(abs(mae) / abs(realized), 3) if realized < 0 else 0.0
    decision["leg_aware_profit_protection_ladder"] = decision.get("profit_protection_ladder", []) if decision.get("profit_lock_enabled_by_dashboard", False) else []
    decision["profit_protection_ladder_scope"] = "DASHBOARD_RUNTIME_CONFIG" if decision.get("profit_lock_enabled_by_dashboard", False) else "DISABLED_BY_DASHBOARD"
    decision["no_profit_reversal_policy"] = "DASHBOARD_RUNTIME_CONFIG" if decision.get("profit_lock_enabled_by_dashboard", False) else "DISABLED_BY_DASHBOARD"
    decision["green_to_red_prevention_policy"] = "DASHBOARD_RUNTIME_CONFIG" if decision.get("breakeven_enabled_by_dashboard", False) or decision.get("profit_lock_enabled_by_dashboard", False) else "DISABLED_BY_DASHBOARD"
    decision["hard_loss_cap_owner"] = "DASHBOARD_RUNTIME_CONFIG"
    decision["hard_loss_warning_usd_001_lot"] = safe_float(decision.get("floating_force_exit_usd_001_lot", 0.0), 0.0)
    decision["absolute_emergency_close_usd_001_lot"] = safe_float(decision.get("hard_loss_cap_usd_001_lot", 0.0), 0.0)
    decision["runner_max_loss_usd_001_lot"] = safe_float(decision.get("hard_loss_cap_usd_001_lot", 0.0), 0.0) if decision.get("runner_enabled_by_dashboard", False) else 0.0
    decision["runner_timeout_policy"] = "DASHBOARD_RUNTIME_CONFIG" if decision.get("runner_enabled_by_dashboard", False) else "DISABLED_BY_DASHBOARD"
    decision["runner_momentum_evidence"] = ["DASHBOARD_RUNTIME_CONFIG"] if decision.get("runner_enabled_by_dashboard", False) else []
    decision["daily_guard_open_position_policy"] = "No new entries while active; open-position BE/profit-lock/trailing actions remain disabled unless the dashboard enables the corresponding module"
    decision["expectancy_targets"] = {"average_loss_usd_001_lot": "-0.80_to_-1.00", "average_win_usd_001_lot": ">=+1.20", "profit_factor": ">1.20", "loss_below_minus_2": "approach_zero"}
    return decision


def _v26_6_2_block_trade(decision, block_code, reason):
    telemetry = decision.setdefault("duplicate_veto_telemetry", [])
    if not isinstance(telemetry, list):
        telemetry = []
        decision["duplicate_veto_telemetry"] = telemetry
    existing_owner = str(decision.get("final_veto_owner", "") or "")
    existing_code = str(decision.get("effective_veto_code", decision.get("final_gate_block_reason_class", "")) or "")
    if existing_owner and existing_code == str(block_code):
        telemetry.append({
            "module": "V26_6_2_EXPECTANCY_ENTRY_FILTER",
            "code": block_code,
            "reason": reason,
            "effective": False,
            "duplicate_of": existing_owner,
        })
        decision["duplicate_veto_consolidation"] = "ACTIVE"
        return decision

    bias = str(decision.get("action", decision.get("bias", decision.get("intended_action", "NEUTRAL")))).upper()
    if bias not in ("BUY", "SELL"):
        bias = "NEUTRAL"
    decision["decision"] = "NO_TRADE"
    decision["entry_allowed"] = False
    decision["execution_state"] = "NO_TRADE"
    decision["management"] = "NO_TRADE"
    decision["mgmt"] = "NO_TRADE"
    decision["intended_action"] = bias
    decision["expectancy_emergency_block"] = block_code
    decision["expectancy_emergency_reason"] = reason
    decision["final_gate_block_reason_class"] = block_code
    decision["effective_veto_code"] = block_code
    decision["final_veto_owner"] = "V26_6_2_EXPECTANCY_ENTRY_FILTER"
    decision["duplicate_veto_consolidation"] = "ACTIVE"
    telemetry.append({
        "module": "V26_6_2_EXPECTANCY_ENTRY_FILTER",
        "code": block_code,
        "reason": reason,
        "effective": True,
        "duplicate_of": "",
    })
    decision["reason"] = (str(decision.get("reason", "")) + " | " + reason).strip()
    return decision


def _v26_6_2_strong_middle_confirmation(bias, rsi, macd_hist):
    if bias == "BUY":
        return rsi >= V26_6_2_STRONG_MIDDLE_BUY_RSI and macd_hist >= V26_6_2_STRONG_MIDDLE_MACD_ABS
    if bias == "SELL":
        return rsi <= V26_6_2_STRONG_MIDDLE_SELL_RSI and macd_hist <= -V26_6_2_STRONG_MIDDLE_MACD_ABS
    return False


def _emergency_gap2_reject(decision, reason, supporting_vetoes=None):
    decision["EMERGENCY_GAP2_PARTICIPATION_CHECK"] = "REJECTED"
    decision["EMERGENCY_GAP2_REJECTED"] = True
    decision["EMERGENCY_GAP2_REJECTED_REASON"] = reason
    decision["EMERGENCY_GAP2_APPROVED"] = False
    decision["supporting_vetoes"] = list(supporting_vetoes or [])
    return False


def _emergency_gap2_payload_can_construct_valid_risk(decision):
    bias = str(decision.get("action", decision.get("bias", ""))).upper()
    entry = _trade_entry_price(decision)
    if bias not in ("BUY", "SELL") or entry <= 0:
        return False, "missing BUY/SELL bias or positive entry price"
    if bool(decision.get("tp_only_profile_active", False)) and not _tp_only_sl_suppression_approved(decision):
        return False, "invalid TP-only profile contract"
    return True, "risk payload can be constructed"


def _emergency_gap2_participation_allowed(decision, bias, action, score_gap, mode, bb_state, rsi, macd_hist, bid, bb_upper, bb_middle, bb_lower):
    """Narrow V26.6.2 emergency exception: gap=2 may execute cautious only when all hard safety remains clear."""
    supporting_vetoes = []
    decision["EMERGENCY_GAP2_PARTICIPATION_CHECK"] = "CHECKING"
    decision["original_veto"] = "V26_6_2_WEAK_GAP_NO_TRADE"
    decision["participation_size_factor"] = EMERGENCY_GAP2_PARTICIPATION_SIZE_FACTOR

    if action not in ("BUY", "SELL") or bias != action:
        return _emergency_gap2_reject(decision, "bias/action not aligned", ["BIAS_ACTION_MISMATCH"])
    if score_gap != 2:
        return _emergency_gap2_reject(decision, f"score_gap={score_gap} is not emergency gap=2", ["NOT_GAP2"])

    hard_block, hard_reason = _v26_has_hard_block(decision)
    if hard_block:
        return _emergency_gap2_reject(decision, f"hard safety block: {hard_reason}", [hard_reason])
    if not bool(decision.get("market_state_fresh", True)):
        return _emergency_gap2_reject(decision, "market_state not fresh", ["MARKET_STATE_STALE"])
    decision_age = safe_float(decision.get("decision_age_sec", decision.get("decision_file_age_sec", 0.0)), 0.0)
    if decision_age > TEMP_DECISION_STALE_TARGET_SEC:
        return _emergency_gap2_reject(decision, f"decision freshness invalid age={decision_age}", ["DECISION_STALE"])

    risk_ok, risk_reason = _emergency_gap2_payload_can_construct_valid_risk(decision)
    if not risk_ok:
        return _emergency_gap2_reject(decision, risk_reason, ["INVALID_RISK_PAYLOAD_CONSTRUCTION"])

    if bool(decision.get("duplicate_order", False) or decision.get("duplicate_order_protection", False)):
        return _emergency_gap2_reject(decision, "duplicate order protection active", ["DUPLICATE_ORDER"])
    if bool(decision.get("daily_catastrophic_risk", False) or decision.get("catastrophic_risk", False) or decision.get("catastrophic_risk_state", False)):
        return _emergency_gap2_reject(decision, "daily catastrophic risk active", ["CATASTROPHIC_RISK"])

    trend_exhaustion_score = safe_int(decision.get("trend_exhaustion_score", 0), 0)
    exhaustion_score = safe_int(decision.get("exhaustion_score", decision.get("exhaustion_risk", 0)), 0)
    late_score = safe_int(decision.get("late_entry_score", 0), 0)
    if trend_exhaustion_score >= TREND_EXHAUSTION_BLOCK_LEVEL or exhaustion_score >= EXHAUSTION_BLOCK_SCORE or late_score >= LATE_ENTRY_BLOCK_SCORE:
        return _emergency_gap2_reject(decision, "severe exhaustion or late-entry risk", ["SEVERE_EXHAUSTION"])

    buy_score = safe_int(decision.get("buy_score", decision.get("buyScore", 0)), 0)
    sell_score = safe_int(decision.get("sell_score", decision.get("sellScore", 0)), 0)
    if not ((action == "BUY" and buy_score > sell_score) or (action == "SELL" and sell_score > buy_score)):
        return _emergency_gap2_reject(decision, "directional dominance missing", ["NO_DIRECTIONAL_DOMINANCE"])

    near_middle = bb_state == "NORMAL" and bid > 0 and is_near_bb_middle(bid, bb_upper, bb_middle, bb_lower)
    if near_middle and not _v26_6_2_strong_middle_confirmation(action, rsi, macd_hist):
        return _emergency_gap2_reject(decision, "BB middle chop without RSI/MACD confirmation", ["BB_MIDDLE_CHOP"])
    if (action == "BUY" and macd_hist <= -EMERGENCY_GAP2_STRONG_OPPOSITE_MACD) or (action == "SELL" and macd_hist >= EMERGENCY_GAP2_STRONG_OPPOSITE_MACD):
        return _emergency_gap2_reject(decision, "MACD strongly opposite beyond emergency threshold", ["STRONG_OPPOSITE_MACD"])

    decision["EMERGENCY_GAP2_PARTICIPATION_CHECK"] = "APPROVED"
    decision["EMERGENCY_GAP2_APPROVED"] = True
    decision["EMERGENCY_GAP2_REJECTED"] = False
    decision["TRADE_CAUTIOUS_FROM_WEAK_GAP"] = True
    decision["original_recovery"] = "TRADE_CAUTIOUS_FROM_WEAK_GAP"
    decision["recovery_applied"] = True
    decision["decision"] = "TRADE"
    decision["allowed"] = True
    decision["entry_allowed"] = True
    decision["participation_type"] = "CAUTIOUS"
    decision["execution_mode"] = "CAUTIOUS"
    decision["participation_size_factor"] = EMERGENCY_GAP2_PARTICIPATION_SIZE_FACTOR
    decision["risk_fraction"] = EMERGENCY_GAP2_PARTICIPATION_SIZE_FACTOR
    decision["position_size_multiplier"] = EMERGENCY_GAP2_PARTICIPATION_SIZE_FACTOR
    decision["minimum_lot_fallback_allowed"] = True
    decision["no_pyramid"] = True
    decision["pyramid_enabled"] = False
    decision["continuation_add_enabled"] = False
    decision["runner_enabled"] = False
    decision["runner_default"] = "DISABLED_FOR_EMERGENCY_GAP2"
    decision["execution_state"] = "EXECUTE_CAUTIOUS"
    decision["decision_output_state"] = "TRADE"
    decision["management"] = "SCALP_TP"
    decision["mgmt"] = "SCALP_TP"
    decision["expectancy_emergency_block"] = "NONE"
    decision["effective_veto_code"] = "NONE"
    decision["final_veto_owner"] = "NONE"
    decision["supporting_vetoes"] = ["V26_6_2_WEAK_GAP_NO_TRADE"] + [v for v in supporting_vetoes if v != "V26_6_2_WEAK_GAP_NO_TRADE"]
    decision["emergency_gap2_reason"] = "TRADE_CAUTIOUS_FROM_WEAK_GAP: bias/action aligned, gap=2, hard safety clear, payload risk constructible"
    decision["reason"] = (str(decision.get("reason", "")).strip() + " | TRADE_CAUTIOUS_FROM_WEAK_GAP").strip()
    return True


def _emergency_gap2_recovered_participation_active(decision):
    if not isinstance(decision, dict):
        return False
    if not bool(decision.get("EMERGENCY_GAP2_APPROVED", False)):
        return False
    if str(decision.get("decision", "")).upper() != "TRADE":
        return False
    if str(decision.get("execution_state", "")).upper() != "EXECUTE_CAUTIOUS":
        return False
    if not bool(decision.get("payload_valid", True)):
        return False
    hard_block, _ = _v26_has_hard_block(decision)
    return not hard_block


def apply_expectancy_entry_filters_v26_6_2(decision):
    """Emergency expectancy filters: no weak gaps, stricter transition-normal, no BB-mid chop."""
    if not isinstance(decision, dict):
        return decision
    if str(decision.get("decision", "")).upper() != "TRADE":
        return decision

    action = str(decision.get("action", decision.get("intended_action", "NEUTRAL"))).upper()
    bias = str(decision.get("bias", action)).upper()
    mode = str(decision.get("market_mode", decision.get("mode", "TRANSITION"))).upper()
    bb_state = str(decision.get("bb_state", decision.get("bb", "NORMAL"))).upper()
    score_gap = safe_int(decision.get("score_gap", 0), 0)
    rsi = safe_float(decision.get("rsi", 50), 50)
    macd_hist = safe_float(decision.get("macd_hist", 0), 0)
    bid = _trade_entry_price(decision)
    bb_upper = safe_float(decision.get("bb_upper", decision.get("bb_upper2", 0)), 0.0)
    bb_middle = safe_float(decision.get("bb_middle", decision.get("bb_mid", 0)), 0.0)
    bb_lower = safe_float(decision.get("bb_lower", decision.get("bb_lower2", 0)), 0.0)

    decision["expectancy_emergency_filter"] = "V26.6.2_ACTIVE"
    decision["minimum_score_gap_required"] = V26_6_2_MIN_SCORE_GAP
    decision["transition_normal_minimum_score_gap"] = V26_6_2_TRANSITION_NORMAL_MIN_GAP

    if _emergency_gap2_recovered_participation_active(decision):
        decision["expectancy_emergency_block"] = "NONE"
        decision["effective_veto_code"] = "NONE"
        decision["final_veto_owner"] = "NONE"
        decision["recovery_applied"] = True
        return decision

    if score_gap < V26_6_2_MIN_SCORE_GAP:
        if _emergency_gap2_participation_allowed(
            decision, bias, action, score_gap, mode, bb_state, rsi, macd_hist, bid, bb_upper, bb_middle, bb_lower
        ):
            return decision
        return _v26_6_2_block_trade(
            decision,
            "V26_6_2_WEAK_GAP_NO_TRADE",
            f"V26.6.2 WEAK GAP NO_TRADE | score_gap={score_gap} < {V26_6_2_MIN_SCORE_GAP}",
        )

    if mode == "TRANSITION" and bb_state == "NORMAL" and score_gap < V26_6_2_TRANSITION_NORMAL_MIN_GAP:
        return _v26_6_2_block_trade(
            decision,
            "V26_6_2_TRANSITION_NORMAL_GAP_BLOCK",
            f"V26.6.2 TRANSITION+NORMAL requires score_gap>={V26_6_2_TRANSITION_NORMAL_MIN_GAP}; got {score_gap}",
        )

    near_middle = bb_state == "NORMAL" and bid > 0 and is_near_bb_middle(bid, bb_upper, bb_middle, bb_lower)
    if near_middle and not _v26_6_2_strong_middle_confirmation(bias, rsi, macd_hist):
        return _v26_6_2_block_trade(
            decision,
            "V26_6_2_BB_MIDDLE_CHOP_BLOCK",
            f"V26.6.2 BB middle block | RSI/MACD not strong enough bias={bias} rsi={rsi:.2f} macd={macd_hist:.2f}",
        )

    decision["expectancy_emergency_block"] = "NONE"
    decision["middle_zone_confirmed_strong"] = bool(near_middle and _v26_6_2_strong_middle_confirmation(bias, rsi, macd_hist))
    return decision


def _v26_6_2_parse_trade_time(value):
    text = str(value or "").strip().replace("T", " ").replace("Z", "")
    if not text:
        return None
    for fmt, length in (("%Y-%m-%d %H:%M:%S", 19), ("%Y-%m-%d %H:%M", 16), ("%Y.%m.%d %H:%M:%S", 19), ("%Y.%m.%d %H:%M", 16)):
        try:
            return datetime.strptime(text[:length], fmt)
        except Exception:
            continue
    try:
        return datetime.fromisoformat(text)
    except Exception:
        return None


def _v26_6_2_trade_memory_path():
    if TRADE_MEMORY_PATH.exists():
        return TRADE_MEMORY_PATH
    if LOCAL_TRADE_MEMORY_PATH.exists():
        return LOCAL_TRADE_MEMORY_PATH
    return None


def _v26_6_2_row_value(row, names, default=""):
    for name in names:
        value = row.get(name)
        if value not in (None, ""):
            return value
    return default


def _v26_6_2_trade_memory_session_stats():
    import csv

    path = _v26_6_2_trade_memory_path()
    stats = {
        "path": str(path) if path else "",
        "daily_net": 0.0,
        "consecutive_losses": 0,
        "same_direction_loss_streak": 0,
        "last_loss_age_sec": 999999,
        "last_loss_direction": "UNKNOWN",
        "last_loss_profit": 0.0,
        "last_loss_row": {},
        "trades_today": 0,
        "available": bool(path),
    }
    if not path:
        return stats

    now_dt = datetime.utcnow()
    rows = []
    try:
        with open(path, "r", encoding="utf-8", errors="ignore", newline="") as f:
            reader = csv.DictReader(f)
            for row in reader:
                close_text = next((row.get(k, "") for k in ("close_time", "exit_time", "closed_at", "timestamp", "time", "date") if row.get(k)), "")
                closed = _v26_6_2_parse_trade_time(close_text)
                profit = safe_float(row.get("profit", row.get("pnl", row.get("net_profit", 0))), 0.0)
                direction = str(_v26_6_2_row_value(row, ("direction", "side", "type", "action", "bias"), "UNKNOWN")).upper()
                if "BUY" in direction:
                    direction = "BUY"
                elif "SELL" in direction:
                    direction = "SELL"
                else:
                    direction = "UNKNOWN"
                if closed and closed.date() == now_dt.date():
                    stats["daily_net"] += profit
                    stats["trades_today"] += 1
                rows.append((closed or datetime.min, profit, str(row.get("result", "")).upper(), direction, dict(row)))
    except Exception as exc:
        stats["available"] = False
        stats["read_error"] = str(exc)
        return stats

    consecutive = 0
    same_direction = 0
    first_loss_direction = "UNKNOWN"
    last_loss_time = None
    last_loss_row = {}
    last_loss_profit = 0.0
    for closed, profit, result, direction, row in sorted(rows, key=lambda item: item[0], reverse=True):
        is_loss = profit < 0 or result == "LOSS"
        is_win = profit > 0 or result == "WIN"
        if is_loss:
            consecutive += 1
            if last_loss_time is None:
                if closed != datetime.min:
                    last_loss_time = closed
                first_loss_direction = direction
                last_loss_row = row
                last_loss_profit = profit
            if first_loss_direction != "UNKNOWN" and direction == first_loss_direction:
                same_direction += 1
        elif is_win:
            break
    stats["consecutive_losses"] = consecutive
    stats["same_direction_loss_streak"] = same_direction
    stats["last_loss_direction"] = first_loss_direction
    stats["last_loss_row"] = last_loss_row
    stats["last_loss_profit"] = round(last_loss_profit, 2)
    if last_loss_time:
        stats["last_loss_age_sec"] = max(0, int((now_dt - last_loss_time).total_seconds()))
    stats["daily_net"] = round(stats["daily_net"], 2)
    return stats


def apply_expectancy_metrics_v26_6_6(decision):
    """Publish realized expectancy diagnostics from trade memory without changing frequency."""
    if not isinstance(decision, dict):
        return decision
    import csv

    path = _v26_6_2_trade_memory_path()
    wins = []
    losses = []
    if path:
        try:
            with open(path, "r", encoding="utf-8", errors="ignore", newline="") as f:
                for row in csv.DictReader(f):
                    profit = safe_float(row.get("profit", row.get("pnl", row.get("net_profit", 0))), 0.0)
                    if profit > 0:
                        wins.append(profit)
                    elif profit < 0:
                        losses.append(profit)
        except Exception as exc:
            decision["expectancy_metrics_read_error"] = str(exc)

    total = len(wins) + len(losses)
    gross_win = sum(wins)
    gross_loss = abs(sum(losses))
    avg_win = gross_win / len(wins) if wins else 0.0
    avg_loss = sum(losses) / len(losses) if losses else 0.0
    decision["expectancy_metrics"] = {
        "win_rate": round(len(wins) / total, 4) if total else 0.0,
        "avg_win": round(avg_win, 2),
        "avg_loss": round(avg_loss, 2),
        "profit_factor": round(gross_win / gross_loss, 3) if gross_loss > 0 else 0.0,
        "sample_size": total,
        "target_profit_factor": 1.20,
    }
    decision["win_rate"] = decision["expectancy_metrics"]["win_rate"]
    decision["avg_win"] = decision["expectancy_metrics"]["avg_win"]
    decision["avg_loss"] = decision["expectancy_metrics"]["avg_loss"]
    decision["profit_factor"] = decision["expectancy_metrics"]["profit_factor"]
    return decision


def _v26_6_6_opposite_direction(direction):
    return "SELL" if direction == "BUY" else "BUY" if direction == "SELL" else "NEUTRAL"


def _v26_6_6_shadow_profit(direction, entry, price):
    if direction == "BUY":
        return price - entry
    if direction == "SELL":
        return entry - price
    return 0.0


def apply_shadow_opposite_audit_v26_6_6(decision):
    """Create/update a non-traded opposite-direction audit record for every real signal."""
    if not isinstance(decision, dict):
        return decision

    bias = str(decision.get("action", decision.get("bias", "NEUTRAL"))).upper()
    entry = _trade_entry_price(decision)
    price = safe_float(decision.get("bid", decision.get("price", entry)), entry)
    now_ts = int(time.time())
    records = []
    try:
        if LOCAL_SHADOW_AUDIT_PATH.exists():
            raw = json.loads(LOCAL_SHADOW_AUDIT_PATH.read_text(encoding="utf-8"))
            records = raw if isinstance(raw, list) else []
    except Exception as exc:
        decision["shadow_audit_read_error"] = str(exc)
        records = []

    for rec in records:
        if rec.get("status") != "OPEN":
            continue
        rec_entry = safe_float(rec.get("entry_price", 0), 0.0)
        real_dir = str(rec.get("real_direction", "NEUTRAL")).upper()
        shadow_dir = str(rec.get("shadow_direction", "NEUTRAL")).upper()
        real_p = _v26_6_6_shadow_profit(real_dir, rec_entry, price)
        shadow_p = _v26_6_6_shadow_profit(shadow_dir, rec_entry, price)
        rec["real_profit"] = round(real_p, 3)
        rec["shadow_profit"] = round(shadow_p, 3)
        rec["real_MFE"] = round(max(safe_float(rec.get("real_MFE", 0), 0), real_p), 3)
        rec["real_MAE"] = round(min(safe_float(rec.get("real_MAE", 0), 0), real_p), 3)
        rec["shadow_MFE"] = round(max(safe_float(rec.get("shadow_MFE", 0), 0), shadow_p), 3)
        rec["shadow_MAE"] = round(min(safe_float(rec.get("shadow_MAE", 0), 0), shadow_p), 3)
        rec["original_vs_opposite_profit"] = round(real_p - shadow_p, 3)
        rec["would_opposite_have_won"] = shadow_p > 0
        rec["would_original_have_won"] = real_p > 0
        if now_ts - safe_int(rec.get("entry_timestamp", now_ts), now_ts) >= V26_6_6_SHADOW_AUDIT_HORIZON_SEC:
            rec["status"] = "CLOSED_AUDIT_HORIZON"

    if str(decision.get("decision", "")).upper() == "TRADE" and bias in ("BUY", "SELL") and entry > 0:
        signal_id = str(decision.get("directional_idea_id") or f"{safe_int(decision.get('market_state_sequence_id', 0), 0)}:{bias}:{round(entry, 3)}")
        if not any(rec.get("signal_id") == signal_id for rec in records):
            records.append({
                "signal_id": signal_id,
                "entry_timestamp": now_ts,
                "entry_price": round(entry, 3),
                "real_direction": bias,
                "shadow_direction": _v26_6_6_opposite_direction(bias),
                "real_profit": 0.0,
                "shadow_profit": 0.0,
                "real_MFE": 0.0,
                "real_MAE": 0.0,
                "shadow_MFE": 0.0,
                "shadow_MAE": 0.0,
                "original_vs_opposite_profit": 0.0,
                "would_opposite_have_won": False,
                "would_original_have_won": False,
                "status": "OPEN",
            })

    open_records = [rec for rec in records if rec.get("status") == "OPEN"]
    try:
        LOCAL_SHADOW_AUDIT_PATH.parent.mkdir(parents=True, exist_ok=True)
        LOCAL_SHADOW_AUDIT_PATH.write_text(json.dumps(records[-500:], indent=2), encoding="utf-8")
    except Exception as exc:
        decision["shadow_audit_write_error"] = str(exc)

    latest = open_records[-1] if open_records else {}
    decision["shadow_opposite_audit_enabled"] = True
    decision["shadow_audit_path"] = str(LOCAL_SHADOW_AUDIT_PATH)
    decision["real_direction"] = bias if bias in ("BUY", "SELL") else "NEUTRAL"
    decision["shadow_direction"] = _v26_6_6_opposite_direction(decision["real_direction"])
    for key in ("real_profit", "shadow_profit", "real_MFE", "real_MAE", "shadow_MFE", "shadow_MAE", "original_vs_opposite_profit", "would_opposite_have_won", "would_original_have_won"):
        decision[key] = latest.get(key, 0 if key.startswith(("real_", "shadow_", "original")) else False)
    return decision


def classify_loss_reason_v26_6_2(decision, stats):
    """Classify the latest realized loss using existing telemetry only."""
    row = stats.get("last_loss_row", {}) if isinstance(stats, dict) else {}
    explicit = str(_v26_6_2_row_value(row, ("loss_reason", "exit_reason", "reason", "final_gate_reason"), "")).upper()
    allowed = {
        "LATE_ENTRY", "EXHAUSTION_ENTRY", "CHOP_ENTRY", "REVERSAL_ENTRY",
        "SL_TOO_WIDE", "BE_TOO_TIGHT", "TREND_THESIS_FAILED", "EXECUTOR_MANAGEMENT_FAILURE",
    }
    for reason in allowed:
        if reason in explicit:
            return reason

    late_score = safe_int(decision.get("late_entry_score", decision.get("late_entry_score_v26_6", 0)), 0)
    location_score = safe_int(decision.get("entry_location_score", decision.get("entry_location_score_v26_5", 0)), 0)
    exhaustion_score = safe_int(decision.get("exhaustion_score", decision.get("runner_risk_score", 0)), 0)
    mode = str(decision.get("market_mode", decision.get("mode", ""))).upper()
    bb_state = str(decision.get("bb_state", decision.get("bb", ""))).upper()
    management = str(decision.get("management", decision.get("mgmt", ""))).upper()
    max_loss = safe_float(decision.get("max_realized_loss_usd_001_lot", V26_6_2_MAX_REALIZED_LOSS_USD_001_LOT), V26_6_2_MAX_REALIZED_LOSS_USD_001_LOT)
    latest_loss = abs(safe_float(stats.get("last_loss_profit", 0.0), 0.0))

    if latest_loss > max_loss * 1.05:
        return "SL_TOO_WIDE"
    if "BE" in explicit and "TIGHT" in explicit:
        return "BE_TOO_TIGHT"
    if late_score >= V26_6_LATE_ENTRY_SIZE_REDUCE_SCORE:
        return "LATE_ENTRY"
    if exhaustion_score >= 70 or "EXHAUST" in explicit:
        return "EXHAUSTION_ENTRY"
    if bb_state == "NORMAL" and mode == "TRANSITION":
        return "CHOP_ENTRY"
    if "REVERSAL" in bb_state or "CHOCH" in explicit or "REVERSAL" in explicit:
        return "REVERSAL_ENTRY"
    if safe_int(stats.get("same_direction_loss_streak", 0), 0) >= 2:
        return "TREND_THESIS_FAILED"
    if management in ("HOLD_TRAIL", "TREND_RUNNER", "SCALP_TP") and location_score >= V26_5_ENTRY_LOCATION_MIN_EXECUTE:
        return "EXECUTOR_MANAGEMENT_FAILURE"
    return "TREND_THESIS_FAILED"


def apply_adaptive_size_down_v26_6_2(decision, reason):
    """Reduce exposure after losses without stopping participation."""
    current_fraction = safe_float(decision.get("risk_fraction", decision.get("position_size_multiplier", 1.0)), 1.0)
    reduced = min(current_fraction, V26_6_2_ADAPTIVE_SIZE_DOWN_FRACTION)
    extreme_caution = "extreme caution" in str(reason).lower()
    decision["adaptive_size_down_active"] = True
    decision["adaptive_size_down_reason"] = reason
    decision["management_downgrade"] = "EXPLICIT_SCALP_DOWNGRADE"
    decision["management_downgrade_reason"] = reason
    decision["risk_fraction"] = round(reduced, 2)
    decision["position_size_multiplier"] = round(reduced, 2)
    decision["active_execution_leg"] = "A"
    decision["adaptive_allowed_legs"] = ["A"]
    decision["runner_allowed"] = False
    decision["runner_disabled"] = True
    decision["runner_disable_reason"] = reason
    decision["pyramid_allowed"] = False
    decision["continuation_add_allowed"] = False
    decision["runner_add_allowed"] = False
    decision["no_runner"] = True
    decision["no_pyramid"] = True
    decision["tighter_risk_cap_active"] = True
    decision["tighter_risk_cap_usd_001_lot"] = round(
        min(
            V26_6_3_EXTREME_CAUTION_LOSS_CAP_USD_001_LOT if extreme_caution else V26_6_2_FLOATING_FORCE_EXIT_USD_001_LOT,
            V26_6_2_MAX_REALIZED_LOSS_USD_001_LOT,
        ),
        2,
    )
    if extreme_caution:
        decision["extreme_caution_mode"] = True
        decision["extreme_caution_rules"] = [
            "Leg A only",
            "reduced size",
            "no runner",
            "no continuation add",
            "tighter loss cap",
        ]
        decision["max_realized_loss_usd_001_lot"] = min(
            safe_float(decision.get("max_realized_loss_usd_001_lot", V26_6_2_MAX_REALIZED_LOSS_USD_001_LOT), V26_6_2_MAX_REALIZED_LOSS_USD_001_LOT),
            V26_6_3_EXTREME_CAUTION_LOSS_CAP_USD_001_LOT,
        )
        decision["floating_force_exit_usd_001_lot"] = min(
            safe_float(decision.get("floating_force_exit_usd_001_lot", V26_6_2_FLOATING_FORCE_EXIT_USD_001_LOT), V26_6_2_FLOATING_FORCE_EXIT_USD_001_LOT),
            V26_6_3_EXTREME_CAUTION_LOSS_CAP_USD_001_LOT,
        )
    decision["adaptive_recovery_condition"] = "return to normal size only after valid recovery trade or improved entry_location_score"
    if isinstance(decision.get("execution_legs"), list):
        for leg in decision["execution_legs"]:
            if str(leg.get("leg", "")).upper() in ("B", "C"):
                leg["enabled"] = False
                leg["disabled_reason"] = reason
    if str(decision.get("decision", "")).upper() == "TRADE":
        decision["execution_state"] = "EXECUTE_CAUTIOUS"
        decision["management"] = "SCALP_TP"
        decision["mgmt"] = "SCALP_TP"
    return decision


def apply_thesis_revalidation_after_loss_v26_6_2(decision, stats, loss_reason):
    bias = str(decision.get("action", decision.get("bias", decision.get("intended_action", "NEUTRAL")))).upper()
    location_score = safe_int(decision.get("entry_location_score", decision.get("entry_location_score_v26_5", 0)), 0)
    exhaustion_score = safe_int(decision.get("exhaustion_score", decision.get("runner_risk_score", 0)), 0)
    score_gap = safe_int(decision.get("score_gap", 0), 0)
    bb_state = str(decision.get("bb_state", decision.get("bb", "NORMAL"))).upper()
    mode = str(decision.get("market_mode", decision.get("mode", "TRANSITION"))).upper()
    rsi = safe_float(decision.get("rsi", 50), 50)
    macd_hist = safe_float(decision.get("macd_hist", 0), 0)
    repeated_same_direction = safe_int(stats.get("same_direction_loss_streak", 0), 0) >= 2
    thesis_valid = (
        bias in ("BUY", "SELL")
        and score_gap >= V26_6_2_MIN_SCORE_GAP
        and location_score >= V26_5_ENTRY_LOCATION_MIN_EXECUTE
        and exhaustion_score < 80
        and not (mode == "TRANSITION" and bb_state == "NORMAL" and loss_reason in ("CHOP_ENTRY", "TREND_THESIS_FAILED"))
    )
    decision["thesis_revalidation_after_loss"] = "ACTIVE" if repeated_same_direction else "NOT_REQUIRED"
    decision["thesis_revalidation_inputs"] = {
        "bias": bias,
        "mode": mode,
        "bb_state": bb_state,
        "rsi": round(rsi, 2),
        "macd_hist": round(macd_hist, 3),
        "entry_location_score": location_score,
        "exhaustion_score": exhaustion_score,
        "score_gap": score_gap,
        "loss_reason": loss_reason,
    }
    decision["thesis_revalidation_result"] = "VALID_CONTINUE_CAUTIOUS" if thesis_valid else "INVALID_WAIT_OR_OPPOSITE_EVALUATION"
    if repeated_same_direction and thesis_valid:
        decision = apply_adaptive_size_down_v26_6_2(decision, "same-direction loss cluster; thesis revalidated, continue cautiously")
    elif repeated_same_direction and not thesis_valid:
        decision["decision"] = "NO_TRADE"
        decision["entry_allowed"] = False
        decision["execution_state"] = "WAIT"
        decision["wait_state"] = "WAIT_ENTRY_LOCATION"
        decision["wait_reason"] = "same-direction losses invalidated thesis; re-check entry location or evaluate opposite thesis"
        decision["next_trigger"] = "bias/mode/BB/RSI/MACD/location/exhaustion reset or opposite thesis evaluation"
        decision["opposite_thesis_evaluation_required"] = True
    if (
        safe_int(stats.get("same_direction_loss_streak", 0), 0) >= V26_6_6_DIRECTION_LOSS_PAUSE_STREAK
        and bias == str(stats.get("last_loss_direction", "UNKNOWN")).upper()
    ):
        decision["directional_loss_pause_active"] = True
        decision["loss_cluster_direction"] = bias
        decision["paused_direction"] = bias
        decision["directional_pause_policy"] = "PAUSE_LOSING_DIRECTION_ONLY_BUY_OR_SELL_OPPOSITE_REMAINS_ALLOWED"
        decision["directional_pause_release_condition"] = "fresh continuation confirmation, new structural setup, or exhaustion reset"
        if str(decision.get("decision", "")).upper() == "TRADE":
            decision["decision"] = "NO_TRADE"
            decision["entry_allowed"] = False
            decision["execution_state"] = "WAIT"
            decision["wait_state"] = "WAIT_ENTRY_WINDOW"
            decision["wait_reason"] = f"{bias} paused after 3 same-direction losses; opposite thesis remains evaluable"
            decision["management"] = "NO_TRADE"
            decision["mgmt"] = "NO_TRADE"
    else:
        decision.setdefault("directional_loss_pause_active", False)
        decision.setdefault("loss_cluster_direction", stats.get("last_loss_direction", "UNKNOWN"))
    return decision


def apply_session_loss_governor_v26_6_2(decision):
    """Diagnose losses and adapt risk; do not pause or session-stop except catastrophic hard risk."""
    if not isinstance(decision, dict):
        return decision
    stats = _v26_6_2_trade_memory_session_stats()
    consecutive_losses = max(safe_int(decision.get("consecutive_losses", 0), 0), safe_int(stats.get("consecutive_losses", 0), 0))
    loss_reason = classify_loss_reason_v26_6_2(decision, stats) if consecutive_losses > 0 else "NONE"

    decision["session_loss_governor"] = "V26.6.3_EXIT_RISK_ASYMMETRY_GOVERNOR"
    decision["trade_memory_source"] = stats.get("path", "")
    decision["daily_net_pnl"] = stats.get("daily_net", 0.0)
    decision["daily_drawdown_caution_usd"] = V26_6_2_DAILY_DRAWDOWN_CAUTION_USD
    decision["catastrophic_daily_stop_usd"] = V26_6_2_CATASTROPHIC_DAILY_STOP_USD
    decision["consecutive_losses"] = consecutive_losses
    decision["same_direction_loss_streak"] = safe_int(stats.get("same_direction_loss_streak", 0), 0)
    decision["last_loss_direction"] = stats.get("last_loss_direction", "UNKNOWN")
    decision["last_loss_age_sec"] = stats.get("last_loss_age_sec", 999999)
    decision["loss_reason_classifier"] = loss_reason
    decision["loss_cluster_pause_active"] = False
    decision["loss_cluster_pause_seconds"] = 0
    decision["loss_cluster_pause_remaining_sec"] = 0
    decision["loss_cluster_pause_policy"] = "DIAGNOSTIC_ONLY_NO_AUTOMATIC_EXECUTION_STOP"
    decision["session_stop_active"] = False
    decision["daily_kill_switch_policy"] = "V26.6.3: if net daily loss <= -$5.00 disable new entries only; keep open position management active"

    daily_net = safe_float(stats.get("daily_net", 0.0), 0.0)
    if daily_net <= V26_6_2_CATASTROPHIC_DAILY_STOP_USD:
        decision["session_stop_active"] = True
        decision["session_stop_reason"] = f"catastrophic hard-risk daily net {daily_net:.2f} <= {V26_6_2_CATASTROPHIC_DAILY_STOP_USD:.2f}"
        if str(decision.get("decision", "")).upper() == "TRADE":
            return _v26_6_2_block_trade(decision, "V26_6_3_DAILY_EMERGENCY_RISK_STOP", "V26.6.3 daily emergency risk stop: disable new entries at <= -$5.00")
        return decision

    if daily_net <= V26_6_2_DAILY_DRAWDOWN_CAUTION_USD:
        decision["drawdown_caution_mode"] = True
        decision["daily_drawdown_protection_active"] = False
        decision["daily_drawdown_response"] = "DRAWDOWN_CAUTION_MODE_REDUCE_SIZE_LEG_A_ONLY_HIGHER_ENTRY_SCORE_NO_STOP"
        if safe_int(decision.get("entry_location_score", 0), 0) < V26_6_2_DRAWDOWN_CAUTION_MIN_ENTRY_SCORE:
            decision["decision"] = "NO_TRADE"
            decision["entry_allowed"] = False
            decision["execution_state"] = "WAIT"
            decision["wait_state"] = "WAIT_ENTRY_LOCATION"
            decision["wait_reason"] = "drawdown caution requires higher entry_location_score"
            decision["next_trigger"] = f"entry_location_score >= {V26_6_2_DRAWDOWN_CAUTION_MIN_ENTRY_SCORE}"
        else:
            decision = apply_adaptive_size_down_v26_6_2(decision, "daily drawdown caution mode")
    else:
        decision["drawdown_caution_mode"] = False

    if consecutive_losses > 0:
        decision = apply_thesis_revalidation_after_loss_v26_6_2(decision, stats, loss_reason)
    if consecutive_losses >= V26_6_3_EXTREME_CAUTION_LOSS_STREAK and str(decision.get("decision", "")).upper() == "TRADE":
        decision = apply_adaptive_size_down_v26_6_2(decision, "3 consecutive losses extreme caution mode")
    elif consecutive_losses >= 2 and str(decision.get("decision", "")).upper() == "TRADE":
        decision = apply_adaptive_size_down_v26_6_2(decision, "loss cluster adaptive size-down; no pause")
    return decision

def apply_late_entry_guard_v26_6(decision):
    """Final maturity guard so later recovery layers cannot chase mature moves."""
    if not isinstance(decision, dict):
        return decision
    score = safe_int(decision.get("late_entry_score", decision.get("late_entry_score_v26_6", 0)), 0)
    bias = str(decision.get("action", decision.get("bias", decision.get("intended_action", "NEUTRAL")))).upper()
    if score >= V26_6_LATE_ENTRY_WAIT_SCORE and bias in ("BUY", "SELL"):
        decision["decision"] = "NO_TRADE"
        decision["entry_allowed"] = False
        decision["execution_state"] = "WAIT"
        decision["wait_state"] = "WAIT_ENTRY_LOCATION"
        decision["wait_reason"] = "late-entry score high; do not chase mature move"
        decision["next_trigger"] = "pullback/reset before participation"
        decision["intended_action"] = bias
        decision["management"] = "NO_TRADE"
        decision["mgmt"] = "NO_TRADE"
        decision["late_entry_action"] = "WAIT_ENTRY_LOCATION"
        if "V26_6_LATE_ENTRY_WAIT" not in str(decision.get("reason", "")):
            decision["reason"] = (str(decision.get("reason", "")) + f" | V26_6_LATE_ENTRY_WAIT score={score}").strip()
    elif score >= V26_6_LATE_ENTRY_SIZE_REDUCE_SCORE:
        current_fraction = safe_float(decision.get("risk_fraction", 1.0), 1.0)
        reduced = min(current_fraction, 0.25)
        decision["risk_fraction"] = round(reduced, 2)
        decision["position_size_multiplier"] = round(reduced, 2)
        decision["late_entry_action"] = "REDUCE_SIZE"
    return decision


def apply_exhaustion_protection_v26_6_6(decision):
    """Downgrade only clear mature-move exhaustion; do not reduce broad entry frequency."""
    if not isinstance(decision, dict):
        return decision
    bias = str(decision.get("action", decision.get("bias", "NEUTRAL"))).upper()
    score = max(
        safe_int(decision.get("late_entry_score", decision.get("late_entry_score_v26_6", 0)), 0),
        safe_int(decision.get("exhaustion_score", decision.get("trend_exhaustion_score", 0)), 0),
        safe_int(decision.get("master_gate_score", 0), 0),
    )
    expansion = safe_int(decision.get("expansion_candle_count", 0), 0)
    factors = list(decision.get("late_entry_factors", [])) if isinstance(decision.get("late_entry_factors", []), list) else []
    mature_move = (
        expansion >= 3
        or bool(decision.get("rsi_compression_after_expansion", False))
        or bool(decision.get("exhausted_macd_expansion", False))
        or safe_float(decision.get("bb_overextension_ratio", 0.0), 0.0) >= DIST_BB_MID_EXTREME_RATIO
    )
    decision["exhaustion_score_at_entry"] = score
    decision["entry_age_after_move"] = expansion
    decision["exhaustion_protection_policy"] = "WAIT high exhaustion; otherwise reduce size/disable runner/scalp-only without global no-trade"
    if str(decision.get("decision", "")).upper() == "TRADE" and bias in ("BUY", "SELL") and score >= V26_6_6_EXHAUSTION_WAIT_SCORE and mature_move:
        decision["decision"] = "NO_TRADE"
        decision["entry_allowed"] = False
        decision["execution_state"] = "WAIT"
        decision["wait_state"] = "WAIT_ENTRY_WINDOW"
        decision["wait_reason"] = f"high exhaustion risk score={score}; wait for reset/resumption window"
        decision["exhaustion_action"] = "WAIT_ENTRY_WINDOW"
        decision["intended_action"] = bias
        decision["management"] = "NO_TRADE"
        decision["mgmt"] = "NO_TRADE"
        decision["reason"] = (str(decision.get("reason", "")) + " | V26_6_6_EXHAUSTION_WAIT_ENTRY_WINDOW").strip()
    elif str(decision.get("decision", "")).upper() == "TRADE" and score >= V26_6_6_EXHAUSTION_SCALP_ONLY_SCORE:
        decision["exhaustion_action"] = "SCALP_ONLY_REDUCED_SIZE_NO_RUNNER"
        decision["risk_fraction"] = round(min(safe_float(decision.get("risk_fraction", 1.0), 1.0), 0.25), 2)
        decision["position_size_multiplier"] = decision["risk_fraction"]
        decision["runner_allowed"] = False
        decision["runner_disabled"] = True
        decision["runner_disable_reason"] = f"V26.6.6 exhaustion risk score={score}; factors={'; '.join(map(str, factors[:4]))}"
        decision["management"] = "SCALP_TP"
        decision["mgmt"] = "SCALP_TP"
    else:
        decision.setdefault("exhaustion_action", "ALLOW")
    return decision


def _v26_6_recent_expansion_count(bias, data):
    opens, highs, lows, closes = get_pullback_candles(data)
    if len(closes) < 2:
        return 0
    count = 0
    for o, h, l, c in zip(opens[:5], highs[:5], lows[:5], closes[:5]):
        if _trend_side(bias, o, c) and _body_ratio(o, h, l, c) >= PULLBACK_EXPANSION_BODY_RATIO:
            count += 1
        else:
            break
    return count


def enrich_late_entry_score_v26_6(decision, data, market_mode, bb_state, bb_extreme):
    """Compute LATE_ENTRY_SCORE using existing RSI/BB/MA/MACD/candle-expansion inputs."""
    if not isinstance(decision, dict) or not isinstance(data, dict):
        return decision
    bias = str(decision.get("action", decision.get("bias", "NEUTRAL"))).upper()
    if bias not in ("BUY", "SELL"):
        return decision
    bid = safe_float(data.get("bid", decision.get("bid", decision.get("price", 0))), 0)
    ma50 = safe_float(data.get("ma50", decision.get("ma50", 0)), 0)
    rsi = safe_float(data.get("rsi", decision.get("rsi", 50)), 50)
    macd = safe_float(data.get("macd_hist", decision.get("macd_hist", 0)), 0)
    upper = safe_float(data.get("bb_upper", decision.get("bb_upper", decision.get("bb_upper2", 0))), 0)
    mid = safe_float(data.get("bb_middle", data.get("bb_mid", decision.get("bb_middle", decision.get("bb_mid", 0)))), 0)
    lower = safe_float(data.get("bb_lower", decision.get("bb_lower", decision.get("bb_lower2", 0))), 0)
    expansion_count = _v26_6_recent_expansion_count(bias, data)
    base_late = safe_int(decision.get("late_entry_score", 0), 0)
    score = base_late
    factors = []

    dist_ma50 = _eti_pct_distance(bid, ma50)
    bb_overextension = _eti_bb_mid_ratio(bid, upper, mid, lower)
    edge = _eti_bb_edge_pos(bias, bid, upper, lower)
    rsi_compressed_after_expansion = expansion_count >= 2 and ((bias == "BUY" and rsi < 58) or (bias == "SELL" and rsi > 42))
    exhausted_macd_expansion = (bias == "BUY" and 0 < macd <= MACD_DECAY_ABS_WEAK) or (bias == "SELL" and -MACD_DECAY_ABS_WEAK <= macd < 0)

    if rsi_compressed_after_expansion:
        score += 15; factors.append(f"RSI compression after expansion rsi={rsi:.1f} expansion={expansion_count}")
    if edge >= VERTICAL_BB_EDGE_RATIO or bb_overextension >= DIST_BB_MID_EXTREME_RATIO:
        score += 15; factors.append(f"BB overextension edge={edge:.2f} mid_ratio={bb_overextension:.2f}")
    if dist_ma50 >= DIST_MA50_EXTREME_PCT:
        score += 12; factors.append(f"distance from MA50={dist_ma50:.4f}")
    if exhausted_macd_expansion:
        score += 12; factors.append(f"exhausted MACD expansion macd={macd:.2f}")
    if expansion_count >= 3:
        score += 18; factors.append(f"expansion candle count={expansion_count}")
    elif expansion_count == 2:
        score += 10; factors.append("expansion candle count=2")
    if bb_extreme in ("DEV4_UPPER", "DEV4_LOWER"):
        score += 15; factors.append(f"dev4 overextension={bb_extreme}")

    score = clamp_int(score, 0, 100)
    decision["late_entry_score"] = score
    decision["late_entry_score_v26_6"] = score
    decision["late_entry_factors"] = factors
    decision["expansion_candle_count"] = expansion_count
    decision["rsi_compression_after_expansion"] = bool(rsi_compressed_after_expansion)
    decision["bb_overextension_ratio"] = round(bb_overextension, 3)
    decision["ma50_distance_pct"] = round(dist_ma50, 5)
    decision["exhausted_macd_expansion"] = bool(exhausted_macd_expansion)
    if score >= V26_6_LATE_ENTRY_WAIT_SCORE and str(decision.get("decision", "")).upper() == "TRADE":
        decision["decision"] = "NO_TRADE"
        decision["entry_allowed"] = False
        decision["execution_state"] = "WAIT"
        decision["wait_state"] = "WAIT_ENTRY_LOCATION"
        decision["wait_reason"] = "late-entry score high; do not chase mature move"
        decision["next_trigger"] = "pullback/reset before participation"
        decision["intended_action"] = bias
        decision["management"] = "NO_TRADE"
        decision["mgmt"] = "NO_TRADE"
        decision["reason"] = (str(decision.get("reason", "")) + f" | V26_6_LATE_ENTRY_WAIT score={score}").strip()
    elif score >= V26_6_LATE_ENTRY_SIZE_REDUCE_SCORE:
        current_fraction = safe_float(decision.get("risk_fraction", 1.0), 1.0)
        reduced = min(current_fraction, 0.25)
        decision["risk_fraction"] = round(reduced, 2)
        decision["position_size_multiplier"] = round(reduced, 2)
        decision["late_entry_action"] = "REDUCE_SIZE"
        decision["late_entry_reason_v26_6"] = "late-entry score elevated; size compressed instead of chasing full risk"
    else:
        decision["late_entry_action"] = "ALLOW"
        decision["late_entry_reason_v26_6"] = "late-entry score acceptable"
    return decision


def _participation_key(prefix, bias, mode, bb):
    return f"{prefix}:{bias}:{mode}:{bb}"


def reset_wait_valid_lifecycle(reason=""):
    if wait_valid_state:
        wait_valid_state.clear()
    return reason


def apply_wait_valid_timeout_recovery(decision, bias, mode, bb, hard_block=False):
    """
    V26.4.7 WAIT_VALID recovery.

    WAIT_VALID is a temporary lifecycle state. Once a valid directional setup has
    waited too many consecutive runtime cycles without a hard safety block, it is
    released into EXECUTE_CAUTIOUS so participation datasets can be generated.
    """
    if not isinstance(decision, dict):
        return decision

    if hard_block or bias not in ("BUY", "SELL"):
        reset_wait_valid_lifecycle("wait reset: no valid directional authority or hard block")
        return decision

    key = _participation_key("WAIT_VALID", bias, mode, bb)
    stale_keys = [k for k in wait_valid_state if k != key]
    for stale_key in stale_keys:
        wait_valid_state.pop(stale_key, None)

    count = safe_int(wait_valid_state.get(key, 0), 0) + 1
    wait_valid_state[key] = count
    decision["wait_timeout_cycles"] = WAIT_TIMEOUT_CYCLES
    decision["wait_valid_cycles"] = count
    decision["wait_recovery_lifecycle"] = "TIMEOUT_RELEASED" if count > WAIT_TIMEOUT_CYCLES else "ACTIVE"

    if count > WAIT_TIMEOUT_CYCLES:
        decision["decision"] = "TRADE"
        decision["entry_allowed"] = True
        decision["execution_state"] = "EXECUTE_CAUTIOUS"
        decision["management"] = "SCALP_TP"
        decision["mgmt"] = "SCALP_TP"
        decision["market_style"] = "SCALP"
        decision["bias"] = bias
        decision["action"] = bias
        decision["intended_action"] = bias
        decision["wait_state"] = "WAIT_TIMEOUT_RELEASED"
        decision["wait_reason"] = "WAIT_VALID timeout released to controlled participation"
        decision["next_trigger"] = "executing cautiously after finite wait lifecycle"
        decision["participation_release"] = True
        decision["participation_release_reason"] = f"WAIT_VALID cycles {count}>{WAIT_TIMEOUT_CYCLES}; EXECUTE_CAUTIOUS"
        decision["reason"] = (str(decision.get("reason", "")) + " | V26_4_7_WAIT_TIMEOUT_EXECUTE_CAUTIOUS").strip()
    return decision



def _protection_bool(value):
    if isinstance(value, bool):
        return value
    return str(value).upper() in ("1", "TRUE", "YES", "ACTIVE", "ON")


def _protection_state_template(state):
    spec = PROTECTION_RELEASE_CONDITIONS[state]
    return {
        "state": "INACTIVE",
        "entry_condition": spec["entry_condition"],
        "exit_condition": spec["exit_condition"],
        "maximum_duration_sec": spec["maximum_duration_sec"],
        "maximum_cycles": spec["maximum_cycles"],
        "recovery_path": spec["recovery_path"],
        "duration_sec": 0,
        "cycles": 0,
        "activation_count": safe_int(protection_authority_state["activation_counts"].get(state, 0), 0),
    }


def _detect_protection_candidates(decision):
    """Return protection candidates detected on the current decision packet."""
    candidates = []
    wait_state = str(decision.get("wait_state", "")).upper()
    reason = str(decision.get("reason", "")).upper()

    if _protection_bool(decision.get("session_profit_protection_active", False)) or _protection_bool(decision.get("profit_protection_active", False)):
        candidates.append("SESSION_PROFIT_PROTECTION")
    if _protection_bool(decision.get("drawdown_caution_mode", False)) or _protection_bool(decision.get("daily_peak_drawdown_protection_active", False)) or _protection_bool(decision.get("daily_drawdown_protection_active", False)):
        candidates.append("DAILY_PEAK_DRAWDOWN_PROTECTION")
    if _protection_bool(decision.get("thesis_revalidation_after_loss", False)) or safe_int(decision.get("same_direction_loss_streak", 0), 0) >= 2:
        candidates.append("THESIS_REVALIDATION_AFTER_LOSS")
    if wait_state == "WAIT_VALID" or _protection_bool(decision.get("transition_decay_active", False)) or "THESIS_DECAY" in reason or "TRANSITION_WAIT" in reason:
        candidates.append("THESIS_DECAY_WAIT")
    if _protection_bool(decision.get("continuation_reentry_block", False)) or _protection_bool(decision.get("post_runner_cooldown_active", False)) or "CONTINUATION_REENTRY_COOLDOWN" in reason:
        candidates.append("POST_RUNNER_COOLDOWN")
    if wait_state == "WAIT_ENTRY_LOCATION" or _protection_bool(decision.get("entry_quality_block", False)) or "ENTRY_LOCATION_WAIT" in reason:
        candidates.append("WAIT_ENTRY_LOCATION")

    # Generic cooldown waits are mapped into post-runner cooldown governance so
    # they cannot stack on top of a location/thesis wait.
    if _protection_bool(decision.get("cooldown_wait_active", False)) or _protection_bool(decision.get("cooldown_active", False)):
        candidates.append("POST_RUNNER_COOLDOWN")

    # Preserve configured priority and de-duplicate.
    return sorted(set(candidates), key=lambda state: PROTECTION_PRIORITY[state])


def _protection_location_recovered(decision):
    score = safe_int(decision.get("entry_location_score", decision.get("entry_location_score_v26_5", 0)), 0)
    late_score = safe_int(decision.get("late_entry_score", decision.get("late_entry_score_v26_6", 0)), 0)
    return score >= V26_5_ENTRY_LOCATION_MIN_EXECUTE and late_score < V26_6_LATE_ENTRY_WAIT_SCORE


def _protection_directional_recovery(decision):
    bias = str(decision.get("action", decision.get("bias", decision.get("intended_action", "NEUTRAL")))).upper()
    dominance = _protection_bool(decision.get("directional_dominance_active", False))
    gap = safe_int(decision.get("score_gap", 0), 0)
    return bias in ("BUY", "SELL") and (dominance or gap >= V26_6_MIN_PARTICIPATION_GAP)


def apply_protection_authority_manager_v26_6_1(decision, allow_release=True, count_cycle=True):
    """
    V26.6.1 Protection Authority Manager.

    Publishes ACTIVE_PROTECTION_STATE and enforces that only one protection state
    can be ACTIVE. Every protection advertises entry/exit/max duration and WAIT-
    like states get an explicit timeout recovery path.
    """
    if not isinstance(decision, dict):
        return decision

    now_ts = int(time.time())
    candidates = _detect_protection_candidates(decision)
    selected = candidates[0] if candidates else "NONE"
    previous = str(protection_authority_state.get("active_state", "NONE"))

    if count_cycle:
        if selected != previous:
            if selected != "NONE":
                protection_authority_state["activation_counts"][selected] = safe_int(
                    protection_authority_state["activation_counts"].get(selected, 0), 0
                ) + 1
                protection_authority_state["active_since_ts"] = now_ts
                protection_authority_state["active_cycles"] = 1
                protection_authority_state["recovery_started_ts"] = now_ts
            else:
                started = safe_int(protection_authority_state.get("recovery_started_ts", 0), 0)
                protection_authority_state["last_recovery_sec"] = max(0, now_ts - started) if started > 0 else 0
                protection_authority_state["active_since_ts"] = 0
                protection_authority_state["active_cycles"] = 0
                protection_authority_state["recovery_started_ts"] = 0
            protection_authority_state["active_state"] = selected
        elif selected != "NONE":
            protection_authority_state["active_cycles"] = safe_int(protection_authority_state.get("active_cycles", 0), 0) + 1

    active_since = safe_int(protection_authority_state.get("active_since_ts", 0), 0)
    duration = max(0, now_ts - active_since) if selected != "NONE" and active_since > 0 else 0
    cycles = safe_int(protection_authority_state.get("active_cycles", 0), 0) if selected != "NONE" else 0

    registry = {state: _protection_state_template(state) for state in PROTECTION_AUTHORITY_STATES}
    timed_out = False
    recovered = False
    release_reason = ""
    if selected != "NONE":
        spec = PROTECTION_RELEASE_CONDITIONS[selected]
        timed_out = duration >= spec["maximum_duration_sec"] or cycles > spec["maximum_cycles"]
        recovered = (
            (selected == "WAIT_ENTRY_LOCATION" and _protection_location_recovered(decision))
            or (selected == "THESIS_DECAY_WAIT" and _protection_directional_recovery(decision) and cycles > WAIT_TIMEOUT_CYCLES)
            or (selected == "POST_RUNNER_COOLDOWN" and not _protection_bool(decision.get("continuation_reentry_block", False)) and not _protection_bool(decision.get("cooldown_wait_active", False)))
            or (selected == "THESIS_REVALIDATION_AFTER_LOSS" and _protection_directional_recovery(decision))
            or (selected == "SESSION_PROFIT_PROTECTION" and not _protection_bool(decision.get("session_profit_protection_active", False)) and not _protection_bool(decision.get("profit_protection_active", False)))
            or (selected == "DAILY_PEAK_DRAWDOWN_PROTECTION" and not _protection_bool(decision.get("daily_peak_drawdown_protection_active", False)) and not _protection_bool(decision.get("daily_drawdown_protection_active", False)))
        )
        if timed_out:
            release_reason = f"{selected} maximum duration reached cycles={cycles} duration_sec={duration}"
        elif recovered:
            release_reason = f"{selected} exit condition satisfied"

    active_for_output = selected
    if allow_release and selected != "NONE" and (timed_out or recovered):
        active_for_output = "NONE"
        protection_authority_state["active_state"] = "NONE"
        protection_authority_state["last_recovery_sec"] = duration
        protection_authority_state["active_since_ts"] = 0
        protection_authority_state["active_cycles"] = 0
        if selected in ("WAIT_ENTRY_LOCATION", "THESIS_DECAY_WAIT") and _protection_directional_recovery(decision):
            bias = str(decision.get("action", decision.get("bias", decision.get("intended_action", "NEUTRAL")))).upper()
            decision["decision"] = "TRADE"
            decision["entry_allowed"] = True
            decision["execution_state"] = "EXECUTE_CAUTIOUS"
            decision["management"] = "SCALP_TP" if str(decision.get("management", "")).upper() in ("", "NO_TRADE") else decision.get("management", "SCALP_TP")
            decision["mgmt"] = decision["management"]
            decision["bias"] = bias
            decision["action"] = bias
            decision["intended_action"] = bias
            decision["wait_state"] = f"{selected}_RELEASED"
            decision["wait_reason"] = release_reason
            decision["participation_release"] = True
            decision["participation_release_reason"] = release_reason

    protection_authority_state["opportunity_block_count"] = safe_int(protection_authority_state.get("opportunity_block_count", 0), 0)
    if active_for_output != "NONE" and str(decision.get("decision", "")).upper() != "TRADE":
        protection_authority_state["opportunity_block_count"] += 1

    for state in PROTECTION_AUTHORITY_STATES:
        if state == active_for_output:
            registry[state]["state"] = "ACTIVE"
            registry[state]["duration_sec"] = duration
            registry[state]["cycles"] = cycles
        elif state in candidates:
            registry[state]["state"] = "PENDING"
        registry[state]["activation_count"] = safe_int(protection_authority_state["activation_counts"].get(state, 0), 0)

    decision["ACTIVE_PROTECTION_STATE"] = active_for_output
    decision["active_protection_state"] = active_for_output
    decision["protection_authority_manager"] = "ACTIVE"
    decision["protection_states"] = registry
    decision["protection_activation_count"] = dict(protection_authority_state["activation_counts"])
    decision["protection_duration_sec"] = duration if active_for_output != "NONE" else 0
    decision["protection_duration_cycles"] = cycles if active_for_output != "NONE" else 0
    decision["opportunity_block_count"] = safe_int(protection_authority_state.get("opportunity_block_count", 0), 0)
    decision["time_to_recovery_sec"] = safe_int(protection_authority_state.get("last_recovery_sec", 0), 0)
    decision["protection_pending_states"] = [state for state in candidates if state != active_for_output]
    decision["protection_release_reason"] = release_reason
    decision["protection_timeout_released"] = bool(timed_out and selected != "NONE")
    decision["protection_recovery_released"] = bool(recovered and selected != "NONE")
    decision["protection_expectancy_measurement"] = "compare protection_activation_count, protection_duration_sec, opportunity_block_count, time_to_recovery_sec against expectancy/profit-factor metrics"
    return decision

def _v26_5_points_distance(a, b):
    a = safe_float(a, 0.0)
    b = safe_float(b, 0.0)
    if a <= 0 or b <= 0:
        return 0.0
    return abs(a - b)


def _v26_5_bb_position(entry_price, bb_upper, bb_middle, bb_lower):
    width = safe_float(bb_upper, 0.0) - safe_float(bb_lower, 0.0)
    if entry_price <= 0 or width <= 0:
        return 0.5
    return clamp_float((entry_price - safe_float(bb_lower, 0.0)) / width, 0.0, 1.0)


def compute_entry_location_score_v26_5(decision):
    """
    V26.5 ENTRY_LOCATION_SCORE.

    Scores whether a correct directional idea is still worth entering at the
    current location. This intentionally reuses existing market-state outputs
    and does not introduce new indicators or classifier trees.
    """
    if not isinstance(decision, dict):
        return 50, [], []

    bias = str(decision.get("action", decision.get("bias", "NEUTRAL"))).upper()
    mode = str(decision.get("market_mode", decision.get("mode", "TRANSITION"))).upper()
    bb_state = str(decision.get("confirmed_bb_state", decision.get("bb_state", decision.get("bb", "NORMAL")))).upper()
    entry_price = safe_float(decision.get("entry_price", decision.get("price", decision.get("bid", 0))), 0.0)
    ma50 = safe_float(decision.get("ma50", 0), 0.0)
    bb_upper = safe_float(decision.get("bb_upper", 0), 0.0)
    bb_middle = safe_float(decision.get("bb_middle", 0), 0.0)
    bb_lower = safe_float(decision.get("bb_lower", 0), 0.0)
    rsi = safe_float(decision.get("rsi", 50), 50.0)
    score_gap = safe_int(decision.get("score_gap", 0), 0)
    late_score = safe_int(decision.get("late_entry_score", 0), 0)
    exhaustion_score = max(
        safe_int(decision.get("exhaustion_score", 0), 0),
        safe_int(decision.get("trend_exhaustion_score", 0), 0),
        safe_int(decision.get("master_gate_score", 0), 0),
        safe_int(decision.get("exhaustion_risk", 0), 0),
    )
    pullback_quality = safe_int(decision.get("pullback_quality", 0), 0)
    continuation_quality = safe_int(decision.get("continuation_quality", 0), 0)
    trend_quality = safe_int(decision.get("trend_quality", 0), 0)
    location_base = safe_int(decision.get("entry_location_score", 50), 50)
    bb_pos = _v26_5_bb_position(entry_price, bb_upper, bb_middle, bb_lower)
    dist_ma50 = _v26_5_points_distance(entry_price, ma50)
    bb_width = _v26_5_points_distance(bb_upper, bb_lower)
    dist_ma50_pct = (dist_ma50 / entry_price) if entry_price > 0 else 0.0
    bb_extension_ratio = 0.0
    if bb_width > 0 and bb_middle > 0:
        bb_extension_ratio = _v26_5_points_distance(entry_price, bb_middle) / bb_width

    score = 50
    positives = []
    negatives = []

    if location_base >= 65:
        score += 10
        positives.append(f"prior_location={location_base}")
    elif location_base <= ENTRY_LOCATION_BLOCK_SCORE:
        score -= 12
        negatives.append(f"prior_location={location_base}")

    if score_gap >= 5:
        score += 10
        positives.append(f"directional_dominance_gap={score_gap}")
    elif score_gap >= 3:
        score += 6
        positives.append(f"directional_edge_gap={score_gap}")

    if mode == "TREND" and pullback_quality >= PULLBACK_CONTINUATION_MIN_QUALITY:
        score += 16
        positives.append(f"healthy_pullback={pullback_quality}")
    elif mode == "TREND" and pullback_quality >= PULLBACK_MIN_QUALITY:
        score += 10
        positives.append(f"acceptable_pullback={pullback_quality}")

    if continuation_quality >= PULLBACK_ALLOW_RUNNER_QUALITY:
        score += 14
        positives.append(f"trend_continuation_pullback={continuation_quality}")
    elif continuation_quality >= PULLBACK_CONTINUATION_MIN_QUALITY:
        score += 8
        positives.append(f"continuation_return={continuation_quality}")

    if str(decision.get("continuation_return", False)).upper() in ("TRUE", "1", "YES"):
        score += 6
        positives.append("continuation_return_confirmed")

    if bb_state in ("WALK_UP", "WALK_DOWN") and mode == "TREND" and trend_quality >= CANDLE_MIN_TREND_QUALITY:
        score += 8
        positives.append(f"fresh_breakout_or_walk={bb_state}")

    if bias == "BUY" and bb_state == "WALK_UP" and 0.45 <= bb_pos <= 0.82:
        score += 8
        positives.append(f"buy_walk_not_extreme_pos={bb_pos:.2f}")
    if bias == "SELL" and bb_state == "WALK_DOWN" and 0.18 <= bb_pos <= 0.55:
        score += 8
        positives.append(f"sell_walk_not_extreme_pos={bb_pos:.2f}")

    exhaustion_state = str(decision.get("exhaustion_state", "")).upper()
    if exhaustion_state == "HIGH" or exhaustion_score >= EXHAUSTION_BLOCK_SCORE:
        score -= 28
        negatives.append(f"exhaustion_candle_or_stack={exhaustion_score}")
    elif exhaustion_score >= TREND_EXHAUSTION_WARN_LEVEL:
        score -= 16
        negatives.append(f"exhaustion_warning={exhaustion_score}")

    if (bias == "BUY" and rsi >= RSI_BUY_BLOWOFF) or (bias == "SELL" and rsi <= RSI_SELL_BLOWOFF):
        score -= 18
        negatives.append(f"extreme_rsi={rsi:.2f}")

    if dist_ma50_pct >= DIST_MA50_EXTREME_PCT and mode == "TREND":
        score -= 12
        negatives.append(f"distance_from_ma50={dist_ma50:.2f}")

    if bb_extension_ratio >= DIST_BB_MID_EXTREME_RATIO:
        score -= 12
        negatives.append(f"bb_overextension={bb_extension_ratio:.2f}")

    if late_score >= LATE_ENTRY_BLOCK_SCORE or str(decision.get("execution_timing_state", "")).upper() == "LATE_CONTINUATION":
        score -= 24
        negatives.append(f"late_expansion_entry={late_score}")
    elif late_score >= 50:
        score -= 10
        negatives.append(f"late_entry_warning={late_score}")

    if bb_state in ("REVERSAL_UP", "REVERSAL_DOWN", "DEV4_UPPER", "DEV4_LOWER"):
        reversal_against_location = (
            (bias == "BUY" and bb_state in ("REVERSAL_UP", "DEV4_UPPER"))
            or (bias == "SELL" and bb_state in ("REVERSAL_DOWN", "DEV4_LOWER"))
        )
        if reversal_against_location:
            score -= 20
            negatives.append(f"reversal_proximity={bb_state}")

    return _v26_clamp_score(score), positives, negatives


def build_execution_legs_v26_5(decision):
    bias = str(decision.get("action", decision.get("bias", "NEUTRAL"))).upper()
    execution_state = str(decision.get("execution_state", "NO_TRADE")).upper()
    location_score = safe_int(decision.get("entry_location_score", 0), 0)
    continuation_quality = safe_int(decision.get("continuation_quality", 0), 0)
    score_gap = safe_int(decision.get("score_gap", 0), 0)
    in_profit_only = True

    legs = [
        {
            "leg": "A",
            "name": "Scout Entry",
            "purpose": "directional confirmation and scalp profit bank",
            "enabled": bias in ("BUY", "SELL") and location_score >= V26_5_ENTRY_LOCATION_MIN_EXECUTE,
            "scale_rule": "initial entry only; never average a loser",
            "profit_role": "SCALP_PROFIT",
        },
        {
            "leg": "B",
            "name": "Confirmation Entry",
            "purpose": "pullback continuation participation after Leg A is positive",
            "enabled": bias in ("BUY", "SELL") and location_score >= V26_5_ENTRY_LOCATION_MIN_CONFIRMATION and continuation_quality >= PULLBACK_CONTINUATION_MIN_QUALITY,
            "scale_rule": "only add if existing idea P/L is positive; never average a loser",
            "profit_role": "TREND_CONTINUATION",
        },
        {
            "leg": "C",
            "name": "Continuation Entry",
            "purpose": "trend expansion runner after confirmed winner state",
            "enabled": bias in ("BUY", "SELL") and location_score >= V26_5_ENTRY_LOCATION_MIN_CONTINUATION and continuation_quality >= PULLBACK_ALLOW_RUNNER_QUALITY and score_gap >= 4,
            "scale_rule": "only scale into winners; no martingale; no hedge",
            "profit_role": "RUNNER",
        },
    ]

    active_leg = "NONE"
    if execution_state in ("EXECUTE_AGGRESSIVE", "EXECUTE_NORMAL", "EXECUTE_CAUTIOUS"):
        if legs[2]["enabled"]:
            active_leg = "C"
        elif legs[1]["enabled"]:
            active_leg = "B"
        elif legs[0]["enabled"]:
            active_leg = "A"

    return legs, active_leg, in_profit_only


def apply_execution_quality_core_v26_5(decision):
    if not isinstance(decision, dict):
        return decision

    location_score, positives, negatives = compute_entry_location_score_v26_5(decision)
    decision["entry_location_score"] = location_score
    decision["entry_location_score_v26_5"] = location_score
    decision["entry_location_grade"] = (
        "EXCELLENT" if location_score >= 80 else
        "GOOD" if location_score >= V26_5_ENTRY_LOCATION_MIN_CONTINUATION else
        "ACCEPTABLE" if location_score >= V26_5_ENTRY_LOCATION_MIN_EXECUTE else
        "POOR"
    )
    decision["entry_location_positive_factors"] = positives
    decision["entry_location_negative_factors"] = negatives
    decision["entry_location_score_reason"] = f"positive={positives}; negative={negatives}"

    legs, active_leg, in_profit_only = build_execution_legs_v26_5(decision)
    decision["directional_idea_id"] = f"{SYMBOL}:{decision.get('market_mode', 'UNKNOWN')}:{decision.get('bb_state', 'UNKNOWN')}:{decision.get('bias', 'NEUTRAL')}"
    decision["execution_legs"] = legs
    decision["active_execution_leg"] = active_leg
    decision["position_construction"] = "ONE_DIRECTIONAL_IDEA_MULTI_LEG"
    decision["scale_policy"] = "SCALE_INTO_WINNERS_ONLY"
    decision["scale_into_winners_only"] = in_profit_only
    decision["martingale_allowed"] = False
    decision["averaging_losers_allowed"] = False
    decision["hedge_architecture_allowed"] = False
    decision["profit_lock_ladder"] = V26_5_PROFIT_LOCK_LADDER_POINTS
    decision["profit_extraction_structure"] = {
        "leg_a": "SCALP_PROFIT",
        "leg_b": "TREND_CONTINUATION",
        "leg_c": "RUNNER",
        "break_even_policy": "defer early BE; use profit lock ladder after expansion",
    }

    bias = str(decision.get("action", decision.get("bias", decision.get("intended_action", "NEUTRAL")))).upper()
    poor_directional_location = location_score < V26_5_ENTRY_LOCATION_MIN_EXECUTE and bias in ("BUY", "SELL")
    hard_block_active = str(decision.get("hard_block", "")).upper() in ("TRUE", "1", "YES")
    if poor_directional_location and not hard_block_active:
        veto_reason = f"ENTRY_LOCATION_SCORE {location_score} < {V26_5_ENTRY_LOCATION_MIN_EXECUTE}"
        softened = _soften_legacy_veto_if_ai_authority_valid(
            decision, veto_reason, "V26_5_ENTRY_LOCATION_WAIT", V26_5_ENTRY_LOCATION_WEAK_PENALTY
        )
        if softened is not None:
            softened["entry_quality_block"] = False
            softened["entry_quality_block_reason"] = veto_reason
            softened["entry_location_wait_diagnostic_only"] = True
            softened["wait_state"] = ""
            softened["wait_reason"] = ""
            return softened
        decision["decision"] = "NO_TRADE"
        decision["entry_allowed"] = False
        decision["execution_state"] = "WAIT"
        decision["wait_state"] = "WAIT_ENTRY_LOCATION"
        decision["wait_reason"] = "entry location not worth entering yet"
        decision["next_trigger"] = "fresh breakout reset / healthy pullback / continuation quality improves"
        decision["intended_action"] = bias
        decision["manual_action"] = f"{bias}_BIAS_WAIT_LOCATION"
        decision["management"] = "NO_TRADE"
        decision["mgmt"] = "NO_TRADE"
        decision["entry_quality_block"] = True
        decision["entry_quality_block_reason"] = veto_reason
        if "V26_5_ENTRY_LOCATION_WAIT" not in str(decision.get("reason", "")):
            decision["reason"] = (str(decision.get("reason", "")) + " | V26_5_ENTRY_LOCATION_WAIT").strip()
    else:
        decision["entry_quality_block"] = False
        decision["entry_quality_block_reason"] = ""

    return decision


def _v26_6_5_directional_alignment(value, bias, bullish_values, bearish_values):
    state = str(value or "UNKNOWN").upper()
    if state in bullish_values:
        return 1 if bias == "BUY" else -1 if bias == "SELL" else 0
    if state in bearish_values:
        return 1 if bias == "SELL" else -1 if bias == "BUY" else 0
    return 0


def compute_execution_timing_layer_v26_6_5(decision):
    """
    V26.6.5 Execution Timing Layer.

    Directional intelligence is preserved. This layer only decides whether the
    short-term execution window is open for the already-selected BUY/SELL bias.
    It intentionally reuses existing candle, structure, BB, RSI, MACD, pullback,
    and continuation telemetry rather than adding indicators or classifier
    branches.
    """
    bias = str(decision.get("action", decision.get("bias", decision.get("intended_action", "NEUTRAL")))).upper()
    bb_state = str(decision.get("confirmed_bb_state", decision.get("bb_state", decision.get("bb", "NORMAL")))).upper()
    candle_trend = str(decision.get("candle_trend", "UNKNOWN")).upper()
    structure_trend = str(decision.get("structure_trend", "UNKNOWN")).upper()
    momentum_shape = str(decision.get("momentum_shape", "UNKNOWN")).upper()
    pullback_state = str(decision.get("pullback_state", "UNKNOWN")).upper()
    entry_timing = str(decision.get("entry_timing", "UNKNOWN")).upper()
    timing_state = str(decision.get("execution_timing_state", "")).upper()
    rsi = safe_float(decision.get("rsi", 50.0), 50.0)
    macd_hist = safe_float(decision.get("macd_hist", 0.0), 0.0)
    pullback_quality = safe_int(decision.get("pullback_quality", 0), 0)
    continuation_quality = safe_int(decision.get("continuation_quality", 0), 0)
    candle_count = safe_int(decision.get("candle_count", 0), 0)

    score = 50
    factors = []
    counter_factors = []
    recovery_factors = []

    candle_align = _v26_6_5_directional_alignment(candle_trend, bias, {"UP"}, {"DOWN"})
    structure_align = _v26_6_5_directional_alignment(structure_trend, bias, {"HH_HL"}, {"LH_LL"})
    momentum_align = _v26_6_5_directional_alignment(momentum_shape, bias, {"EXPANDING_BULL"}, {"EXPANDING_BEAR"})
    bb_align = _v26_6_5_directional_alignment(bb_state, bias, {"WALK_UP"}, {"WALK_DOWN"})

    for name, align, weight in (
        ("candle_trend", candle_align, 14),
        ("structure", structure_align, 16),
        ("momentum_shape", momentum_align, 14),
        ("bb_walk", bb_align, 16),
    ):
        if align > 0:
            score += weight
            recovery_factors.append(f"{name}_with_bias")
        elif align < 0:
            score -= weight
            counter_factors.append(f"{name}_against_bias")

    if bias == "BUY":
        if macd_hist <= -V26_6_5_STRONG_MACD_COUNTER:
            score -= 18; counter_factors.append(f"negative_macd_expansion={macd_hist:.2f}")
        elif macd_hist > -V26_6_5_STRONG_MACD_COUNTER:
            score += 6; recovery_factors.append(f"macd_improving={macd_hist:.2f}")
        if rsi <= V26_6_5_RSI_STRONG_COUNTER_BUY:
            score -= 10; counter_factors.append(f"rsi_still_selling={rsi:.2f}")
        elif rsi >= V26_6_5_RSI_BUY_RECOVERY:
            score += 8; recovery_factors.append(f"rsi_recovering={rsi:.2f}")
    elif bias == "SELL":
        if macd_hist >= V26_6_5_STRONG_MACD_COUNTER:
            score -= 18; counter_factors.append(f"positive_macd_expansion={macd_hist:.2f}")
        elif macd_hist < V26_6_5_STRONG_MACD_COUNTER:
            score += 6; recovery_factors.append(f"macd_improving={macd_hist:.2f}")
        if rsi >= V26_6_5_RSI_STRONG_COUNTER_SELL:
            score -= 10; counter_factors.append(f"rsi_still_buying={rsi:.2f}")
        elif rsi <= V26_6_5_RSI_SELL_RECOVERY:
            score += 8; recovery_factors.append(f"rsi_recovering={rsi:.2f}")

    if pullback_quality >= PULLBACK_CONTINUATION_MIN_QUALITY:
        score += 10
        recovery_factors.append(f"pullback_mature={pullback_quality}")
    elif pullback_state in ("WAIT_PULLBACK_AFTER_SPIKE", "WAIT_PULLBACK"):
        score -= 10
        counter_factors.append(f"pullback_not_mature={pullback_state}")

    if continuation_quality >= PULLBACK_CONTINUATION_MIN_QUALITY or str(decision.get("continuation_return", False)).upper() in ("TRUE", "1", "YES"):
        score += 12
        recovery_factors.append(f"continuation_confirmed={continuation_quality}")

    if timing_state in ("HEALTHY_CONTINUATION", "EARLY_CONTINUATION") or entry_timing in ("PULLBACK_REENTRY_AFTER_SPIKE",):
        score += 10
        recovery_factors.append(f"timing={timing_state or entry_timing}")
    elif timing_state == "LATE_CONTINUATION":
        score -= 8
        counter_factors.append("late_continuation")

    score = _v26_clamp_score(score)
    active_countertrend = bias in ("BUY", "SELL") and score <= V26_6_5_ACTIVE_COUNTERTREND_SCORE and len(counter_factors) >= 2 and candle_count >= 3
    execution_window_open = bias in ("BUY", "SELL") and not active_countertrend and score >= V26_6_5_ENTRY_WINDOW_MIN_SCORE

    if active_countertrend:
        phase = "PULLBACK"
    elif execution_window_open and recovery_factors:
        phase = "RESUMPTION"
    elif score >= 75 and not counter_factors:
        phase = "TREND_EXPANSION"
    elif timing_state == "LATE_CONTINUATION" or safe_int(decision.get("late_entry_score", 0), 0) >= 70:
        phase = "EXHAUSTION"
    else:
        phase = "PULLBACK" if counter_factors else "RESUMPTION"

    factors.extend(recovery_factors)
    factors.extend(counter_factors)
    return {
        "execution_window_state": "OPEN" if execution_window_open else "WAIT_ENTRY_WINDOW",
        "entry_window_score": score,
        "short_term_countertrend": bool(active_countertrend),
        "pullback_phase": phase == "PULLBACK",
        "trend_phase": phase,
        "execution_delay_reason": "; ".join(counter_factors) if not execution_window_open else "",
        "execution_window_open": bool(execution_window_open),
        "bias_preserved": bias in ("BUY", "SELL"),
        "entry_window_factors": factors,
        "entry_window_recovery_factors": recovery_factors,
        "entry_window_counter_factors": counter_factors,
    }



def _cooldown_gate_bypass_reject(decision, reason, supporting_vetoes=None):
    decision["COOLDOWN_GATE_BYPASS_CHECK"] = "REJECTED"
    decision["COOLDOWN_GATE_BYPASS_REJECTED"] = True
    decision["COOLDOWN_GATE_BYPASS_REJECTED_REASON"] = reason
    decision["COOLDOWN_GATE_BYPASS_APPROVED"] = False
    if supporting_vetoes:
        decision["cooldown_gate_bypass_supporting_vetoes"] = list(supporting_vetoes)
    return False


def _cooldown_gate_wait_entry_window_bypass_allowed(decision, bias, action, score_gap, mode, macd_hist):
    """Narrow emergency bypass: aligned TREND gap>=2 may create a cautious candidate instead of terminal WAIT_ENTRY_WINDOW."""
    decision["COOLDOWN_GATE_BYPASS_CHECK"] = "CHECKING"

    if action not in ("BUY", "SELL") or bias != action:
        return _cooldown_gate_bypass_reject(decision, "bias/action not aligned", ["BIAS_ACTION_MISMATCH"])
    if mode != "TREND":
        return _cooldown_gate_bypass_reject(decision, f"mode={mode} is not TREND", ["NOT_TREND"])
    if score_gap < 2:
        return _cooldown_gate_bypass_reject(decision, f"score_gap={score_gap} < 2", ["INSUFFICIENT_SCORE_GAP"])

    hard_block, hard_reason = _v26_has_hard_block(decision)
    if hard_block:
        return _cooldown_gate_bypass_reject(decision, f"hard safety block: {hard_reason}", [hard_reason])
    if not bool(decision.get("market_state_fresh", True)):
        return _cooldown_gate_bypass_reject(decision, "market_state not fresh", ["MARKET_STATE_STALE"])

    trend_exhaustion_score = safe_int(decision.get("trend_exhaustion_score", 0), 0)
    exhaustion_score = safe_int(decision.get("exhaustion_score", decision.get("exhaustion_risk", 0)), 0)
    late_score = safe_int(decision.get("late_entry_score", 0), 0)
    if trend_exhaustion_score >= TREND_EXHAUSTION_BLOCK_LEVEL or exhaustion_score >= EXHAUSTION_BLOCK_SCORE or late_score >= LATE_ENTRY_BLOCK_SCORE:
        return _cooldown_gate_bypass_reject(decision, "severe exhaustion or late-entry risk", ["SEVERE_EXHAUSTION"])

    if (action == "BUY" and macd_hist <= -EMERGENCY_GAP2_STRONG_OPPOSITE_MACD) or (action == "SELL" and macd_hist >= EMERGENCY_GAP2_STRONG_OPPOSITE_MACD):
        return _cooldown_gate_bypass_reject(decision, "MACD strongly opposite beyond emergency threshold", ["STRONG_OPPOSITE_MACD"])

    open_positions = safe_int(decision.get("open_positions", decision.get("current_open_positions", 0)), 0)
    max_open_positions = safe_int(decision.get("max_open_positions", 1), 1)
    if bool(decision.get("open_position_violation", False)) or open_positions >= max_open_positions:
        return _cooldown_gate_bypass_reject(decision, "open-position violation", ["OPEN_POSITION_LIMIT"])

    decision["COOLDOWN_GATE_BYPASS_CHECK"] = "APPROVED"
    decision["COOLDOWN_GATE_BYPASS_APPROVED"] = True
    decision["COOLDOWN_GATE_BYPASS_REJECTED"] = False
    return True


def _apply_cooldown_gate_wait_entry_window_bypass(decision, bias):
    decision["decision"] = "TRADE"
    decision["allowed"] = True
    decision["entry_allowed"] = True
    decision["execution_state"] = "EXECUTE_CAUTIOUS"
    decision["execution_mode"] = "CAUTIOUS"
    decision["decision_output_state"] = "TRADE"
    decision["participation_type"] = "CAUTIOUS"
    decision["participation_size_factor"] = EMERGENCY_GAP2_PARTICIPATION_SIZE_FACTOR
    decision["risk_fraction"] = EMERGENCY_GAP2_PARTICIPATION_SIZE_FACTOR
    decision["position_size_multiplier"] = EMERGENCY_GAP2_PARTICIPATION_SIZE_FACTOR
    decision["runner_enabled"] = False
    decision["pyramid_enabled"] = False
    decision["continuation_add_enabled"] = False
    decision["no_pyramid"] = True
    decision["runner_default"] = "DISABLED_FOR_COOLDOWN_GATE_BYPASS"
    decision["wait_state"] = "BYPASSED_WAIT_ENTRY_WINDOW"
    decision["entry_window_validation"] = "WAIT_ENTRY_WINDOW_CONVERTED_TO_EXECUTE_CAUTIOUS"
    decision["WAIT_ENTRY_WINDOW_CONVERTED_TO_EXECUTE_CAUTIOUS"] = True
    decision["final_veto_owner"] = "NONE"
    decision["effective_veto_code"] = "NONE"
    decision["management"] = "SCALP_TP"
    decision["mgmt"] = "SCALP_TP"
    decision["bias"] = bias
    decision["action"] = bias
    decision["reason"] = (str(decision.get("reason", "")).strip() + " | WAIT_ENTRY_WINDOW_CONVERTED_TO_EXECUTE_CAUTIOUS").strip()
    return decision

def apply_execution_timing_layer_v26_6_5(decision):
    if not isinstance(decision, dict):
        return decision

    bias = str(decision.get("action", decision.get("bias", decision.get("intended_action", "NEUTRAL")))).upper()
    if bias not in ("BUY", "SELL"):
        decision.setdefault("execution_window_state", "NO_DIRECTION")
        decision.setdefault("entry_window_score", 0)
        decision.setdefault("short_term_countertrend", False)
        decision.setdefault("pullback_phase", False)
        decision.setdefault("trend_phase", "UNKNOWN")
        decision.setdefault("execution_delay_reason", "no BUY/SELL bias")
        decision.setdefault("execution_window_open", False)
        decision.setdefault("bias_preserved", False)
        return decision

    fields = compute_execution_timing_layer_v26_6_5(decision)
    decision.update(fields)

    hard_block, _hard_reason = _v26_has_hard_block(decision)
    is_trade = str(decision.get("decision", "")).upper() == "TRADE"
    if is_trade and not hard_block and not fields["execution_window_open"]:
        action = str(decision.get("action", decision.get("intended_action", bias))).upper()
        mode = str(decision.get("market_mode", decision.get("mode", "TRANSITION"))).upper()
        score_gap = safe_int(decision.get("score_gap", 0), 0)
        macd_hist = safe_float(decision.get("macd_hist", 0.0), 0.0)
        if _cooldown_gate_wait_entry_window_bypass_allowed(decision, bias, action, score_gap, mode, macd_hist):
            return _apply_cooldown_gate_wait_entry_window_bypass(decision, bias)
        decision["decision"] = "NO_TRADE"
        decision["entry_allowed"] = False
        decision["allowed"] = False
        decision["execution_state"] = "WAIT"
        decision["wait_state"] = "WAIT_ENTRY_WINDOW"
        decision["wait_reason"] = "short-term execution window not open; directional bias preserved"
        decision["next_trigger"] = "pullback losing momentum / higher-low or lower-high break / MACD-RSI recovery / BB walk ending / continuation candle"
        decision["intended_action"] = bias
        decision["manual_action"] = f"{bias}_BIAS_WAIT_ENTRY_WINDOW"
        decision["management"] = "NO_TRADE"
        decision["mgmt"] = "NO_TRADE"
        decision["bias"] = bias
        decision["action"] = bias
        decision["bias_preserved"] = True
        decision["entry_window_validation"] = "WAIT_ENTRY_WINDOW"
        decision["reason"] = (str(decision.get("reason", "")) + " | V26_6_5_WAIT_ENTRY_WINDOW").strip()
    elif fields["execution_window_open"]:
        decision["entry_window_validation"] = "OPEN"

    return decision


def apply_v26_execution_confidence_engine(decision):
    """
    V26 Execution Confidence Engine.

    Converts most hard vetoes into score penalties.
    Separates WAIT from NO_TRADE.
    Reduces M3 veto authority.
    Preserves directional bias when valid.
    """
    if not V26_EXECUTION_CONFIDENCE_ENABLED or not isinstance(decision, dict):
        return decision

    hard_block, hard_reason = _v26_has_hard_block(decision)

    bias, buy, sell, gap = _v26_score_from_direction(decision)
    mode = _v26_safe_upper(decision.get("market_mode", decision.get("mode", "TRANSITION")), "TRANSITION")
    bb = _v26_safe_upper(decision.get("confirmed_bb_state", decision.get("bb_state", decision.get("bb", "NORMAL"))), "NORMAL")
    timing = _v26_safe_upper(decision.get("execution_timing_state", ""), "")
    location = _v26_safe_upper(decision.get("entry_location_state", ""), "")
    style = _v26_safe_upper(decision.get("market_style", ""), "")
    exhaustion = _v26_safe_upper(decision.get("exhaustion_state", ""), "")
    pullback_state = _v26_safe_upper(decision.get("pullback_state", ""), "")
    entry_timing = _v26_safe_upper(decision.get("entry_timing", ""), "")

    late_score = safe_int(decision.get("late_entry_score", 0), 0)
    exhaustion_score = safe_int(decision.get("exhaustion_score", 0), 0)
    entry_location_score = safe_int(decision.get("entry_location_score", 50), 50)
    rr = safe_float(decision.get("estimated_reward_risk", decision.get("rr_quality", 0)), 0)
    mkt_age = safe_int(decision.get("market_state_age_sec", 999), 999)
    soft_state = _v26_safe_upper(decision.get("soft_lock_state", ""), "")
    transition_decay_count = safe_int(decision.get("transition_decay_count", 0), 0)
    transition_decay_required = max(1, safe_int(decision.get("transition_decay_required", TRANSITION_DECAY_REQUIRED_COUNT), TRANSITION_DECAY_REQUIRED_COUNT))

    dominance_bias, dominance_reason = detect_directional_dominance(decision, decision)
    dominance_active = dominance_bias in ("BUY", "SELL")

    score = 0
    reasons = []

    # Infrastructure safety first.
    if hard_block:
        decision["execution_state"] = "NO_TRADE"
        decision["execution_confidence_score"] = 0
        decision["hard_block"] = True
        decision["hard_block_reason"] = hard_reason
        decision["wait_reason"] = ""
        decision["bias_preserved"] = bias in ("BUY", "SELL")
        if bias in ("BUY", "SELL"):
            decision["bias"] = bias
            decision["action"] = bias
        decision["decision"] = "NO_TRADE"
        decision["entry_allowed"] = False
        decision["management"] = "NO_TRADE"
        decision["mgmt"] = "NO_TRADE"
        decision["execution_confidence_reason"] = f"HARD_BLOCK | {hard_reason}"
        reset_wait_valid_lifecycle("wait reset: hard safety block")
        return decision

    decision["hard_block"] = False
    decision["hard_block_reason"] = ""

    # HTF authority proxy: current mode + strong score gap.
    # If Writer later sends explicit h1/h4 fields, map them here.
    if mode == "TREND":
        score += 35
        reasons.append("mode TREND +35")
    elif mode == "TRANSITION":
        score += 18
        reasons.append("mode TRANSITION +18")
    elif mode == "RANGE":
        score += 12
        reasons.append("mode RANGE +12")
    elif mode == "SPIKE":
        score += 12
        reasons.append("mode SPIKE +12")

    # Directional score gap.
    if bias in ("BUY", "SELL"):
        if gap >= 5:
            score += 28
            reasons.append(f"strong score gap {gap} +28")
        elif gap >= 3:
            score += 20
            reasons.append(f"good score gap {gap} +20")
        elif gap >= 2:
            score += 12
            reasons.append(f"acceptable score gap {gap} +12")
        else:
            score += 4
            reasons.append(f"weak score gap {gap} +4")
    else:
        score -= 20
        reasons.append("no directional bias -20")

    # M15/setup proxy via BB state and location.
    if bb in ("WALK_UP", "WALK_DOWN"):
        score += 12
        reasons.append(f"BB walk context {bb} +12")
    elif bb == "NORMAL":
        score += 5
        reasons.append("BB normal context +5")
    elif bb in ("REVERSAL_UP", "REVERSAL_DOWN"):
        score -= 5
        reasons.append(f"BB reversal penalty {bb} -5")

    # Entry location / RR.
    if entry_location_score >= 65:
        score += 15
        reasons.append(f"good location {entry_location_score} +15")
    elif entry_location_score >= 45:
        score += 5
        reasons.append(f"acceptable location {entry_location_score} +5")
    else:
        score -= 15
        reasons.append(f"weak location {entry_location_score} -15")

    if rr >= 1.5:
        score += 15
        reasons.append(f"good RR {rr:.2f} +15")
    elif rr >= 1.0:
        score += 8
        reasons.append(f"acceptable RR {rr:.2f} +8")
    elif rr > 0:
        score -= 12
        reasons.append(f"weak RR {rr:.2f} -12")

    if entry_location_score >= 80:
        score += V26_5_ENTRY_LOCATION_EXCELLENT_BONUS
        reasons.append(f"V26.5 excellent entry location {entry_location_score} +{V26_5_ENTRY_LOCATION_EXCELLENT_BONUS}")
    elif entry_location_score >= V26_5_ENTRY_LOCATION_MIN_CONTINUATION:
        score += V26_5_ENTRY_LOCATION_GOOD_BONUS
        reasons.append(f"V26.5 high-quality entry location {entry_location_score} +{V26_5_ENTRY_LOCATION_GOOD_BONUS}")
    elif entry_location_score < V26_5_ENTRY_LOCATION_MIN_EXECUTE:
        score -= V26_5_ENTRY_LOCATION_WEAK_PENALTY
        reasons.append(f"V26.5 poor entry location {entry_location_score} -{V26_5_ENTRY_LOCATION_WEAK_PENALTY}")

    # M3 timing refinement only, never full veto except severe risk handled above.
    m3_penalty = 0
    if timing == "LATE_CONTINUATION" or late_score >= 70:
        m3_penalty -= 12
        reasons.append(f"M3 late penalty late={late_score} -12")
    elif timing in ("HEALTHY_CONTINUATION", "EARLY_CONTINUATION"):
        score += 10
        reasons.append(f"M3 timing {timing} +10")
    elif entry_timing == "WAIT_PULLBACK" or pullback_state == "WAIT_PULLBACK_AFTER_SPIKE":
        m3_penalty -= 8
        reasons.append("WAIT_PULLBACK penalty -8")

    if m3_penalty < V26_M3_MAX_NEGATIVE_PENALTY:
        m3_penalty = V26_M3_MAX_NEGATIVE_PENALTY
    score += m3_penalty

    # Soft-lock governance should be a confidence modifier, not an execution killer.
    if soft_state == "TRANSITION_WAIT":
        score -= 18
        reasons.append("transition wait governance penalty -18")
    elif soft_state == "TREND_LOCK":
        score += 3
        reasons.append("trend lock continuity +3")

    if transition_decay_count > 0:
        decay_penalty = min(12, int((transition_decay_count / transition_decay_required) * 12))
        score -= decay_penalty
        reasons.append(f"persistent weakening decay {transition_decay_count}/{transition_decay_required} -{decay_penalty}")

    # Exhaustion as penalty, not full veto unless safety hard block says so.
    if exhaustion == "HIGH" or exhaustion_score >= 75:
        score -= 25
        reasons.append(f"high exhaustion {exhaustion_score} -25")
    elif exhaustion == "MEDIUM" or exhaustion_score >= 55:
        score -= 15
        reasons.append(f"medium exhaustion {exhaustion_score} -15")
    elif exhaustion_score > 0:
        score -= 5
        reasons.append(f"minor exhaustion {exhaustion_score} -5")

    # Freshness bonus within temp live tolerance.
    if mkt_age <= 5:
        score += 5
        reasons.append(f"fresh market age={mkt_age} +5")
    elif mkt_age <= TEMP_MARKET_STATE_STALE_LIMIT_SEC:
        reasons.append(f"market age acceptable={mkt_age}")

    score = _v26_clamp_score(score)
    if dominance_active:
        if bias not in ("BUY", "SELL"):
            bias = dominance_bias
        score = max(score, V26_EXECUTE_CAUTIOUS_SCORE)
        reasons.append(f"{dominance_reason} -> dominance floor EXECUTE_CAUTIOUS")

    if entry_location_score < V26_5_ENTRY_LOCATION_MIN_EXECUTE:
        score = min(score, V26_5_ENTRY_LOCATION_POOR_CAP)
        reasons.append(f"V26.5 location cap: score capped at WAIT because ENTRY_LOCATION_SCORE={entry_location_score}")

    # State selection.
    if score >= V26_EXECUTE_AGGRESSIVE_SCORE:
        execution_state = "EXECUTE_AGGRESSIVE"
    elif score >= V26_EXECUTE_NORMAL_SCORE:
        execution_state = "EXECUTE_NORMAL"
    elif score >= V26_EXECUTE_CAUTIOUS_SCORE:
        execution_state = "EXECUTE_CAUTIOUS"
    elif score >= V26_WAIT_SCORE:
        execution_state = "WAIT"
    else:
        execution_state = "NO_TRADE"

    decision["execution_state"] = execution_state
    decision["execution_confidence_score"] = score
    decision["execution_confidence_reason"] = "; ".join(reasons)
    decision["htf_authority"] = bias if mode == "TREND" and bias in ("BUY", "SELL") else "MIXED"
    decision["m15_setup_quality"] = _v26_clamp_score(entry_location_score + (10 if bb in ("WALK_UP", "WALK_DOWN") else 0))
    decision["m3_timing_quality"] = _v26_clamp_score(70 - late_score + (10 if timing in ("HEALTHY_CONTINUATION", "EARLY_CONTINUATION") else 0))
    decision["bias_preserved"] = bias in ("BUY", "SELL")

    if bias in ("BUY", "SELL"):
        decision["bias"] = bias
        decision["action"] = bias

    # WAIT != NO_TRADE.
    if execution_state in ("EXECUTE_AGGRESSIVE", "EXECUTE_NORMAL", "EXECUTE_CAUTIOUS") and bias in ("BUY", "SELL"):
        decision["decision"] = "TRADE"
        decision["entry_allowed"] = True
        if _management_prefers_runner(bias, mode, bb, gap):
            decision["management"] = "HOLD_TRAIL"
            decision["mgmt"] = "HOLD_TRAIL"
            decision["market_style"] = "INTRADAY_SWING"
            decision["management_alignment"] = "TREND_WALK_PREFERS_HOLD_TRAIL"
        else:
            decision["management"] = decision.get("management", "SCALP_TP") if str(decision.get("management", "")).upper() not in ("", "NO_TRADE") else "SCALP_TP"
            decision["mgmt"] = decision["management"]
        if execution_state == "EXECUTE_CAUTIOUS" and V26_FORCE_SCALP_FOR_CAUTIOUS and str(decision.get("management", "")).upper() == "SCALP_TP":
            decision["market_style"] = "SCALP"
        decision["wait_reason"] = ""
        decision["next_trigger"] = ""
    elif execution_state == "WAIT":
        decision["decision"] = "NO_TRADE"
        decision["entry_allowed"] = False
        decision["management"] = "NO_TRADE"
        decision["mgmt"] = "NO_TRADE"
        decision["wait_state"] = "WAIT_VALID"
        decision["wait_reason"] = "timing not ideal yet; bias preserved"
        decision["next_trigger"] = "pullback reset / M3 timing improves / confidence >= execute threshold"
        decision["intended_action"] = bias if bias in ("BUY", "SELL") else decision.get("intended_action", "WAIT")
        decision["manual_action"] = f"{bias}_BIAS_WAIT_RECOVERY" if bias in ("BUY", "SELL") else "WAIT"
        decision["wait_recovery_lifecycle"] = "ACTIVE"
        decision["wait_directional_memory"] = bias if bias in ("BUY", "SELL") else "NONE"
        decision["reason"] = (str(decision.get("reason", "")) + " | V26_WAIT_NOT_NO_TRADE").strip()
    else:
        soft_directional_context = (
            bias in ("BUY", "SELL")
            and mode in ("SPIKE", "TREND", "TRANSITION")
            and mkt_age <= TEMP_MARKET_STATE_STALE_LIMIT_SEC
            and not hard_block
        )

        if soft_directional_context:
            decision["execution_state"] = "WAIT"
            decision["decision"] = "NO_TRADE"
            decision["entry_allowed"] = False
            decision["management"] = "NO_TRADE"
            decision["mgmt"] = "NO_TRADE"
            decision["wait_state"] = "WAIT_VALID"
            decision["wait_reason"] = "low confidence/cooldown governance; directional authority preserved"
            decision["next_trigger"] = "confidence recovery / cooldown release / continuation confirmation"
            decision["intended_action"] = bias
            decision["manual_action"] = f"{bias}_BIAS_WAIT_RECOVERY"
            decision["wait_recovery_lifecycle"] = "ACTIVE"
            decision["wait_directional_memory"] = bias
            decision["suppression_active"] = True
            decision["reason"] = (str(decision.get("reason", "")) + " | V26_LOW_CONFIDENCE_WAIT_VALID_DIRECTION_PRESERVED").strip()
        else:
            decision["decision"] = "NO_TRADE"
            decision["entry_allowed"] = False
            decision["management"] = "NO_TRADE"
            decision["mgmt"] = "NO_TRADE"
            decision["wait_reason"] = ""
            decision["next_trigger"] = ""
            if dominance_active and bias in ("BUY", "SELL"):
                decision["execution_state"] = "WAIT"
                decision["wait_reason"] = "dominance active but confidence not ready"
                decision["next_trigger"] = "confidence recovery with directional dominance preserved"
                decision["intended_action"] = bias
                decision["manual_action"] = f"{bias}_BIAS_WAIT_RECOVERY"
                decision["wait_recovery_lifecycle"] = "ACTIVE"
                decision["wait_directional_memory"] = bias
                decision["reason"] = (str(decision.get("reason", "")) + " | V26_DOMINANCE_LOW_CONFIDENCE_PENALTY_WAIT").strip()
            else:
                decision["reason"] = (str(decision.get("reason", "")) + " | V26_LOW_CONFIDENCE_NO_TRADE").strip()

    if decision.get("execution_state") == "WAIT" and bias in ("BUY", "SELL"):
        decision = apply_wait_valid_timeout_recovery(decision, bias, mode, bb, hard_block=False)
    else:
        reset_wait_valid_lifecycle("wait reset: executing or no wait state")

    decision["directional_dominance_active"] = bool(dominance_active)
    decision["directional_dominance_bias"] = dominance_bias if dominance_active else "NONE"
    decision["directional_dominance_reason"] = dominance_reason if dominance_active else ""

    return decision

def apply_spike_pullback_reentry_v25_6(decision, data):
    if not SPIKE_PULLBACK_REENTRY_ENABLED or not isinstance(decision, dict):
        return decision

    mode = str(decision.get("market_mode", decision.get("mode", "TRANSITION"))).upper()
    bb = str(decision.get("confirmed_bb_state", decision.get("bb_state", decision.get("bb", "NORMAL")))).upper()
    bias, buy, sell, gap = _v25_6_bias_from_scores(decision)
    exhaustion_score = safe_int(decision.get("exhaustion_score", 0), 0)
    late_entry_score = safe_int(decision.get("late_entry_score", 0), 0)
    timing = str(decision.get("execution_timing_state", "")).upper()

    if bias in ("BUY", "SELL"):
        decision["bias"] = bias
        decision["action"] = bias

    trend_valid = mode in ("TREND", "SPIKE", "TRANSITION") and bias in ("BUY", "SELL") and gap >= SPIKE_MIN_SCORE_GAP
    is_spike_overextended = (
        mode == "SPIKE"
        or timing == "LATE_CONTINUATION"
        or late_entry_score >= 70
        or exhaustion_score >= SPIKE_REENTRY_MAX_EXHAUSTION_SCORE
    )

    zone, dist, threshold = _v25_6_reentry_zone_distance(data, decision)
    near_zone = zone != "NONE" and dist <= threshold

    if is_spike_overextended and trend_valid and not near_zone:
        spike_pullback_state["waiting"] = True
        spike_pullback_state["bias"] = bias
        spike_pullback_state["started_ts"] = int(time.time())
        reason = f"SPIKE_WAIT_PULLBACK | bias={bias} gap={gap} mode={mode} bb={bb} late={late_entry_score} exhaustion={exhaustion_score}"
        spike_pullback_state["reason"] = reason

        decision["decision"] = "NO_TRADE"
        decision["bias"] = bias
        decision["action"] = bias
        decision["entry_allowed"] = False
        decision["management"] = "NO_TRADE"
        decision["mgmt"] = "NO_TRADE"
        decision["entry_timing"] = "WAIT_PULLBACK"
        decision["pullback_state"] = "WAIT_PULLBACK_AFTER_SPIKE"
        decision["spike_pullback_wait"] = True
        decision["spike_reentry_zone"] = zone
        decision["spike_reentry_distance"] = round(dist, 3)
        decision["final_gate_block_reason_class"] = "WAIT_PULLBACK"
        decision["final_gate_reason"] = reason
        decision["reason"] = (str(decision.get("reason", "")) + " | " + reason).strip()
        return decision

    if spike_pullback_state.get("waiting", False):
        same_bias = bias == str(spike_pullback_state.get("bias", "NEUTRAL")).upper()
        risk_ok = exhaustion_score < SPIKE_REENTRY_MAX_EXHAUSTION_SCORE and late_entry_score < 80
        if trend_valid and same_bias and near_zone and risk_ok:
            spike_pullback_state["waiting"] = False
            reason = f"SPIKE_PULLBACK_REENTRY_ALLOW | bias={bias} zone={zone} dist={dist:.2f} gap={gap}"
            decision["decision"] = "TRADE"
            decision["bias"] = bias
            decision["action"] = bias
            decision["entry_allowed"] = True
            decision["management"] = "SCALP_TP"
            decision["mgmt"] = "SCALP_TP"
            decision["entry_timing"] = "PULLBACK_REENTRY_AFTER_SPIKE"
            decision["pullback_state"] = "SPIKE_PULLBACK_REENTRY"
            decision["spike_pullback_wait"] = False
            decision["spike_reentry_zone"] = zone
            decision["spike_reentry_distance"] = round(dist, 3)
            decision["final_gate_override"] = True
            decision["final_gate_reason"] = reason
            decision["reason"] = (str(decision.get("reason", "")) + " | " + reason).strip()
            return decision

    decision.setdefault("spike_pullback_wait", bool(spike_pullback_state.get("waiting", False)))
    decision.setdefault("spike_reentry_zone", zone)
    decision.setdefault("spike_reentry_distance", round(dist, 3))
    return decision

def apply_structure_aware_hold_intelligence_v25_5(decision):
    """
    V25.5 Structure-Aware Hold Intelligence.

    This layer does not move SL itself.
    It sends exit/BE/trailing policy fields to the EA Exit Master.

    Philosophy:
    OLD: small profit -> instant BE
    NEW: allow controlled swing room first, then protect after structure confirms continuation.
    """
    if not STRUCTURE_HOLD_ENABLED or not isinstance(decision, dict):
        return decision

    # Base defaults for all decisions so EA always sees a complete policy.
    decision["exit_style"] = DEFAULT_EXIT_STYLE
    decision["be_aggressiveness"] = DEFAULT_BE_AGGRESSIVENESS
    decision["swing_room_required"] = DEFAULT_SWING_ROOM_REQUIRED
    decision["min_be_atr_multiple"] = DEFAULT_MIN_BE_ATR_MULTIPLE
    decision["trail_width_mode"] = DEFAULT_TRAIL_WIDTH_MODE
    decision["trail_width"] = DEFAULT_TRAIL_WIDTH_MODE

    mode = str(decision.get("market_mode", decision.get("mode", "TRANSITION"))).upper()
    bb = str(decision.get("confirmed_bb_state", decision.get("bb_state", decision.get("bb", "NORMAL")))).upper()
    timing = str(decision.get("execution_timing_state", "")).upper()
    location = str(decision.get("entry_location_state", "")).upper()
    exhaustion = str(decision.get("exhaustion_state", "")).upper()
    style = str(decision.get("market_style", "")).upper()
    decision_state = str(decision.get("decision", "NO_TRADE")).upper()

    late_score = safe_int(decision.get("late_entry_score", 0), 0)
    exhaustion_score = safe_int(decision.get("exhaustion_score", 0), 0)
    location_score = safe_int(decision.get("entry_location_score", 50), 50)
    rr = safe_float(decision.get("estimated_reward_risk", decision.get("rr_quality", 0)), 0)

    # Conservative but useful probability estimate for EA policy.
    continuation_probability = 50
    if mode == "TREND":
        continuation_probability += 15
    if bb in ("WALK_UP", "WALK_DOWN"):
        continuation_probability += 10
    if location in ("GOOD_LOCATION", "A_GRADE"):
        continuation_probability += 10
    if timing == "HEALTHY_CONTINUATION":
        continuation_probability += 10
    if exhaustion in ("MEDIUM", "HIGH"):
        continuation_probability -= 15 if exhaustion == "MEDIUM" else 30
    if late_score >= 50:
        continuation_probability -= 15
    if rr >= 1.2:
        continuation_probability += 5
    continuation_probability = clamp_int(continuation_probability, 0, 100)

    # Trend maturity estimate.
    if exhaustion == "HIGH" or late_score >= 70:
        trend_maturity = "EXHAUSTED"
    elif timing == "LATE_CONTINUATION" or late_score >= 50 or exhaustion == "MEDIUM":
        trend_maturity = "MATURE"
    elif mode == "TREND" and bb in ("WALK_UP", "WALK_DOWN"):
        trend_maturity = "HEALTHY"
    elif mode == "TREND":
        trend_maturity = "EARLY_OR_BUILDING"
    else:
        trend_maturity = "UNKNOWN"

    # Pullback risk estimate.
    pullback_risk_score = 30
    if late_score >= 50:
        pullback_risk_score += 20
    if exhaustion_score >= 55:
        pullback_risk_score += 25
    if location_score < 45:
        pullback_risk_score += 15
    if bb in ("REVERSAL_UP", "REVERSAL_DOWN"):
        pullback_risk_score += 15
    pullback_risk_score = clamp_int(pullback_risk_score, 0, 100)
    if pullback_risk_score >= 70:
        pullback_risk = "HIGH"
    elif pullback_risk_score >= 45:
        pullback_risk = "NORMAL"
    else:
        pullback_risk = "LOW"

    # Structure confirmation: report-only until Writer supplies real candle/swing fields.
    structure_confirmed = bool(
        str(decision.get("pullback_state", "")).upper() in ("CONTINUATION_RETURN", "HEALTHY_PULLBACK")
        or str(decision.get("entry_timing", "")).upper() == "EARLY_CONTINUATION"
        or timing == "HEALTHY_CONTINUATION"
        or (mode == "TREND" and bb in ("WALK_UP", "WALK_DOWN") and location_score >= 55)
    )

    # Noise zone policy: EA should avoid BE while trade is still inside noise.
    # Since ATR active indicator was removed from AI direction, this is a policy multiplier only.
    if structure_confirmed and continuation_probability >= 65:
        noise_zone_status = "CAN_PROTECT_AFTER_STRUCTURE"
    else:
        noise_zone_status = "INSIDE_NOISE_ZONE_OR_UNCONFIRMED"

    decision["structure_confirmed"] = structure_confirmed
    decision["continuation_probability"] = continuation_probability
    decision["pullback_risk"] = pullback_risk
    decision["pullback_risk_score"] = pullback_risk_score
    decision["trend_maturity"] = trend_maturity
    decision["noise_zone_status"] = noise_zone_status

    # Current V25.5 default: low BE aggression and wide trail.
    # Only allow normal/moderate BE policy after stronger confirmation.
    if decision_state == "TRADE":
        if not structure_confirmed or noise_zone_status == "INSIDE_NOISE_ZONE_OR_UNCONFIRMED":
            decision["be_aggressiveness"] = "LOW"
            decision["swing_room_required"] = True
            decision["trail_width_mode"] = "WIDE"
            decision["trail_width"] = "WIDE"
            decision["exit_management_note"] = (
                "Do not move BE from tiny profit; wait for structure/continuation confirmation."
            )
        elif continuation_probability >= 70 and pullback_risk != "HIGH":
            decision["be_aggressiveness"] = "LOW_TO_NORMAL"
            decision["swing_room_required"] = True
            decision["trail_width_mode"] = "WIDE"
            decision["trail_width"] = "WIDE"
            decision["exit_management_note"] = (
                "Structure confirmed; BE allowed only after minimum RR/noise-zone rule."
            )
    else:
        decision["exit_management_note"] = "NO_TRADE policy fields attached for schema consistency."

    decision["structure_hold_policy"] = {
        "exit_style": decision["exit_style"],
        "be_aggressiveness": decision["be_aggressiveness"],
        "swing_room_required": decision["swing_room_required"],
        "min_be_atr_multiple": decision["min_be_atr_multiple"],
        "trail_width": decision["trail_width_mode"],
    }

    return decision

def apply_bb_state_smoothing_v25_4(data):
    """
    V25.4 BB State Smoothing.

    Separates:
    - raw_bb_state: direct Writer/indicator state
    - confirmed_bb_state: smoothed state used by AI decision logic

    Confirmation requires either:
    - same raw state count >= BB_CONFIRM_MIN_SAME_RAW_COUNT
    OR
    - same raw state age >= BB_CONFIRM_MIN_SECONDS
    """
    if not BB_SMOOTHING_ENABLED or not isinstance(data, dict):
        return data

    now_ts = int(time.time())
    raw = _bb_clean_state_v25_4(data.get("bb_state", data.get("bb", "NORMAL")))

    last_raw = bb_smoothing_state.get("last_raw_bb_state", "NORMAL")
    confirmed = bb_smoothing_state.get("confirmed_bb_state", "NORMAL")

    if raw != last_raw:
        bb_smoothing_state["flip_count"] = safe_int(bb_smoothing_state.get("flip_count", 0), 0) + 1
        bb_smoothing_state["last_raw_bb_state"] = raw
        bb_smoothing_state["raw_state_started_ts"] = now_ts
        bb_smoothing_state["same_raw_count"] = 1
    else:
        bb_smoothing_state["same_raw_count"] = safe_int(bb_smoothing_state.get("same_raw_count", 0), 0) + 1

    raw_age = max(0, now_ts - safe_int(bb_smoothing_state.get("raw_state_started_ts", now_ts), now_ts))
    same_count = safe_int(bb_smoothing_state.get("same_raw_count", 1), 1)

    if raw == confirmed:
        bb_confidence = 100
    elif same_count >= BB_CONFIRM_MIN_SAME_RAW_COUNT or raw_age >= BB_CONFIRM_MIN_SECONDS:
        confirmed = raw
        bb_smoothing_state["confirmed_bb_state"] = confirmed
        bb_confidence = 80
    else:
        bb_confidence = 45

    bb_smoothing_state["raw_bb_state"] = raw
    bb_smoothing_state["last_update_ts"] = now_ts

    # Keep raw fields for logging.
    data["raw_bb_state"] = raw
    data["confirmed_bb_state"] = confirmed
    data["bb_state_age_sec"] = raw_age
    data["bb_flip_count"] = safe_int(bb_smoothing_state.get("flip_count", 0), 0)
    data["bb_confidence"] = bb_confidence

    # AI logic should consume confirmed state.
    data["bb_state"] = confirmed
    data["bb"] = confirmed

    return data


def apply_bb_smoothing_fields_to_decision_v25_4(decision, source=None):
    if not isinstance(decision, dict):
        return decision
    source = source or decision

    raw = _bb_clean_state_v25_4(source.get("raw_bb_state", source.get("bb_state", source.get("bb", "NORMAL"))))
    confirmed = _bb_clean_state_v25_4(source.get("confirmed_bb_state", source.get("bb_state", source.get("bb", "NORMAL"))))

    decision["raw_bb_state"] = raw
    decision["confirmed_bb_state"] = confirmed
    decision["bb_state_age_sec"] = safe_int(source.get("bb_state_age_sec", 0), 0)
    decision["bb_flip_count"] = safe_int(source.get("bb_flip_count", 0), 0)
    decision["bb_confidence"] = safe_int(source.get("bb_confidence", 100), 100)

    # Ensure final decision exposes and uses confirmed BB state.
    decision["bb_state"] = confirmed
    decision["bb"] = confirmed

    # BB NORMAL must not hard block.
    reason = str(decision.get("reason", ""))
    if BB_NORMAL_IS_NOT_HARD_BLOCK and "BB=NORMAL" in reason.upper() and "NOT STRONG BB WALK" in reason.upper():
        decision["bb_normal_softened"] = True
        decision["reason"] = reason + " | BB_NORMAL_CONTEXT_ONLY"

    # REVERSAL is penalty only unless other gates already created explicit hard block.
    if BB_REVERSAL_IS_QUALITY_PENALTY_ONLY and confirmed in ("REVERSAL_UP", "REVERSAL_DOWN"):
        decision["bb_reversal_quality_penalty_only"] = True
        decision["bb_reversal_note"] = "BB reversal is context/quality penalty, not auto hard block"

    return decision

def apply_v25_3_rsi_soft_penalty_recovery(decision):
    if not isinstance(decision, dict) or not V25_3_RSI_SOFT_PENALTY_MODE:
        return decision

    if decision.get("decision") != "NO_TRADE":
        return decision

    reason = str(decision.get("reason", ""))
    rl = reason.lower()
    is_target_block = (
        "transition+normal not strong enough" in rl
        and ("rsi_not_bullish" in rl or "rsi_not_bearish" in rl)
    )
    if not is_target_block:
        return decision

    buy = safe_int(decision.get("buy_score", decision.get("buyScore", 0)), 0)
    sell = safe_int(decision.get("sell_score", decision.get("sellScore", 0)), 0)
    gap = abs(buy - sell)
    bias = "BUY" if buy > sell else "SELL" if sell > buy else str(decision.get("bias", "NEUTRAL")).upper()
    rsi = safe_float(decision.get("rsi", 50), 50)
    mode = str(decision.get("market_mode", decision.get("mode", "TRANSITION"))).upper()
    bb = str(decision.get("bb_state", decision.get("bb", "NORMAL"))).upper()
    age = safe_int(decision.get("market_state_age_sec", 999), 999)

    hard_block_words = [
        "STALE", "INVALID_SCHEMA", "EXHAUSTION_HIGH", "EXECUTION_TIMING_BLOCK",
        "LATE_ENTRY HIGH", "SR_ENTRY_LOCATION_BLOCK", "LOW_RR", "SUPPORT_RESISTANCE_BLOCK"
    ]
    hard_block = any(w in reason.upper() for w in hard_block_words)
    strongly_opposite = (
        (bias == "BUY" and rsi <= V25_3_RSI_STRONGLY_OPPOSITE_BUY)
        or (bias == "SELL" and rsi >= V25_3_RSI_STRONGLY_OPPOSITE_SELL)
    )

    if (
        V25_3_ALLOW_TRANSITION_NORMAL_SCALP
        and mode == "TRANSITION"
        and bb == "NORMAL"
        and gap >= 2
        and bias in ("BUY", "SELL")
        and age <= TEMP_MARKET_STATE_STALE_LIMIT_SEC
        and not hard_block
        and not strongly_opposite
    ):
        decision["decision"] = "TRADE"
        decision["bias"] = bias
        decision["action"] = bias
        decision["entry_allowed"] = True
        decision["management"] = "SCALP_TP"
        decision["mgmt"] = "SCALP_TP"
        decision["market_style"] = "SCALP"
        decision["rsi_soft_penalty_applied"] = True
        decision["rsi_soft_penalty_reason"] = f"RSI softened; bias={bias} gap={gap} rsi={rsi:.2f}"
        decision["final_gate_override"] = True
        decision["final_gate_reason"] = f"V25_3_TRANSITION_NORMAL_SCALP_ALLOW | bias={bias} gap={gap} rsi={rsi:.2f} age={age}"
        decision["reason"] = reason + " | " + decision["final_gate_reason"]
    else:
        decision["final_gate_block_reason_class"] = (
            "RSI_STRONGLY_OPPOSITE" if strongly_opposite
            else "EXPLICIT_HARD_BLOCK" if hard_block
            else "RSI_SOFT_PENALTY_NOT_RECOVERED"
        )
        decision["final_gate_reason"] = decision["final_gate_block_reason_class"]

    return decision

def apply_final_decision_gate_trace_v25_2(decision):
    """
    V25.2 final gate audit and recovery.

    Rule:
    If signal is strong and infrastructure is fresh/valid, final decision must not stay NO_TRADE
    unless a specific hard-block reason exists.
    """
    if not FINAL_GATE_TRACE_ENABLED or not isinstance(decision, dict):
        return decision

    strong, snap = is_strong_signal_v25_2(decision)
    decision["final_gate_trace_enabled"] = True
    decision["final_gate_signal_buy_score"] = snap["buy_score"]
    decision["final_gate_signal_sell_score"] = snap["sell_score"]
    decision["final_gate_signal_gap"] = snap["score_gap"]
    decision["final_gate_signal_bias"] = snap["inferred_bias"]
    decision["final_gate_mode"] = snap["market_mode"]
    decision["final_gate_bb"] = snap["bb_state"]

    if decision.get("decision") == "NO_TRADE":
        ok_reason, reason_key = has_specific_no_trade_reason_v25_2(decision)
        decision["final_gate_block_reason_class"] = reason_key
        decision["final_gate_reason_is_specific"] = ok_reason

        if strong and not ok_reason and STRONG_SIGNAL_OVERRIDE_ENABLED:
            # Recover from silent/generic NO_TRADE when signal layer is clearly valid.
            recovered_bias = snap["inferred_bias"]
            decision["decision"] = "TRADE"
            decision["bias"] = recovered_bias
            decision["action"] = recovered_bias
            decision["entry_allowed"] = True
            decision["management"] = "SCALP_TP"
            decision["mgmt"] = "SCALP_TP"
            decision["slot"] = decision.get("slot", decision.get("entry_slot", 2))
            decision["final_gate_override"] = True
            decision["final_gate_reason"] = (
                f"STRONG_SIGNAL_OVERRIDE | {recovered_bias} gap={snap['score_gap']} "
                f"mode={snap['market_mode']} bb={snap['bb_state']} age={decision.get('market_state_age_sec')}"
            )
            decision["reason"] = (str(decision.get("reason", "")) + " | " + decision["final_gate_reason"]).strip()
        elif decision.get("decision") == "NO_TRADE" and not ok_reason:
            # Keep NO_TRADE but make reason explicit so EA/debug never sees generic suppression.
            decision["reason"] = (
                str(decision.get("reason", "")).strip()
                + f" | FINAL_GATE_GENERIC_NO_TRADE_BLOCKED reason_class={reason_key}"
            ).strip()
            decision["final_gate_reason"] = decision["reason"]
    else:
        decision["final_gate_block_reason_class"] = "TRADE"
        decision["final_gate_reason_is_specific"] = True
        decision["final_gate_reason"] = "TRADE_ALLOWED"

    return decision

def normalize_decision_schema_v20_2(decision):
    """
    EA V20.2 decision.json schema guard.
    Guarantees valid market_mode / bb_state / decision heartbeat every write.
    """
    global decision_sequence_counter

    if not isinstance(decision, dict):
        decision = {}

    now_unix = int(time.time())
    decision_sequence_counter += 1

    dec = _schema_clean_str(decision.get("decision", "NO_TRADE"), "NO_TRADE")
    if dec not in VALID_DECISIONS:
        dec = "NO_TRADE"

    bias = _schema_clean_str(decision.get("bias", decision.get("action", "NEUTRAL")), "NEUTRAL")
    if dec == "TRADE" and bias not in ("BUY", "SELL"):
        dec = "NO_TRADE"
        bias = "NEUTRAL"
        decision["reason"] = (str(decision.get("reason", "")) + " | INVALID_TRADE_BIAS_DOWNGRADED").strip()
    elif bias not in VALID_BIASES:
        bias = "NEUTRAL"

    mode = _schema_clean_str(decision.get("market_mode", decision.get("mode", decision.get("marketMode", ""))), "TRANSITION")
    if mode in ("UNKNOWN", "NONE", "NULL", "") or mode not in VALID_MARKET_MODES:
        mode = "TRANSITION"

    bb = _schema_clean_str(decision.get("bb_state", decision.get("bb", decision.get("bbState", ""))), "NORMAL")
    if bb in ("UNKNOWN", "NONE", "NULL", "") or bb not in VALID_BB_STATES:
        bb = "NORMAL"

    mgmt = _schema_clean_str(
        decision.get("management", decision.get("mgmt", "NO_TRADE" if dec == "NO_TRADE" else "SCALP_TP")),
        "NO_TRADE" if dec == "NO_TRADE" else "SCALP_TP"
    )
    if mgmt not in VALID_MANAGEMENT:
        mgmt = "NO_TRADE" if dec == "NO_TRADE" else "SCALP_TP"
    if dec == "NO_TRADE":
        mgmt = "NO_TRADE"

    market_sequence = safe_int(
        decision.get("market_state_sequence_id", decision.get("market_sequence_id", decision.get("sequence_id", 0))),
        0
    )
    market_age = safe_int(decision.get("market_state_age_sec", -1), -1)

    decision["decision"] = dec
    decision["bias"] = bias
    decision["market_mode"] = mode
    decision["mode"] = mode
    decision["bb_state"] = bb
    decision["bb"] = bb
    decision["management"] = mgmt
    decision["mgmt"] = mgmt

    # Decision heartbeat/sequence must represent decision freshness, not old market_state freshness.
    decision["heartbeat_unix"] = now_unix
    decision["decision_heartbeat_unix"] = now_unix
    decision["sequence_id"] = decision_sequence_counter
    decision["decision_sequence_id"] = decision_sequence_counter
    decision["market_state_sequence_id"] = market_sequence
    decision["market_state_age_sec"] = market_age
    decision["decision_age_sec"] = 0
    decision["updated_at"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    if not str(decision.get("time_sync_standard", "")).strip():
        decision["time_sync_standard"] = "RP_TIME_SYNC_STANDARD_V1"

    decision.setdefault("slot", 0 if dec == "NO_TRADE" else 1)
    if "sl" not in decision:
        decision["sl"] = safe_float(decision.get("stop_loss", 0), 0.0)
    if "tp" not in decision:
        decision["tp"] = safe_float(decision.get("tp1", 0), 0.0)
    if dec == "NO_TRADE":
        decision["entry_allowed"] = False
    else:
        decision["entry_allowed"] = bool(decision.get("entry_allowed", True))

    return decision

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
    data.setdefault("execution_window_state", "NOT_EVALUATED")
    data.setdefault("entry_window_score", 0)
    data.setdefault("short_term_countertrend", False)
    data.setdefault("pullback_phase", False)
    data.setdefault("trend_phase", "UNKNOWN")
    data.setdefault("execution_delay_reason", "")
    data.setdefault("execution_window_open", False)
    data.setdefault("entry_window_validation", "NOT_EVALUATED")
    data.setdefault("trend_momentum_mode", "")
    data.setdefault("trend_momentum_reason", "")
    data.setdefault("trend_momentum_override", False)
    data.setdefault("transition_decay_count", 0)
    data.setdefault("transition_decay_required", 0)
    data.setdefault("transition_decay_active", False)
    data.setdefault("transition_decay_reason", "")
    data.setdefault("transition_wait_max_cycles", TRANSITION_WAIT_MAX_CYCLES)
    data.setdefault("transition_wait_released", False)
    data.setdefault("participation_release", False)
    data.setdefault("participation_release_reason", "")
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
    data.setdefault("heartbeat_unix", 0)
    data.setdefault("sequence_id", 0)
    data.setdefault("market_state_sequence_id", 0)
    data.setdefault("market_state_age_sec", -1)
    data.setdefault("decision_age_sec", 0)
    data.setdefault("time_sync_standard", TIME_SYNC_STANDARD)
    data.setdefault("pullback_state", "UNKNOWN")
    data.setdefault("pullback_quality", 0)
    data.setdefault("pullback_depth", "UNKNOWN")
    data.setdefault("pullback_depth_pct", 0)
    data.setdefault("continuation_return", False)
    data.setdefault("continuation_quality", 0)
    data.setdefault("entry_timing", "UNKNOWN")
    data.setdefault("runner_allowed", False)
    data.setdefault("pullback_reason", "")
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

    # Mandatory NO_TRADE explainability schema. These defaults are observability-only
    # and are populated with concrete blocker details immediately before publish.
    data.setdefault("no_trade_reason", "")
    data.setdefault("no_trade_reasons", [])
    data.setdefault("blocked_stage", "")
    data.setdefault("blocking_module", "")
    data.setdefault("confidence_score", safe_float(data.get("confidence", 0), 0.0))
    data.setdefault("score_gap", abs(safe_int(data.get("buy_score"), 0) - safe_int(data.get("sell_score"), 0)))
    data.setdefault("required_score_gap", safe_int(data.get("adaptive_gap", data.get("minimum_score_gap_required", 0)), 0))
    data.setdefault("entry_window_state", data.get("execution_window_state", data.get("entry_window_validation", "NOT_EVALUATED")))
    data.setdefault("bb_state", data.get("bb", "NORMAL"))
    data.setdefault("rsi_state", "NOT_EVALUATED")
    data.setdefault("macd_state", "NOT_EVALUATED")
    data.setdefault("countertrend_state", "NOT_EVALUATED")
    data.setdefault("exhaustion_state", data.get("trend_exhaustion", "NOT_EVALUATED"))
    data.setdefault("protection_state", data.get("active_protection_state", "NOT_EVALUATED"))
    data.setdefault("final_veto_reason", "")
    data.setdefault("final_veto_owner", "")
    data.setdefault("effective_veto_code", "")
    data.setdefault("duplicate_veto_consolidation", "NOT_EVALUATED")
    data.setdefault("duplicate_veto_telemetry", [])
    data.setdefault("score_decomposition", {})
    data.setdefault("score_gap_audit", "")


    if "_market_state_path" in data:
        data["market_state_path"] = data.get("_market_state_path", "")
    if "_market_state_modified_time" in data:
        data["market_state_modified_time"] = data.get("_market_state_modified_time", "")
    if "_market_state_age_sec" in data:
        data["market_state_age_sec"] = data.get("_market_state_age_sec", 0)
    if "_market_state_read_signature" in data:
        data["market_state_read_signature"] = data.get("_market_state_read_signature", "")

    return data



def _trade_entry_price(decision):
    """Best available executable entry reference for late payload construction."""
    for key in ("entry_price", "price", "bid", "current_bid", "last_bid"):
        value = safe_float(decision.get(key, 0), 0.0)
        if value > 0:
            return value
    sl = safe_float(decision.get("sl", decision.get("stop_loss", 0)), 0.0)
    tp = safe_float(decision.get("tp", decision.get("tp1", 0)), 0.0)
    bias = str(decision.get("action", decision.get("bias", ""))).upper()
    if sl > 0 and tp > 0:
        return (sl + tp) / 2.0
    if sl > 0:
        mode = str(decision.get("market_mode", "TRANSITION")).upper()
        sl_points, _ = risk_points_for_mode(mode)
        if bias == "BUY":
            return sl + sl_points
        if bias == "SELL":
            return sl - sl_points
    return 0.0


def _append_no_trade_reason(reasons, code, detail="", stage="", module="", priority=50):
    if not code:
        return
    reasons.append({
        "priority": priority,
        "code": str(code).upper(),
        "detail": str(detail or code),
        "blocked_stage": str(stage or "DECISION_ENGINE"),
        "blocking_module": str(module or "AI_DECISION_ENGINE"),
    })


def _classify_no_trade_reason_text(reason_text):
    text = str(reason_text or "").upper()
    if "COOLDOWN" in text or "MAX SIGNAL" in text or "WAIT" in text:
        return "WAIT_ENTRY_WINDOW", "ENTRY_WINDOW", "COOLDOWN_GATE", 10
    if "SOFT LOCK" in text or "TRANSITION_WAIT" in text or "COUNTERTREND" in text:
        return "COUNTERTREND_BLOCK", "COUNTERTREND", "SOFT_DIRECTION_LOCK", 15
    if "WEAK GAP" in text or "SCORE_GAP" in text or "ADAPTIVE SCORE GAP" in text or "WEAK EDGE" in text:
        return "INSUFFICIENT_SCORE_GAP", "SCORING", "SCORE_GAP_GATE", 20
    if "RSI" in text and ("MID" in text or "MIDDLE" in text):
        return "RSI_MIDZONE", "MOMENTUM_FILTER", "RSI_FILTER", 25
    if "BB" in text and ("EXHAUST" in text or "DEV4" in text or "OVEREXTENSION" in text):
        return "BB_EXHAUSTION", "BB_FILTER", "BOLLINGER_FILTER", 30
    if "BB" in text or "COMPRESSION" in text or "REVERSAL ZONE" in text:
        return "BB_STATE_BLOCK", "BB_FILTER", "BOLLINGER_FILTER", 35
    if "EXHAUST" in text or "LATE" in text:
        return "EXHAUSTION_BLOCK", "EXHAUSTION_PROTECTION", "EXHAUSTION_GUARD", 40
    if "PROTECTION" in text or "LOSS" in text or "RISK" in text or "RR" in text:
        return "PROTECTION_BLOCK", "PROTECTION", "PROTECTION_AUTHORITY", 45
    if "INVALID" in text or "STALE" in text or "MARKET_STATE" in text:
        return "INVALID_OR_STALE_MARKET_STATE", "MARKET_STATE", "MARKET_STATE_READER", 5
    if "NO SETUP" in text:
        return "NO_EXECUTABLE_SETUP", "SETUP_SELECTION", "SETUP_CLASSIFIER", 55
    return "FINAL_VETO", "FINAL_DECISION", "FINAL_DECISION_GATE", 90


def _rsi_state_for_decision(decision):
    rsi = safe_float(decision.get("rsi", 0), 0.0)
    bias = str(decision.get("bias", decision.get("action", "NEUTRAL"))).upper()
    if rsi <= 0:
        return "NOT_EVALUATED"
    if 45 <= rsi <= 55:
        return "RSI_MIDZONE"
    if bias == "BUY" and rsi >= 70:
        return "BUY_OVERBOUGHT"
    if bias == "SELL" and rsi <= 30:
        return "SELL_OVERSOLD"
    return "DIRECTIONAL_CONFIRM" if bias in ("BUY", "SELL") else "NEUTRAL"


def _macd_state_for_decision(decision):
    macd = safe_float(decision.get("macd_hist", 0), 0.0)
    bias = str(decision.get("bias", decision.get("action", "NEUTRAL"))).upper()
    if macd == 0:
        return "FLAT_OR_NOT_EVALUATED"
    if (bias == "BUY" and macd > 0) or (bias == "SELL" and macd < 0):
        return "DIRECTIONAL_CONFIRM"
    if bias in ("BUY", "SELL"):
        return "DIRECTIONAL_CONFLICT"
    return "NEUTRAL"


def attach_no_trade_explainability(decision):
    """
    Publish a complete, structured explanation for every NO_TRADE decision.
    Observability only: does not change thresholds, indicators, or trade decisions.
    """
    if not isinstance(decision, dict) or str(decision.get("decision", "")).upper() != "NO_TRADE":
        return decision

    reasons = []
    reason_text = str(decision.get("reason", "") or decision.get("final_veto_reason", "") or "NO_TRADE")
    code, stage, module, priority = _classify_no_trade_reason_text(reason_text)
    _append_no_trade_reason(reasons, code, reason_text, stage, module, priority)

    score_gap = abs(safe_int(decision.get("buy_score"), 0) - safe_int(decision.get("sell_score"), 0))
    required_gap = safe_int(decision.get("required_score_gap", 0), 0)
    if required_gap <= 0:
        required_gap = safe_int(decision.get("adaptive_gap", decision.get("minimum_score_gap_required", 0)), 0)
    if required_gap > 0 and score_gap < required_gap:
        _append_no_trade_reason(
            reasons,
            "INSUFFICIENT_SCORE_GAP",
            f"score_gap={score_gap} < required_score_gap={required_gap}",
            "SCORING",
            "SCORE_GAP_GATE",
            20,
        )

    entry_window_state = str(decision.get("execution_window_state", decision.get("entry_window_validation", "")) or "").upper()
    execution_delay = str(decision.get("execution_delay_reason", "") or "").strip()
    if entry_window_state and entry_window_state not in ("OPEN", "PASS", "PASSED", "APPROVED", "NOT_EVALUATED"):
        _append_no_trade_reason(reasons, "WAIT_ENTRY_WINDOW", execution_delay or entry_window_state, "ENTRY_WINDOW", "EXECUTION_TIMING_LAYER", 10)

    if bool(decision.get("short_term_countertrend", False)) or str(decision.get("soft_lock_state", "")).upper() in ("TREND_LOCK", "TRANSITION_WAIT"):
        _append_no_trade_reason(
            reasons,
            "COUNTERTREND_BLOCK",
            decision.get("soft_lock_reason", decision.get("execution_delay_reason", "")),
            "COUNTERTREND",
            "SOFT_DIRECTION_LOCK",
            15,
        )

    exhaustion_state = str(decision.get("trend_exhaustion", decision.get("exhaustion_state", "")) or "").upper()
    if exhaustion_state in ("BLOCK", "BLOCKED", "EXHAUSTED", "HIGH", "EXTREME") or bool(decision.get("late_continuation_risk", False)):
        _append_no_trade_reason(reasons, "EXHAUSTION_BLOCK", decision.get("trend_exhaustion_reason", exhaustion_state), "EXHAUSTION_PROTECTION", "EXHAUSTION_GUARD", 40)

    protection_state = str(decision.get("active_protection_state", decision.get("protection_state", "")) or "").upper()
    if protection_state and protection_state not in ("NONE", "CLEAR", "NOT_EVALUATED", "INACTIVE"):
        _append_no_trade_reason(reasons, "PROTECTION_BLOCK", decision.get("active_protection_reason", protection_state), "PROTECTION", "PROTECTION_AUTHORITY", 45)

    deduped = {}
    duplicate_veto_telemetry = decision.setdefault("duplicate_veto_telemetry", [])
    if not isinstance(duplicate_veto_telemetry, list):
        duplicate_veto_telemetry = []
        decision["duplicate_veto_telemetry"] = duplicate_veto_telemetry
    for item in reasons:
        key = item["code"]
        if key not in deduped or item["priority"] < deduped[key]["priority"]:
            if key in deduped:
                duplicate_veto_telemetry.append({
                    "module": item["blocking_module"],
                    "code": item["code"],
                    "reason": item["detail"],
                    "effective": False,
                    "duplicate_of": deduped[key]["blocking_module"],
                })
            deduped[key] = item
        else:
            duplicate_veto_telemetry.append({
                "module": item["blocking_module"],
                "code": item["code"],
                "reason": item["detail"],
                "effective": False,
                "duplicate_of": deduped[key]["blocking_module"],
            })
    ordered = sorted(deduped.values(), key=lambda item: item["priority"])
    primary = ordered[0] if ordered else {
        "code": "FINAL_VETO",
        "detail": reason_text,
        "blocked_stage": "FINAL_DECISION",
        "blocking_module": "FINAL_DECISION_GATE",
    }

    decision["no_trade_reason"] = primary["code"]
    decision["no_trade_reasons"] = [
        {k: v for k, v in item.items() if k != "priority"}
        for item in ordered
    ]
    decision["blocked_stage"] = primary["blocked_stage"]
    decision["blocking_module"] = primary["blocking_module"]
    decision["final_veto_owner"] = str(decision.get("final_veto_owner", "") or primary["blocking_module"])
    decision["effective_veto_code"] = str(decision.get("effective_veto_code", "") or primary["code"])
    decision["duplicate_veto_consolidation"] = "ACTIVE"
    decision["confidence_score"] = safe_float(decision.get("confidence", decision.get("execution_confidence_score", 0)), 0.0)
    decision["score_gap"] = score_gap
    decision["required_score_gap"] = required_gap
    decision["entry_window_state"] = entry_window_state or "NOT_EVALUATED"
    decision["bb_state"] = str(decision.get("bb_state", decision.get("bb", "UNKNOWN"))).upper()
    decision["rsi_state"] = _rsi_state_for_decision(decision)
    decision["macd_state"] = _macd_state_for_decision(decision)
    decision["countertrend_state"] = "BLOCKED" if any(item["code"] == "COUNTERTREND_BLOCK" for item in ordered) else "CLEAR"
    decision["exhaustion_state"] = exhaustion_state or "NOT_EVALUATED"
    decision["protection_state"] = protection_state or "NOT_EVALUATED"
    decision["final_veto_reason"] = reason_text
    decision = attach_score_decomposition(decision)
    return decision



def _dashboard_exit_mode_from_decision(decision):
    dashboard_exit_mode = str(
        decision.get(
            "dashboard_exit_mode",
            decision.get("fixed_take_profit_close_mode", decision.get("dashboard_fixed_take_profit_close_mode", ""))
        )
    ).upper().strip()
    fixed_take_profit = decision.get("dashboard_fixed_take_profit", {})
    if isinstance(fixed_take_profit, dict) and not dashboard_exit_mode:
        dashboard_exit_mode = str(fixed_take_profit.get("close_mode", "")).upper().strip()
    return dashboard_exit_mode


def _tp_only_sl_suppression_approved(decision):
    active_profile = str(decision.get("active_profile", decision.get("dashboard_active_profile", ""))).upper().strip()
    fixed_take_profit = decision.get("dashboard_fixed_take_profit", {})
    fixed_tp_enabled = bool(decision.get("fixed_take_profit_enabled_by_dashboard", False))
    if isinstance(fixed_take_profit, dict):
        fixed_tp_enabled = fixed_tp_enabled or bool(fixed_take_profit.get("enable", fixed_take_profit.get("fixed_take_profit_enable", False)))
    dashboard_exit_mode = _dashboard_exit_mode_from_decision(decision)
    risk = decision.get("dashboard_risk", {})
    initial_sl = safe_float(decision.get("initial_sl_usd_001_lot", risk.get("initial_sl_usd_001_lot", 0.0) if isinstance(risk, dict) else 0.0), 0.0)
    broker_sl_required = _protection_bool(decision.get("broker_sl_required", active_profile != "TP_ONLY_1USD_TEST"))
    approved = (
        active_profile == "TP_ONLY_1USD_TEST"
        and not broker_sl_required
        and initial_sl <= 0
        and fixed_tp_enabled
        and dashboard_exit_mode in ("MARKET_CLOSE", "IMMEDIATE_MARKET_CLOSE")
    )
    decision["broker_sl_required"] = broker_sl_required
    decision["broker_tp_required"] = not (approved and dashboard_exit_mode in ("MARKET_CLOSE", "IMMEDIATE_MARKET_CLOSE"))
    decision["dashboard_exit_mode"] = dashboard_exit_mode
    decision["profile_sl_suppression_check"] = "PROFILE_SL_SUPPRESSION_APPROVED" if approved else "PROFILE_SL_SUPPRESSION_REJECTED"
    print(decision["profile_sl_suppression_check"], f"profile={active_profile}", f"broker_sl_required={broker_sl_required}", f"exit_mode={dashboard_exit_mode}")
    return approved


def _risk_payload_trace_fields(decision, entry_price=None, sl=None, tp=None, risk_distance=None, repair_applied=False):
    active_profile = str(decision.get("active_profile", decision.get("dashboard_active_profile", ""))).upper().strip()
    direction = str(decision.get("direction", decision.get("action", decision.get("bias", "")))).upper().strip()
    if entry_price is None:
        entry_price = _trade_entry_price(decision)
    if sl is None:
        sl = safe_float(decision.get("sl", decision.get("stop_loss", 0)), 0.0)
    if tp is None:
        tp = safe_float(decision.get("tp", decision.get("tp1", decision.get("take_profit", 0))), 0.0)
    if risk_distance is None:
        risk_distance = abs(entry_price - sl) if entry_price > 0 and sl > 0 else safe_float(decision.get("risk_distance", decision.get("planned_sl_risk_points", 0)), 0.0)
    return {
        "active_profile": active_profile,
        "broker_sl_required": bool(decision.get("broker_sl_required", True)),
        "broker_tp_required": bool(decision.get("broker_tp_required", True)),
        "direction": direction,
        "entry_price": round(entry_price, 3) if entry_price > 0 else entry_price,
        "stop_loss": round(sl, 3) if sl > 0 else sl,
        "take_profit": round(tp, 3) if tp > 0 else tp,
        "risk_distance": round(risk_distance, 3) if risk_distance > 0 else risk_distance,
        "management_mode": str(decision.get("management", decision.get("mgmt", ""))).upper().strip(),
        "source_of_sl": str(decision.get("source_of_sl", decision.get("initial_order_send_sl_tp_source", ""))),
        "source_of_tp": str(decision.get("source_of_tp", decision.get("initial_order_send_sl_tp_source", ""))),
        "repair_applied": bool(repair_applied),
    }


def _log_risk_payload_event(event, decision, **overrides):
    fields = _risk_payload_trace_fields(decision, **overrides)
    decision[event.lower()] = fields
    decision["risk_payload_trace"] = event
    print(event, " ".join(f"{k}={v}" for k, v in fields.items()))


def _risk_geometry_valid(direction, entry_price, sl, tp, broker_sl_required=True, broker_tp_required=True):
    errors = []
    if broker_sl_required:
        if sl <= 0:
            errors.append(f"sl_invalid={sl}")
        elif direction == "BUY" and sl >= entry_price:
            errors.append(f"sl_geometry_invalid_buy_sl={sl}_entry={entry_price}")
        elif direction == "SELL" and sl <= entry_price:
            errors.append(f"sl_geometry_invalid_sell_sl={sl}_entry={entry_price}")
    if broker_tp_required:
        if tp <= 0:
            errors.append(f"tp_invalid={tp}")
        elif direction == "BUY" and tp <= entry_price:
            errors.append(f"tp_geometry_invalid_buy_tp={tp}_entry={entry_price}")
        elif direction == "SELL" and tp >= entry_price:
            errors.append(f"tp_geometry_invalid_sell_tp={tp}_entry={entry_price}")
    return errors


def _construct_emergency_default_risk(decision, reason):
    """Last-mile broker risk repair for otherwise valid TRADE payloads."""
    direction = str(decision.get("direction", decision.get("action", decision.get("bias", "")))).upper().strip()
    entry_price = _trade_entry_price(decision)
    if direction not in ("BUY", "SELL") or entry_price <= 0:
        decision["sl_zero_repair_status"] = "SL_ZERO_REPAIR_FAILED"
        _log_risk_payload_event("SL_ZERO_REPAIR_FAILED", decision, entry_price=entry_price)
        return decision, False

    risk = decision.get("dashboard_risk", {})
    sl_usd = safe_float(decision.get("initial_sl_usd_001_lot", risk.get("initial_sl_usd_001_lot", 1.20) if isinstance(risk, dict) else 1.20), 1.20)
    if sl_usd <= 0:
        sl_usd = 1.20
    tp_usd = safe_float(decision.get("fixed_take_profit_close_usd_001_lot", decision.get("fixed_tp_usd", 1.00)), 1.00)
    if tp_usd <= 0:
        tp_usd = 1.00

    sl_distance = max(_v26_6_2_usd_to_points(sl_usd), 0.001)
    tp_distance = max(_v26_6_2_usd_to_points(tp_usd), 0.001)
    sl = entry_price - sl_distance if direction == "BUY" else entry_price + sl_distance
    tp = entry_price + tp_distance if direction == "BUY" else entry_price - tp_distance
    sl = round(sl, 3)
    tp = round(tp, 3)

    decision["sl"] = sl
    decision["stop_loss"] = sl
    decision["tp"] = tp
    decision["tp1"] = tp
    decision["take_profit"] = tp
    decision["risk_distance"] = round(abs(entry_price - sl), 3)
    decision["source_of_sl"] = f"EMERGENCY_DEFAULT_DASHBOARD_RISK:{reason}"
    decision["source_of_tp"] = f"EMERGENCY_DEFAULT_FIXED_TP:{reason}"
    decision["repair_applied"] = True
    decision["risk_default_constructed"] = "RISK_DEFAULT_CONSTRUCTED"
    decision["sl_zero_repair_status"] = "SL_ZERO_REPAIR_SUCCESS"
    _log_risk_payload_event("RISK_DEFAULT_CONSTRUCTED", decision, entry_price=entry_price, sl=sl, tp=tp, risk_distance=decision["risk_distance"], repair_applied=True)
    _log_risk_payload_event("SL_ZERO_REPAIR_SUCCESS", decision, entry_price=entry_price, sl=sl, tp=tp, risk_distance=decision["risk_distance"], repair_applied=True)
    return decision, True


def enforce_risk_payload_invariant_before_publication(decision):
    """Final pre-publication guard: executable TRADE must never publish invalid broker risk."""
    if not isinstance(decision, dict):
        return decision
    if str(decision.get("decision", "")).upper() != "TRADE":
        return decision

    decision["risk_payload_invariant_check"] = "RISK_PAYLOAD_INVARIANT_CHECK"
    _log_risk_payload_event("RISK_PAYLOAD_TRACE", decision)
    _log_risk_payload_event("RISK_BEFORE_PUBLICATION", decision)
    if safe_float(decision.get("lot", decision.get("position_size", 0)), 0.0) <= 0:
        decision["lot"] = 0.01
        decision["lot_source"] = "EMERGENCY_DEFAULT_REFERENCE_LOT_0_01"
    action = str(decision.get("direction", decision.get("action", decision.get("bias", "")))).upper().strip()
    sl = safe_float(decision.get("sl", decision.get("stop_loss", 0)), 0.0)
    tp = safe_float(decision.get("tp", decision.get("tp1", decision.get("take_profit", 0))), 0.0)
    entry_price = _trade_entry_price(decision)
    risk_distance = abs(entry_price - sl) if entry_price > 0 and sl > 0 else safe_float(decision.get("risk_distance", decision.get("planned_sl_risk_points", 0)), 0.0)
    suppression_approved = _tp_only_sl_suppression_approved(decision)
    broker_sl_required = bool(decision.get("broker_sl_required", True))
    dashboard_exit_mode = str(decision.get("dashboard_exit_mode", "")).upper()
    broker_tp_required = _protection_bool(decision.get("broker_tp_required", True))
    tp_dashboard_managed = dashboard_exit_mode in ("MARKET_CLOSE", "IMMEDIATE_MARKET_CLOSE")

    errors = []
    if action not in ("BUY", "SELL"):
        errors.append(f"action_invalid={action}")
    if safe_float(decision.get("lot", decision.get("position_size", 0)), 0.0) <= 0:
        errors.append(f"lot_invalid={decision.get('lot', decision.get('position_size', 0))}")
    if entry_price <= 0:
        errors.append(f"entry_price_invalid={entry_price}")
    if not str(decision.get("management", decision.get("mgmt", ""))).upper().strip():
        errors.append("management_mode_invalid")
    if broker_sl_required:
        if sl <= 0:
            errors.append(f"sl_invalid={sl}")
        if risk_distance <= 0:
            errors.append(f"risk_distance_invalid={risk_distance}")
    elif sl <= 0 and not suppression_approved:
        errors.append("sl_suppression_not_profile_approved")
    if broker_tp_required and not tp_dashboard_managed and tp <= 0:
        errors.append(f"tp_invalid={tp}")
    errors.extend(_risk_geometry_valid(action, entry_price, sl, tp, broker_sl_required, broker_tp_required and not tp_dashboard_managed))

    repairable = str(decision.get("management", decision.get("mgmt", ""))).upper().strip() in ("HOLD_TRAIL", "TREND_RUNNER", "SCALP_TP")
    if errors and repairable and not suppression_approved and any("sl_" in e or "tp_" in e or "risk_distance" in e for e in errors):
        _log_risk_payload_event("SL_ZERO_REPAIR_ATTEMPT", decision, entry_price=entry_price, sl=sl, tp=tp, risk_distance=risk_distance)
        decision, repaired = _construct_emergency_default_risk(decision, ";".join(errors))
        if repaired:
            sl = safe_float(decision.get("sl", decision.get("stop_loss", 0)), 0.0)
            tp = safe_float(decision.get("tp", decision.get("tp1", decision.get("take_profit", 0))), 0.0)
            entry_price = _trade_entry_price(decision)
            risk_distance = abs(entry_price - sl) if entry_price > 0 and sl > 0 else 0.0
            errors = [e for e in errors if not ("sl_" in e or "tp_" in e or "risk_distance" in e)]
            errors.extend(_risk_geometry_valid(action, entry_price, sl, tp, broker_sl_required, broker_tp_required and not tp_dashboard_managed))
        else:
            _log_risk_payload_event("SL_ZERO_REPAIR_FAILED", decision, entry_price=entry_price, sl=sl, tp=tp, risk_distance=risk_distance)

    if errors:
        bias = action if action in ("BUY", "SELL") else str(decision.get("bias", "NEUTRAL")).upper()
        decision["risk_payload_invariant_result"] = "RISK_PAYLOAD_INVALID"
        decision["risk_payload_invalid_errors"] = errors
        decision["risk_construction_skipped"] = "RISK_CONSTRUCTION_SKIPPED" if str(decision.get("risk_payload_construction", "")).upper().startswith("FAILED") else False
        decision["trade_downgrade_reason"] = "TRADE_DOWNGRADED_INVALID_RISK_PACKAGE"
        decision["decision"] = "NO_TRADE"
        decision["decision_output_state"] = "WAIT_VALID"
        decision["entry_allowed"] = False
        decision["allowed"] = False
        decision["payload_valid"] = False
        decision["payload_validation_failed"] = True
        decision["payload_validation_reason"] = "RISK_PAYLOAD_INVALID: " + "; ".join(errors)
        decision["bias"] = bias if bias in ("BUY", "SELL") else "NEUTRAL"
        decision["action"] = bias if bias in ("BUY", "SELL") else "NEUTRAL"
        decision["no_trade_reason"] = "INVALID_RISK_PACKAGE"
        decision["blocked_stage"] = "RISK_CONSTRUCTION"
        decision["blocking_module"] = "risk_payload_invariant"
        decision["final_veto_reason"] = "RISK_PAYLOAD_INVALID"
        decision["reason"] = (str(decision.get("reason", "")).strip() + " | TRADE_DOWNGRADED_INVALID_RISK_PACKAGE").strip()
        _log_risk_payload_event("TRADE_DOWNGRADED_INVALID_RISK_PACKAGE", decision, entry_price=entry_price, sl=sl, tp=tp, risk_distance=risk_distance)
        print("RISK_PAYLOAD_INVALID", "; ".join(errors))
    else:
        decision["risk_payload_invariant_result"] = "RISK_PAYLOAD_VALID"
        decision["risk_distance"] = round(risk_distance, 3) if risk_distance > 0 else 0
        decision["take_profit"] = round(tp, 3) if tp > 0 else 0
        decision["stop_loss"] = round(sl, 3) if sl > 0 else 0
        decision["payload_valid"] = True
        _log_risk_payload_event("RISK_PAYLOAD_VALID", decision, entry_price=entry_price, sl=sl, tp=tp, risk_distance=risk_distance, repair_applied=bool(decision.get("repair_applied", False)))
        print("RISK_PAYLOAD_VALID", f"sl={sl}", f"tp={tp}", f"entry={entry_price}", f"broker_sl_required={broker_sl_required}")
    return decision

def construct_risk_payload_before_validation(decision):
    """
    V26.4.8 intent-to-payload bridge.

    Any final TRADE decision with BUY/SELL intent must reach payload validation with
    concrete SL/TP. Validation remains the last hard stop if construction cannot
    produce a valid risk packet from available market context.
    """
    if not isinstance(decision, dict):
        return decision

    if str(decision.get("decision", "")).upper() != "TRADE":
        return decision

    bias = str(decision.get("action", decision.get("bias", ""))).upper()
    if bias not in ("BUY", "SELL"):
        return decision

    hard_block, hard_reason = _v26_has_hard_block(decision)
    if hard_block:
        decision["risk_payload_construction"] = "SKIPPED_HARD_BLOCK"
        decision["risk_payload_construction_reason"] = hard_reason
        return decision

    _log_risk_payload_event("RISK_BEFORE_DASHBOARD", decision)
    decision = apply_trade_management_dashboard_v27(decision)
    _log_risk_payload_event("RISK_AFTER_DASHBOARD", decision)
    tp_only_profile = bool(decision.get("tp_only_profile_active", False)) and _tp_only_sl_suppression_approved(decision)
    if bool(decision.get("tp_only_profile_active", False)) and not tp_only_profile:
        decision["risk_payload_construction"] = "TP_ONLY_PROFILE_SL_SUPPRESSION_REJECTED"
        decision["risk_payload_construction_reason"] = "TP_ONLY profile active but broker SL suppression contract is not approved"
    if tp_only_profile:
        decision["sl"] = 0
        decision["stop_loss"] = 0
        decision["initial_order_send_sl_tp_source"] = "TP_ONLY_1USD_TEST: OrderSend SL suppressed; dashboard owns +1.00 USD per 0.01 lot market close"
        decision["risk_payload_construction"] = "TP_ONLY_PROFILE_SL_SUPPRESSED"
        decision["risk_payload_construction_reason"] = "TP_ONLY_PROFILE_ACTIVE; ORDERSEND_SL_SUPPRESSED_BY_PROFILE"
    mode = str(decision.get("market_mode", decision.get("mode", "TRANSITION"))).upper()
    dashboard_initial_sl_usd = safe_float(decision.get("initial_sl_usd_001_lot", 0.0), 0.0)
    if dashboard_initial_sl_usd > 0:
        sl_points = _v26_6_2_usd_to_points(dashboard_initial_sl_usd)
        _, tp_points = risk_points_for_mode(mode)
        decision["initial_order_send_sl_tp_source"] = "DASHBOARD_RISK_INITIAL_SL; TP remains AI setup unless fixed_take_profit dashboard close is enabled"
    else:
        sl_points, tp_points = risk_points_for_mode(mode)
        if not tp_only_profile:
            decision["initial_order_send_sl_tp_source"] = "AI_INITIAL_RISK_ONLY; dashboard initial_sl unavailable; no hidden post-entry override"
    entry_price = _trade_entry_price(decision)
    sl = safe_float(decision.get("sl", decision.get("stop_loss", 0)), 0.0)
    tp = safe_float(decision.get("tp", decision.get("tp1", 0)), 0.0)
    built = []

    if entry_price > 0:
        if sl <= 0 and not tp_only_profile:
            sl = entry_price - sl_points if bias == "BUY" else entry_price + sl_points
            built.append("SL")
        if tp <= 0 and not tp_only_profile:
            tp = entry_price + tp_points if bias == "BUY" else entry_price - tp_points
            built.append("TP")

    if tp_only_profile:
        decision["sl"] = 0
        decision["stop_loss"] = 0
    elif sl > 0:
        decision["sl"] = round(sl, 3)
        decision["stop_loss"] = round(sl, 3)
    if tp_only_profile:
        decision["tp"] = 0
        decision["tp1"] = 0
    elif tp > 0:
        decision["tp"] = round(tp, 3)
        decision["tp1"] = round(tp, 3)
        decision["take_profit"] = round(tp, 3)

    if entry_price > 0:
        decision.setdefault("entry_price", round(entry_price, 3))
        decision.setdefault("price", round(entry_price, 3))
    if safe_float(decision.get("lot", 0), 0.0) <= 0:
        decision["lot"] = 0.01
        decision["lot_source"] = "EMERGENCY_DEFAULT_REFERENCE_LOT_0_01"

    if tp_only_profile:
        decision["risk_payload_construction"] = "TP_ONLY_PROFILE_SL_TP_SUPPRESSED"
        decision["risk_payload_construction_reason"] = "TP_ONLY_PROFILE_ACTIVE; ORDERSEND_SL_SUPPRESSED_BY_PROFILE; fixed TP uses dashboard market close"
    elif built:
        decision["risk_payload_construction"] = "BUILT_BEFORE_VALIDATION"
        decision["risk_payload_construction_reason"] = f"intent={bias}; mode={mode}; built={','.join(built)}; entry={entry_price:.3f}"
    else:
        decision.setdefault("risk_payload_construction", "UNCHANGED_ALREADY_VALID" if sl > 0 and tp > 0 else "FAILED_NO_ENTRY_PRICE")
        if sl <= 0 or tp <= 0:
            decision["risk_payload_construction_reason"] = "missing positive entry_price/bid for SL/TP construction"

    if tp_only_profile or (sl > 0 and tp > 0):
        decision["risk_payload_valid_after_construction"] = True
        decision["payload_valid"] = True
        if str(decision.get("management", "")).upper() in ("", "NO_TRADE"):
            decision["management"] = "SCALP_TP"
            decision["mgmt"] = "SCALP_TP"
        decision.setdefault("entry_slot", safe_int(decision.get("slot", 1), 1) or 1)
        decision.setdefault("slot", safe_int(decision.get("entry_slot", 1), 1) or 1)
    else:
        decision["risk_payload_valid_after_construction"] = False

    return decision


def _build_wait_or_block_payload(source_data, reason, state_label, payload_reason, bias_hint="NEUTRAL", market_mode="UNKNOWN", bb_state="UNKNOWN"):
    """
    Create explicit non-trade output states while preserving lifecycle freshness.
    state_label: WAIT_VALID or INVALID_PAYLOAD_BLOCK
    """
    fallback = no_trade(reason, market_mode, bb_state)
    fallback["bias"] = bias_hint if bias_hint in ("BUY", "SELL") else "NEUTRAL"
    fallback["trend_bias"] = fallback["bias"]
    fallback["entry_allowed"] = False
    fallback["decision_output_state"] = state_label
    fallback["payload_validation_failed"] = state_label == "INVALID_PAYLOAD_BLOCK"
    fallback["payload_validation_reason"] = payload_reason
    fallback["payload_validation_source_decision"] = str(source_data.get("decision", "UNKNOWN")).upper()
    fallback["payload_validation_source_action"] = str(source_data.get("action", source_data.get("bias", "UNKNOWN"))).upper()
    fallback["payload_validation_source_management"] = str(source_data.get("management", source_data.get("mgmt", "UNKNOWN"))).upper()
    fallback["loop_duration_sec"] = safe_float(source_data.get("loop_duration_sec", 0), 0.0)
    fallback["total_cycle_time"] = safe_float(source_data.get("total_cycle_time", 0), 0.0)
    fallback["market_state_age_sec"] = safe_int(source_data.get("market_state_age_sec", source_data.get("_market_state_age_sec", -1)), -1)
    fallback["market_state_sequence_id"] = safe_int(source_data.get("market_state_sequence_id", source_data.get("sequence_id", 0)), 0)
    fallback["execution_state"] = "WAIT" if state_label == "WAIT_VALID" else "NO_TRADE"
    return fallback

def validate_final_decision_payload(data):
    """
    Final lightweight payload integrity gate before decision.json write.
    Never emits a corrupted TRADE packet.
    """
    if not isinstance(data, dict):
        return _build_wait_or_block_payload(
            {},
            "payload_validation_failed | payload_not_dict",
            "INVALID_PAYLOAD_BLOCK",
            "payload_not_dict"
        )

    symbol = str(data.get("symbol", "")).upper().strip()
    decision = str(data.get("decision", "")).upper().strip()
    action = str(data.get("action", data.get("bias", ""))).upper().strip()
    execution_state = str(data.get("execution_state", "")).upper().strip()
    management = str(data.get("management", data.get("mgmt", ""))).upper().strip()

    errors = []
    if symbol != SYMBOL:
        errors.append(f"symbol_invalid={symbol}")
    if action not in VALID_ACTIONS:
        errors.append(f"action_invalid={action}")
    if execution_state and execution_state not in VALID_EXECUTION_STATES:
        errors.append(f"execution_state_invalid={execution_state}")
    if management not in VALID_MANAGEMENT:
        errors.append(f"management_invalid={management}")

    if decision == "TRADE":
        sl = safe_float(data.get("sl", data.get("stop_loss", 0)), 0.0)
        tp = safe_float(data.get("tp", data.get("tp1", 0)), 0.0)
        data["sl"] = sl
        data["tp"] = tp
        data["stop_loss"] = round(sl, 3) if sl > 0 else 0
        data["tp1"] = round(tp, 3) if tp > 0 else 0

        active_profile = str(data.get("active_profile", data.get("dashboard_active_profile", ""))).upper().strip()
        dashboard_exit_mode = str(
            data.get(
                "dashboard_exit_mode",
                data.get("fixed_take_profit_close_mode", data.get("dashboard_fixed_take_profit_close_mode", ""))
            )
        ).upper().strip()
        fixed_take_profit = data.get("dashboard_fixed_take_profit", {})
        if isinstance(fixed_take_profit, dict) and not dashboard_exit_mode:
            dashboard_exit_mode = str(fixed_take_profit.get("close_mode", "")).upper().strip()

        broker_sl_required = _protection_bool(data.get("broker_sl_required", active_profile != "TP_ONLY_1USD_TEST"))
        broker_tp_required = _protection_bool(data.get("broker_tp_required", True))
        dashboard_tp_required = _protection_bool(data.get("dashboard_tp_required", broker_tp_required))
        profile_contract_status = str(data.get("profile_sl_suppression_check", "PROFILE_SL_SUPPRESSION_UNKNOWN")).upper().strip()
        skip_broker_sl_validation = _tp_only_sl_suppression_approved(data) or (not broker_sl_required and active_profile == "TP_ONLY_1USD_TEST")
        profile_contract_status = str(data.get("profile_sl_suppression_check", profile_contract_status)).upper().strip()
        skip_broker_tp_validation = (
            dashboard_exit_mode in ("MARKET_CLOSE", "IMMEDIATE_MARKET_CLOSE")
            or not dashboard_tp_required
        )

        print(
            "EXECUTOR_SL_VALIDATION_CONTRACT",
            f"decision={decision}",
            f"payload_valid={data.get('payload_valid')}",
            f"sl={sl}",
            f"broker_sl_required={broker_sl_required}",
            f"active_profile={active_profile}",
            f"profile_contract_status={profile_contract_status}",
        )

        exception_reasons = []
        if broker_sl_required:
            print("EXECUTOR_SL_REQUIRED_TRUE", f"active_profile={active_profile}", f"sl={sl}")

        if sl <= 0 and skip_broker_sl_validation:
            exception_reasons.append("broker_sl_validation_skipped")
            print(
                "EXECUTOR_SL_SUPPRESSION_APPROVED",
                f"reason=broker_sl_required_false_and_profile_contract_approved",
                f"broker_sl_required={broker_sl_required}",
                f"active_profile={active_profile}",
                f"payload_valid={data.get('payload_valid')}",
                f"profile_contract_status={profile_contract_status}",
            )
        elif sl <= 0:
            errors.append(f"sl_invalid={sl}")
            print(
                "EXECUTOR_SL_SUPPRESSION_REJECTED",
                f"reason=sl_zero_requires_broker_sl_or_unapproved_contract",
                f"broker_sl_required={broker_sl_required}",
                f"active_profile={active_profile}",
                f"payload_valid={data.get('payload_valid')}",
                f"profile_contract_status={profile_contract_status}",
            )

        if tp <= 0 and skip_broker_tp_validation:
            exception_reasons.append("broker_tp_validation_skipped")
        elif tp <= 0:
            errors.append(f"tp_invalid={tp}")

        if exception_reasons:
            data["payload_validation_profile_exception"] = "PAYLOAD_VALIDATION_PROFILE_EXCEPTION"
            data["payload_validation_exception_active_profile"] = active_profile
            data["payload_validation_exception_broker_sl_required"] = broker_sl_required
            data["payload_validation_exception_broker_tp_required"] = broker_tp_required
            data["payload_validation_exception_dashboard_exit_mode"] = dashboard_exit_mode
            data["payload_validation_exception_reason"] = ";".join(exception_reasons)
            print(
                "PAYLOAD_VALIDATION_PROFILE_EXCEPTION:"
                f" active_profile={active_profile}"
                f" broker_sl_required={broker_sl_required}"
                f" broker_tp_required={broker_tp_required}"
                f" dashboard_exit_mode={dashboard_exit_mode}"
                f" validation_exception_reason={data['payload_validation_exception_reason']}"
            )
            if active_profile == "TP_ONLY_1USD_TEST":
                data["tp_only_validation_exception_applied"] = True
                print("TP_ONLY_VALIDATION_EXCEPTION_APPLIED")

    if errors:
        if decision == "TRADE" and any(e.startswith("sl_invalid=") or e.startswith("tp_invalid=") for e in errors):
            bias_hint = action if action in ("BUY", "SELL") else "NEUTRAL"
            return _build_wait_or_block_payload(
                data,
                "payload_validation_wait_valid | " + "; ".join(errors),
                "WAIT_VALID",
                "; ".join(errors),
                bias_hint=bias_hint,
                market_mode=data.get("market_mode", "UNKNOWN"),
                bb_state=data.get("bb_state", "UNKNOWN")
            )
        return _build_wait_or_block_payload(
            data,
            "payload_validation_failed | " + "; ".join(errors),
            "INVALID_PAYLOAD_BLOCK",
            "; ".join(errors),
            bias_hint=action if action in ("BUY", "SELL") else "NEUTRAL",
            market_mode=data.get("market_mode", "UNKNOWN"),
            bb_state=data.get("bb_state", "UNKNOWN")
        )

    data["payload_validation_failed"] = False
    data["payload_validation_reason"] = ""
    data.setdefault("decision_output_state", "TRADE" if decision == "TRADE" else "NO_TRADE")
    return data

def attach_final_write_metadata(data, write_start):
    """Attach local freshness and publication audit fields before atomic replace."""
    if not isinstance(data, dict):
        return data

    now = time.time()
    write_duration = round(now - write_start, 6)
    data["write_target_path"] = str(OUTPUT_PATH)
    data["market_state_read_path"] = str(data.get("market_state_path") or FILE_PATH)
    data["final_output_state"] = str(
        data.get("decision_output_state")
        or data.get("execution_state")
        or data.get("decision")
        or "UNKNOWN"
    ).upper()
    data["ai_final_write_status"] = "SUCCESS"
    data["final_decision_build_sec"] = round(safe_float(
        data.get("final_decision_build_sec", data.get("loop_duration_sec", data.get("stale_prevention_timing_sec", 0.0))),
        0.0
    ), 6)
    data["decision_write_duration"] = write_duration
    total_cycle_time = safe_float(data.get("total_cycle_time", 0.0), 0.0)
    if total_cycle_time <= 0:
        total_cycle_time = safe_float(data.get("loop_duration_sec", 0.0), 0.0) + write_duration
    data["total_cycle_time"] = round(total_cycle_time, 6)
    data["file_write_latency"] = 0.0
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
    BASE_PATH.mkdir(parents=True, exist_ok=True)
    temp_path = OUTPUT_PATH.with_suffix(".tmp")

    write_start = time.time()
    for _ in range(5):
        try:
            with open(temp_path, "w", encoding="utf-8") as f:
                data = ensure_ea_v17_compat_fields(data)
                data = attach_v25_adaptive_style_fields(data)
                data = apply_spike_pullback_reentry_v25_6(data, data)
                data = apply_execution_quality_core_v26_5(data)
                data = align_management_with_trend_context(data)
                data = enforce_trend_management_v26_6(data)
                data = apply_v26_execution_confidence_engine(data)
                data = apply_execution_timing_layer_v26_6_5(data)
                data = apply_execution_quality_core_v26_5(data)
                data = align_management_with_trend_context(data)
                data = enforce_trend_management_v26_6(data)
                data = apply_early_participation_sizing_v26_6(data)
                data = apply_structure_aware_hold_intelligence_v25_5(data)
                data = apply_bb_smoothing_fields_to_decision_v25_4(data, data)
                data = apply_v25_3_rsi_soft_penalty_recovery(data)
                data = apply_final_decision_gate_trace_v25_2(data)
                data = apply_late_entry_guard_v26_6(data)
                data = initialize_final_decision_trace(data)
                _trace_before = dict(data)
                data = apply_exhaustion_protection_v26_6_6(data)
                data = record_final_decision_trace_stage(data, "exhaustion_protection", _trace_before)
                _trace_before = dict(data)
                data = apply_expectancy_entry_filters_v26_6_2(data)
                data = record_final_decision_trace_stage(data, "expectancy_entry_filter", _trace_before)
                _trace_before = dict(data)
                data = apply_session_loss_governor_v26_6_2(data)
                data = record_final_decision_trace_stage(data, "transition_gate", _trace_before)
                data = apply_expectancy_metrics_v26_6_6(data)
                _trace_before = dict(data)
                data = apply_protection_authority_manager_v26_6_1(data)
                data = record_final_decision_trace_stage(data, "protection_authority_manager", _trace_before)
                _trace_before = dict(data)
                data = apply_execution_timing_layer_v26_6_5(data)
                data = record_final_decision_trace_stage(data, "execution_timing_layer", _trace_before)
                _trace_before = dict(data)
                data = normalize_decision_schema_v20_2(data)
                data = record_final_decision_trace_stage(data, "schema_normalization", _trace_before)
                data = align_management_with_trend_context(data)
                data = enforce_trend_management_v26_6(data)
                data = apply_early_participation_sizing_v26_6(data)
                _trace_before = dict(data)
                data = apply_expectancy_entry_filters_v26_6_2(data)
                data = record_final_decision_trace_stage(data, "expectancy_entry_filter", _trace_before)
                _trace_before = dict(data)
                data = apply_session_loss_governor_v26_6_2(data)
                data = record_final_decision_trace_stage(data, "transition_gate", _trace_before)
                data = apply_expectancy_metrics_v26_6_6(data)
                data = apply_shadow_opposite_audit_v26_6_6(data)
                _trace_before = dict(data)
                data = construct_risk_payload_before_validation(data)
                data = record_final_decision_trace_stage(data, "risk_payload_construction", _trace_before)
                data = apply_loss_cap_and_profit_lock_v26_6_2(data)
                data = apply_exit_authority_manager_v26_6_4(data)
                data = enforce_expectancy_rr_structure(data)
                data = enforce_trend_management_v26_6(data)
                data = apply_max_realized_loss_guard_v26_6(data)
                _trace_before = dict(data)
                data = validate_final_decision_payload(data)
                data = record_final_decision_trace_stage(data, "payload_validation", _trace_before)
                _trace_before = dict(data)
                data = apply_executor_authority_contract_v26_6_1(data)
                data = record_final_decision_trace_stage(data, "executor_authority_contract", _trace_before)
                _trace_before = dict(data)
                data = apply_execution_timing_layer_v26_6_5(data)
                data = record_final_decision_trace_stage(data, "execution_timing_layer", _trace_before)
                _trace_before = dict(data)
                data = apply_protection_authority_manager_v26_6_1(data, allow_release=False, count_cycle=False)
                data = record_final_decision_trace_stage(data, "protection_authority_manager", _trace_before)
                _trace_before = dict(data)
                data = normalize_decision_schema_v20_2(data)
                data = record_final_decision_trace_stage(data, "schema_normalization", _trace_before)
                data = enforce_trend_management_v26_6(data)
                data = apply_early_participation_sizing_v26_6(data)
                data = apply_loss_cap_and_profit_lock_v26_6_2(data)
                data = apply_max_realized_loss_guard_v26_6(data)
                data = apply_exit_authority_manager_v26_6_4(data)
                _trace_before = dict(data)
                data = apply_executor_authority_contract_v26_6_1(data)
                data = record_final_decision_trace_stage(data, "executor_authority_contract", _trace_before)
                _trace_before = dict(data)
                data = enforce_risk_payload_invariant_before_publication(data)
                data = record_final_decision_trace_stage(data, "risk_payload_invariant", _trace_before)
                data = attach_no_trade_explainability(data)
                data = record_final_decision_trace_stage(data, "final_no_trade_explainability", data)
                data = attach_score_decomposition(data)
                if str(data.get("decision", "")).upper() == "TRADE":
                    data["final_veto_owner"] = "NONE"
                    data["effective_veto_code"] = "NONE"
                    data["final_veto_reason"] = ""
                data["runtime_branch"] = RUNTIME_BRANCH
                data["arch_version"] = ARCH_VERSION
                data["build_tag"] = BUILD_TAG
                data["runtime_signature"] = RUNTIME_SIGNATURE
                data = attach_final_write_metadata(data, write_start)
                data = record_final_decision_trace_stage(data, "final_publish", data)
                payload_text = json.dumps(data, indent=2)
                f.write(payload_text)
                f.flush()
                os.fsync(f.fileno())

            replace_start = time.time()
            os.replace(str(temp_path), str(OUTPUT_PATH))
            replace_latency = round(time.time() - replace_start, 6)
            total_write = round(time.time() - write_start, 6)

            if data.get("executor_order_send_required"):
                print(
                    "EXECUTOR_FINAL_GATE_PASS:",
                    "AI TRADE payload validated; broker safety owns final pre-send gate",
                )
                print(
                    "EXECUTOR AUTHORITY AUDIT:",
                    "TRADE decision emitted",
                    "| executor receives TRADE",
                    "| no legacy V15/V17 veto override allowed",
                    "| OrderSend required after broker safety checks",
                    "| allowed", data.get("allowed"),
                    "| payload_valid", data.get("payload_valid"),
                    "| raw_v17_quality", data.get("v17_quality_score_diagnostic"),
                    "| compat_quality", data.get("analysis_quality"),
                )

            print(data.get("dashboard_single_source_of_truth_status", "DASHBOARD_BYPASS_DETECTED"))
            print(
                "DECISION WRITTEN:", data.get("decision", ""),
                "|", data.get("entry_type", ""),
                "| mode", data.get("market_mode", ""),
                "| bb", data.get("bb_state", ""),
                "| mgmt", data.get("management", ""),
                "| slot", data.get("entry_slot", 0),
                "| write_sec", total_write,
                "| replace_sec", replace_latency,
                "| target", data.get("write_target_path", str(OUTPUT_PATH)),
                "| market", data.get("market_state_read_path", str(FILE_PATH)),
                "| status", data.get("ai_final_write_status", ""),
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
        "transition_wait_max_cycles": TRANSITION_WAIT_MAX_CYCLES,
        "transition_wait_released": False,
        "participation_release": False,
        "participation_release_reason": "",
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
        "pullback_state": "UNKNOWN",
        "pullback_quality": 0,
        "pullback_depth": "UNKNOWN",
        "pullback_depth_pct": 0,
        "continuation_return": False,
        "continuation_quality": 0,
        "entry_timing": "UNKNOWN",
        "runner_allowed": False,
        "pullback_reason": "",
        "heartbeat_unix": 0,
        "sequence_id": 0,
        "market_state_sequence_id": 0,
        "market_state_age_sec": -1,
        "decision_age_sec": 0,
        "time_sync_standard": TIME_SYNC_STANDARD,
        "entry_location_score_v26_5": 50,
        "entry_location_grade": "UNKNOWN",
        "entry_location_positive_factors": [],
        "entry_location_negative_factors": [],
        "entry_location_score_reason": "",
        "directional_idea_id": "",
        "execution_legs": [],
        "active_execution_leg": "NONE",
        "position_construction": "ONE_DIRECTIONAL_IDEA_SINGLE_LEG_COMPAT",
        "scale_policy": "SCALE_INTO_WINNERS_ONLY",
        "scale_into_winners_only": True,
        "martingale_allowed": False,
        "averaging_losers_allowed": False,
        "hedge_architecture_allowed": False,
        "profit_lock_ladder": V26_5_PROFIT_LOCK_LADDER_POINTS,
        "profit_extraction_structure": {},
        "planned_rr": 0.0,
        "minimum_required_rr": 0.0,
        "expectancy_structure_valid": False,
        "rr_enforcement": "NOT_EVALUATED",
        "rr_enforcement_reason": "",
        "entry_type": entry_type,
        "entry_slot": entry_slot,
        "market_mode": market_mode,
        "bb_state": bb_state,
        "management": management,
        "entry_price": round((sl + tp) / 2, 3) if sl > 0 and tp > 0 else 0,
        "price": round((sl + tp) / 2, 3) if sl > 0 and tp > 0 else 0,
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
        "transition_wait_max_cycles": TRANSITION_WAIT_MAX_CYCLES,
        "transition_wait_released": False,
        "participation_release": False,
        "participation_release_reason": "",
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
        "pullback_state": "UNKNOWN",
        "pullback_quality": 0,
        "pullback_depth": "UNKNOWN",
        "pullback_depth_pct": 0,
        "continuation_return": False,
        "continuation_quality": 0,
        "entry_timing": "UNKNOWN",
        "runner_allowed": False,
        "pullback_reason": "",
        "heartbeat_unix": 0,
        "sequence_id": 0,
        "market_state_sequence_id": 0,
        "market_state_age_sec": -1,
        "decision_age_sec": 0,
        "time_sync_standard": TIME_SYNC_STANDARD,
        "entry_location_score_v26_5": 50,
        "entry_location_grade": "UNKNOWN",
        "entry_location_positive_factors": [],
        "entry_location_negative_factors": [],
        "entry_location_score_reason": "",
        "directional_idea_id": "",
        "execution_legs": [],
        "active_execution_leg": "NONE",
        "position_construction": "ONE_DIRECTIONAL_IDEA_SINGLE_LEG_COMPAT",
        "scale_policy": "SCALE_INTO_WINNERS_ONLY",
        "scale_into_winners_only": True,
        "martingale_allowed": False,
        "averaging_losers_allowed": False,
        "hedge_architecture_allowed": False,
        "profit_lock_ladder": V26_5_PROFIT_LOCK_LADDER_POINTS,
        "profit_extraction_structure": {},
        "planned_rr": 0.0,
        "minimum_required_rr": 0.0,
        "expectancy_structure_valid": False,
        "rr_enforcement": "NOT_EVALUATED",
        "rr_enforcement_reason": "",
        "entry_type": "",
        "entry_slot": 0,
        "market_mode": market_mode,
        "bb_state": bb_state,
        "management": "NO_TRADE",
        "stop_loss": 0,
        "tp1": 0,
        "reason": reason,
        "no_trade_reason": "",
        "no_trade_reasons": [],
        "blocked_stage": "",
        "blocking_module": "",
        "confidence_score": 0,
        "required_score_gap": 0,
        "entry_window_state": "NOT_EVALUATED",
        "rsi_state": "NOT_EVALUATED",
        "macd_state": "NOT_EVALUATED",
        "countertrend_state": "NOT_EVALUATED",
        "exhaustion_state": "NOT_EVALUATED",
        "protection_state": "NOT_EVALUATED",
        "final_veto_reason": "",
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
        weak_trend_momentum = "weak trend momentum" in str(nova_reason).lower()
        bias = str(decision.get("bias", decision.get("action", "NEUTRAL"))).upper()
        score_gap = abs(safe_int(buy_score, 0) - safe_int(sell_score, 0))
        htf_aligned = str(market_mode).upper() in ("TREND", "TRANSITION", "SPIKE")
        dominance_valid = bias in ("BUY", "SELL") and score_gap >= 2
        payload_valid = bool(decision.get("schema_validation_ok", True))
        hard_block, _hard_reason = _v26_has_hard_block(decision)

        # V26.4.7 governance softening:
        # Weak trend momentum no longer hard-kills participation when direction/HTF/payload are valid.
        # Convert veto into a confidence penalty while preserving ACTION/MODE/BIAS.
        if V26_6_WEAK_MOMENTUM_PENALTY_ONLY and weak_trend_momentum and dominance_valid and htf_aligned and payload_valid and not hard_block:
            softened = dict(decision)
            softened["nova_brain"] = "SOFTENED"
            softened["nova_reason"] = nova_reason
            softened["momentum_governance_state"] = "SOFTENED_WEAK_MOMENTUM"
            softened["intended_action"] = bias
            softened["action"] = bias
            softened["bias"] = bias
            softened["buy_score"] = buy_score
            softened["sell_score"] = sell_score
            softened["buyScore"] = buy_score
            softened["sellScore"] = sell_score
            softened["score_gap"] = score_gap
            softened["runner_allowed"] = False
            softened["runner_disabled"] = True
            softened["runner_disable_reason"] = "weak momentum governance cautious mode"
            softened["runner_disable_source"] = "V26.4.7_WEAK_MOMENTUM_SOFTENING"
            softened["confidence_modifier"] = "WEAK_MOMENTUM_CONFIDENCE_PENALTY"
            base_confidence = safe_int(softened.get("confidence", 65), 65)
            softened["confidence_penalty"] = WEAK_MOMENTUM_CONFIDENCE_PENALTY
            softened["penalty_sources"] = list(softened.get("penalty_sources", [])) if isinstance(softened.get("penalty_sources", []), list) else []
            softened["penalty_sources"].append({
                "module": "NOVA_WEAK_MOMENTUM_GOVERNANCE",
                "penalty": WEAK_MOMENTUM_CONFIDENCE_PENALTY,
                "reason": nova_reason,
                "effective": True,
            })
            softened["confidence"] = max(0, base_confidence - WEAK_MOMENTUM_CONFIDENCE_PENALTY)
            softened["participation_restoration_rule"] = "weak momentum is a confidence penalty, not a hard veto"
            softened["weak_momentum_reform"] = "PENALTY_ONLY_V26_6"

            # Any valid directional gap now participates cautiously; weak momentum no longer erases authority.
            if score_gap >= WEAK_MOMENTUM_EXECUTE_MIN_GAP:
                softened["decision"] = "TRADE"
                softened["entry_allowed"] = True
                softened["management"] = "SCALP_TP"
                softened["mgmt"] = "SCALP_TP"
                softened["market_style"] = "SCALP"
                softened["execution_state"] = "EXECUTE_CAUTIOUS"
                softened["execution_confidence_floor"] = "V26.4.7_WEAK_MOMENTUM_CAUTIOUS"
                softened["reason"] = (str(softened.get("reason", "")) + f" | {nova_reason} -> confidence -{WEAK_MOMENTUM_CONFIDENCE_PENALTY}; EXECUTE_CAUTIOUS_SOFTENED").strip()
            else:
                softened["decision"] = "NO_TRADE"
                softened["entry_allowed"] = False
                softened["management"] = "NO_TRADE"
                softened["mgmt"] = "NO_TRADE"
                softened["execution_state"] = "WAIT"
                softened["wait_state"] = "WAIT_VALID"
                softened["wait_reason"] = "weak momentum; directional bias preserved for valid continuation"
                softened["wait_recovery_lifecycle"] = "ACTIVE"
                softened["wait_directional_memory"] = bias
                softened["next_trigger"] = "momentum recovery / confidence uplift / timing improves"
                softened["manual_action"] = f"{bias}_BIAS_WAIT_RECOVERY"
                softened["reason"] = (str(softened.get("reason", "")) + f" | {nova_reason} -> confidence -{WEAK_MOMENTUM_CONFIDENCE_PENALTY}; WAIT_VALID_DIRECTION_PRESERVED").strip()
            return softened

        ai_valid, ai_reason = _ai_authority_valid(decision, buy_score, sell_score)
        if ai_valid and dominance_valid and htf_aligned and payload_valid and not hard_block:
            softened = dict(decision)
            softened = add_confidence_penalty(softened, V26_LEGACY_ALIGNMENT_PENALTY, nova_reason)
            softened["nova_brain"] = "SOFTENED"
            softened["nova_reason"] = f"{nova_reason} | {ai_reason}; NOVA legacy veto converted to confidence penalty"
            softened["nova_legacy_veto"] = nova_reason
            softened["decision"] = "TRADE"
            softened["entry_allowed"] = True
            softened["action"] = bias
            softened["bias"] = bias
            softened["buy_score"] = buy_score
            softened["sell_score"] = sell_score
            softened["buyScore"] = buy_score
            softened["sellScore"] = sell_score
            softened["score_gap"] = score_gap
            softened["reason"] = (str(softened.get("reason", "")) + f" | NOVA_PENALTY_ONLY: {nova_reason}").strip()
            return softened

        blocked = no_trade(nova_reason, market_mode, bb_state)
        for key in (
            "buy_score", "sell_score", "score_gap", "dir_m15", "dir_m3",
            "rsi", "macd_hist", "bb_mid", "bb_upper2", "bb_lower2", "bid", "price", "entry_price", "bb_middle", "bb_upper", "bb_lower",
            "analysis_quality", "entry_allowed", "adaptive_gap", "learning_enabled", "learning_key",
            "learning_gap_adjust", "learning_note", "learning_stats", "bb_extreme",
            "entry_quality", "entry_quality_reason",
            "soft_lock_state", "soft_lock_direction", "soft_lock_allowed", "soft_lock_reason",
            "transition_decay_count", "transition_decay_required", "transition_decay_active", "transition_decay_reason",
            "transition_wait_max_cycles", "transition_wait_released", "participation_release", "participation_release_reason",
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


def build_score_decomposition(data, decision=None):
    """Telemetry: expose why score_gap is what it is without changing scoring."""
    source = decision if isinstance(decision, dict) else data
    buy_score = safe_int(source.get("buy_score", source.get("buyScore", 0)), 0)
    sell_score = safe_int(source.get("sell_score", source.get("sellScore", 0)), 0)
    if isinstance(data, dict):
        buy_score = safe_int(source.get("buy_score", source.get("buyScore", data.get("buy_score", data.get("buyScore", buy_score)))), buy_score)
        sell_score = safe_int(source.get("sell_score", source.get("sellScore", data.get("sell_score", data.get("sellScore", sell_score)))), sell_score)
    score_gap = abs(buy_score - sell_score)
    dominant_side = "BUY" if buy_score > sell_score else "SELL" if sell_score > buy_score else "FLAT"
    score_inputs = []
    if isinstance(data, dict):
        for key in sorted(data.keys()):
            lowered = str(key).lower()
            if lowered in ("buyscore", "sellscore", "buy_score", "sell_score", "score_gap"):
                continue
            if "score" in lowered:
                value = data.get(key)
                if isinstance(value, (int, float, str)):
                    score_inputs.append({"module": key, "value": value, "source": "market_state"})
    return {
        "buy_score": buy_score,
        "sell_score": sell_score,
        "score_gap": score_gap,
        "dominant_side": dominant_side,
        "score_contributions_by_module": [
            {"module": "market_state_buy_score", "side": "BUY", "contribution": buy_score},
            {"module": "market_state_sell_score", "side": "SELL", "contribution": sell_score},
        ],
        "additional_score_inputs": score_inputs,
        "raw_score_source": {
            "buyScore": safe_int(data.get("buyScore", 0), 0) if isinstance(data, dict) else buy_score,
            "sellScore": safe_int(data.get("sellScore", 0), 0) if isinstance(data, dict) else sell_score,
            "buy_score": safe_int(data.get("buy_score", 0), 0) if isinstance(data, dict) else buy_score,
            "sell_score": safe_int(data.get("sell_score", 0), 0) if isinstance(data, dict) else sell_score,
        },
        "gap_formula": "abs(buy_score - sell_score)",
        "gap_audit": f"score_gap={score_gap} from buy_score={buy_score}, sell_score={sell_score}",
    }


def attach_score_decomposition(decision, data=None):
    if not isinstance(decision, dict):
        return decision
    source = data if isinstance(data, dict) else decision
    decomposition = build_score_decomposition(source, decision)
    decision["score_decomposition"] = decomposition
    decision["score_gap_audit"] = decomposition["gap_audit"]
    decision["score_gap_source"] = "SCORE_DECOMPOSITION"
    return decision


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
        "pullback_state": decision.get("pullback_state", "UNKNOWN"),
        "pullback_quality": decision.get("pullback_quality", 0),
        "pullback_depth": decision.get("pullback_depth", "UNKNOWN"),
        "pullback_depth_pct": decision.get("pullback_depth_pct", 0),
        "continuation_return": decision.get("continuation_return", False),
        "continuation_quality": decision.get("continuation_quality", 0),
        "entry_timing": decision.get("entry_timing", "UNKNOWN"),
        "runner_allowed": decision.get("runner_allowed", False),
        "pullback_reason": decision.get("pullback_reason", ""),
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
    strong_gap_soft_confirm = score_gap >= STRONG_TRANSITION_NORMAL_SCORE_GAP

    if bias == "BUY":
        if rsi < TRANSITION_RSI_BUY_MIN and not strong_gap_soft_confirm:
            reasons.append(f"rsi_not_bullish:{rsi:.2f}<{TRANSITION_RSI_BUY_MIN}")
        elif rsi < TRANSITION_RSI_BUY_MIN and strong_gap_soft_confirm:
            reasons.append(f"rsi_soft_penalty_only:{rsi:.2f}<{TRANSITION_RSI_BUY_MIN};gap={score_gap}")
        if macd_hist < TRANSITION_MACD_BUY_MIN:
            reasons.append(f"macd_strongly_opposite:{macd_hist:.2f}<{TRANSITION_MACD_BUY_MIN}")
    elif bias == "SELL":
        if rsi > TRANSITION_RSI_SELL_MAX and not strong_gap_soft_confirm:
            reasons.append(f"rsi_not_bearish:{rsi:.2f}>{TRANSITION_RSI_SELL_MAX}")
        elif rsi > TRANSITION_RSI_SELL_MAX and strong_gap_soft_confirm:
            reasons.append(f"rsi_soft_penalty_only:{rsi:.2f}>{TRANSITION_RSI_SELL_MAX};gap={score_gap}")
        if macd_hist > TRANSITION_MACD_SELL_MAX:
            reasons.append(f"macd_strongly_opposite:{macd_hist:.2f}>{TRANSITION_MACD_SELL_MAX}")
    else:
        reasons.append("neutral_bias")

    # Near BB middle is allowed only if both RSI and MACD confirm the direction.
    if near_middle and not direction_ok and not strong_gap_soft_confirm:
        reasons.append("near_bb_middle_without_rsi_macd_confirm")

    hard_reasons = [r for r in reasons if not str(r).startswith("rsi_soft_penalty_only:")]
    return len(hard_reasons) == 0, reasons

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
    V25:
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
    V25.1 reset controller.
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
    V25 Transition Decay Logic V1.

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
            "transition_decay_ratio": 0.0,
            "transition_decay_reason": "recovery/reset: strong score or RSI/MACD recovered",
            **reset_info,
        }

    if not raw_weakening:
        transition_decay_state[key] = 0
        return False, {
            "transition_decay_count": 0,
            "transition_decay_required": required,
            "transition_decay_active": False,
            "transition_decay_ratio": 0.0,
            "transition_decay_reason": "not weakening",
            **reset_info,
        }

    count = transition_decay_state.get(key, 0) + 1
    transition_decay_state[key] = count

    if count > TRANSITION_WAIT_MAX_CYCLES:
        transition_wait_release_state[key] = count
        return False, {
            "transition_decay_count": count,
            "transition_decay_required": required,
            "transition_decay_active": False,
            "transition_decay_ratio": 1.0,
            "transition_wait_max_cycles": TRANSITION_WAIT_MAX_CYCLES,
            "transition_wait_released": True,
            "participation_release": True,
            "participation_release_reason": f"TRANSITION_WAIT cycles {count}>{TRANSITION_WAIT_MAX_CYCLES}; auto-release to cautious participation path",
            "transition_decay_reason": f"persistent weakening exceeded maximum {count}/{TRANSITION_WAIT_MAX_CYCLES}; release soft lock instead of perpetual suppression",
            **reset_info,
        }

    if count >= required:
        return True, {
            "transition_decay_count": count,
            "transition_decay_required": required,
            "transition_decay_active": True,
            "transition_decay_ratio": 1.0,
            "transition_wait_max_cycles": TRANSITION_WAIT_MAX_CYCLES,
            "transition_wait_released": False,
            "transition_decay_reason": f"persistent weakening count={count}/{required}; allow temporary TRANSITION_WAIT",
            **reset_info,
        }

    return False, {
        "transition_decay_count": count,
        "transition_decay_required": required,
        "transition_decay_active": True,
        "transition_decay_ratio": round(max(0.0, min(1.0, float(count) / float(required))), 3),
        "transition_wait_max_cycles": TRANSITION_WAIT_MAX_CYCLES,
        "transition_wait_released": False,
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
    V25 helper.
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
    V25 TREND WALK Override.
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
    V25 TREND NORMAL Continuation Override.

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

    softened = _soften_legacy_veto_if_ai_authority_valid(
        decision, reason, "CANDLE_INTELLIGENCE_BLOCK", V26_LEGACY_ALIGNMENT_PENALTY, buy_score, sell_score
    )
    if softened is not None:
        softened["candle_filter"] = "SOFTENED_TO_CONFIDENCE_PENALTY"
        softened["candle_reason"] = reason
        return softened

    blocked = no_trade(reason, market_mode, bb_state)
    for key in (
        "buy_score", "sell_score", "buyScore", "sellScore", "score_gap", "dir_m15", "dir_m3",
        "rsi", "macd_hist", "bb_mid", "bb_upper2", "bb_lower2", "bid", "price", "entry_price", "bb_middle", "bb_upper", "bb_lower",
        "analysis_quality", "adaptive_gap", "learning_enabled", "learning_key",
        "learning_gap_adjust", "learning_note", "learning_stats", "bb_extreme",
        "dual_mode", "aggressive_mode", "dual_mode_reason", "trend_priority", "trend_priority_reason",
        "soft_lock_state", "soft_lock_direction", "soft_lock_allowed", "soft_lock_reason",
            "transition_decay_count", "transition_decay_required", "transition_decay_active", "transition_decay_reason",
            "transition_wait_max_cycles", "transition_wait_released", "participation_release", "participation_release_reason",
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
    V25 TREND NORMAL Momentum Override.

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
    V25 Trend Exhaustion Detection.
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
        softened = _soften_legacy_veto_if_ai_authority_valid(
            decision, reason, "TREND_EXHAUSTION_BLOCK", V26_LEGACY_ALIGNMENT_PENALTY
        )
        if softened is not None:
            softened["trend_exhaustion_diagnostic_only"] = True
            return softened


        blocked = no_trade(reason, market_mode, bb_state)
        for key in (
            "buy_score", "sell_score", "buyScore", "sellScore", "score_gap",
            "rsi", "macd_hist", "bb_mid", "bb_upper2", "bb_lower2", "bid", "price", "entry_price", "bb_middle", "bb_upper", "bb_lower",
            "soft_lock_state", "soft_lock_direction", "soft_lock_allowed", "soft_lock_reason",
            "transition_decay_count", "transition_decay_required", "transition_decay_active", "transition_decay_reason",
            "transition_wait_max_cycles", "transition_wait_released", "participation_release", "participation_release_reason",
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
        softened = _soften_legacy_veto_if_ai_authority_valid(
            decision, reason, "MASTER_GATE_BLOCK", V26_LEGACY_ALIGNMENT_PENALTY
        )
        if softened is not None:
            softened["master_gate_diagnostic_only"] = True
            return softened

        blocked = no_trade(reason, market_mode, bb_state)
        for key in (
            "buy_score", "sell_score", "buyScore", "sellScore", "score_gap",
            "rsi", "macd_hist", "bb_mid", "bb_upper2", "bb_lower2", "bid", "price", "entry_price", "bb_middle", "bb_upper", "bb_lower",
            "soft_lock_state", "soft_lock_direction", "soft_lock_allowed", "soft_lock_reason",
            "transition_decay_count", "transition_decay_required", "transition_decay_active", "transition_decay_reason",
            "transition_wait_max_cycles", "transition_wait_released", "participation_release", "participation_release_reason",
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


def _pb_series(data, names, lookback=PULLBACK_LOOKBACK):
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


def get_pullback_candles(data, lookback=PULLBACK_LOOKBACK):
    opens = _pb_series(data, ["opens", "open"], lookback)
    highs = _pb_series(data, ["highs", "high"], lookback)
    lows = _pb_series(data, ["lows", "low"], lookback)
    closes = _pb_series(data, ["closes", "close"], lookback)
    if not opens:
        opens = closes[:]
    n = min(len(opens), len(highs), len(lows), len(closes), lookback)
    return opens[:n], highs[:n], lows[:n], closes[:n]


def _body_ratio(o, h, l, c):
    return abs(c - o) / max(h - l, 0.00001)


def _candle_dir(o, c):
    if c > o:
        return "BULL"
    if c < o:
        return "BEAR"
    return "DOJI"


def _trend_side(bias, o, c):
    d = _candle_dir(o, c)
    return (bias == "BUY" and d == "BULL") or (bias == "SELL" and d == "BEAR")


def _counter_side(bias, o, c):
    d = _candle_dir(o, c)
    return (bias == "BUY" and d == "BEAR") or (bias == "SELL" and d == "BULL")


def _rejection_for_bias(bias, o, h, l, c):
    rng = max(h - l, 0.00001)
    upper = h - max(o, c)
    lower = min(o, c) - l
    if bias == "BUY":
        return lower / rng
    if bias == "SELL":
        return upper / rng
    return 0.0


def compute_pullback_depth_pct(bias, bid, bb_upper, bb_middle, bb_lower, ma50):
    if bb_upper <= bb_lower or bb_upper <= 0 or bb_lower <= 0:
        return 0.0
    width = max(bb_upper - bb_lower, 0.00001)
    if bias == "BUY":
        depth = (bb_upper - bid) / width
        if ma50 > 0 and bid < ma50:
            depth += 0.15
    elif bias == "SELL":
        depth = (bid - bb_lower) / width
        if ma50 > 0 and bid > ma50:
            depth += 0.15
    else:
        depth = 0.0
    return round(clamp_float(depth, 0.0, 1.0), 3)


def classify_pullback_depth(depth_pct):
    if depth_pct <= PULLBACK_SHALLOW_DEPTH_PCT:
        return "SHALLOW"
    if depth_pct <= PULLBACK_MEDIUM_DEPTH_PCT:
        return "MEDIUM"
    if depth_pct <= PULLBACK_MAX_DEPTH_PCT:
        return "DEEP"
    return "TOO_DEEP"


def detect_recent_expansion_chase(bias, opens, highs, lows, closes):
    if len(closes) < 4:
        return False, 0
    count = 0
    for o, h, l, c in zip(opens[:4], highs[:4], lows[:4], closes[:4]):
        if _trend_side(bias, o, c) and _body_ratio(o, h, l, c) >= PULLBACK_EXPANSION_BODY_RATIO:
            count += 1
    return count >= PULLBACK_EXPANSION_COUNT_BLOCK, count


def evaluate_pullback_quality(bias, data, market_mode, bb_state, bb_extreme, buy_score, sell_score):
    bid = safe_float(data.get("bid", 0), 0)
    ma50 = safe_float(data.get("ma50", 0), 0)
    rsi = safe_float(data.get("rsi", 50), 50)
    macd_hist = safe_float(data.get("macd_hist", 0), 0)
    bb_upper = safe_float(data.get("bb_upper", data.get("bb_upper2", 0)), 0)
    bb_middle = safe_float(data.get("bb_middle", data.get("bb_mid", 0)), 0)
    bb_lower = safe_float(data.get("bb_lower", data.get("bb_lower2", 0)), 0)

    opens, highs, lows, closes = get_pullback_candles(data)
    depth_pct = compute_pullback_depth_pct(bias, bid, bb_upper, bb_middle, bb_lower, ma50)
    depth = classify_pullback_depth(depth_pct)

    if len(closes) < 4:
        return {"pullback_state": "INSUFFICIENT_DATA", "pullback_quality": 0, "pullback_depth": depth, "pullback_depth_pct": depth_pct, "pullback_reason": "not enough candle history"}

    score = 0
    reasons = []
    score_gap = abs(buy_score - sell_score)
    counter_count = sum(1 for o, c in zip(opens[:4], closes[:4]) if _counter_side(bias, o, c))
    trend_count = sum(1 for o, c in zip(opens[:4], closes[:4]) if _trend_side(bias, o, c))
    avg_body = sum(_body_ratio(o, h, l, c) for o, h, l, c in zip(opens[:4], highs[:4], lows[:4], closes[:4])) / 4.0

    if market_mode == "TREND":
        score += 15; reasons.append("trend mode")
    if bb_state in ("NORMAL", "WALK_UP", "WALK_DOWN"):
        score += 10; reasons.append(f"bb={bb_state}")
    if depth == "SHALLOW":
        score += 22; reasons.append("shallow pullback")
    elif depth == "MEDIUM":
        score += 18; reasons.append("medium pullback")
    elif depth == "DEEP":
        score += 6; reasons.append("deep pullback")
    else:
        score -= 25; reasons.append("pullback too deep")

    if bias == "BUY":
        if rsi >= 50:
            score += 12; reasons.append("RSI above 50")
        else:
            score -= 15; reasons.append("RSI lost 50")
        if macd_hist >= -0.35:
            score += 12; reasons.append("MACD not collapsed")
        else:
            score -= 15; reasons.append("MACD collapse")
        if buy_score >= sell_score:
            score += 10; reasons.append("score supports BUY")
        if bb_extreme == "DEV4_UPPER":
            score -= 25; reasons.append("DEV4 upper late")
    elif bias == "SELL":
        if rsi <= 50:
            score += 12; reasons.append("RSI below 50")
        else:
            score -= 15; reasons.append("RSI lost SELL side")
        if macd_hist <= 0.35:
            score += 12; reasons.append("MACD not reversed")
        else:
            score -= 15; reasons.append("MACD reversed")
        if sell_score >= buy_score:
            score += 10; reasons.append("score supports SELL")
        if bb_extreme == "DEV4_LOWER":
            score -= 25; reasons.append("DEV4 lower late")

    if counter_count >= 1 and avg_body <= 0.55:
        score += 10; reasons.append("controlled counter candles")
    if trend_count >= 3:
        score -= 12; reasons.append("possible expansion chase")
    score += min(score_gap, 5) * 2

    score = clamp_int(score, 0, 100)
    state = "HEALTHY_PULLBACK" if score >= PULLBACK_MIN_QUALITY and depth != "TOO_DEEP" else "WEAK_PULLBACK"
    return {"pullback_state": state, "pullback_quality": score, "pullback_depth": depth, "pullback_depth_pct": depth_pct, "pullback_reason": "; ".join(reasons)}


def detect_continuation_return(bias, data):
    opens, highs, lows, closes = get_pullback_candles(data)
    rsi = safe_float(data.get("rsi", 50), 50)
    macd_hist = safe_float(data.get("macd_hist", 0), 0)
    if len(closes) < 3:
        return False, 0, "insufficient candle history"

    o1, h1, l1, c1 = opens[0], highs[0], lows[0], closes[0]
    o2, h2, l2, c2 = opens[1], highs[1], lows[1], closes[1]
    quality = 0
    reasons = []
    body = _body_ratio(o1, h1, l1, c1)
    rejection = _rejection_for_bias(bias, o1, h1, l1, c1)

    if _trend_side(bias, o1, c1):
        quality += 20; reasons.append("trend-side candle")
    if body >= PULLBACK_MOMENTUM_BODY_RATIO:
        quality += 18; reasons.append("momentum body")
    if rejection >= PULLBACK_REJECTION_WICK_RATIO:
        quality += 18; reasons.append("rejection wick")

    if bias == "BUY":
        if c1 > h2:
            quality += 18; reasons.append("close > previous high")
        if rsi >= 52:
            quality += 10; reasons.append("RSI recovery")
        if macd_hist >= -0.10:
            quality += 12; reasons.append("MACD recovery")
        if c1 > o2 and o1 <= c2:
            quality += 12; reasons.append("bullish engulf-like")
    elif bias == "SELL":
        if c1 < l2:
            quality += 18; reasons.append("close < previous low")
        if rsi <= 48:
            quality += 10; reasons.append("RSI recovery sell")
        if macd_hist <= 0.10:
            quality += 12; reasons.append("MACD recovery sell")
        if c1 < o2 and o1 >= c2:
            quality += 12; reasons.append("bearish engulf-like")

    quality = clamp_int(quality, 0, 100)
    return quality >= PULLBACK_CONTINUATION_MIN_QUALITY, quality, "; ".join(reasons) if reasons else "no continuation return"



def has_enough_pullback_candle_history(data, min_bars=PULLBACK_MIN_CANDLE_HISTORY):
    opens, highs, lows, closes = get_pullback_candles(data)
    n = min(len(opens), len(highs), len(lows), len(closes))
    return n >= min_bars, n

def pullback_continuation_engine(decision, data, market_mode, bb_state, bb_extreme, buy_score, sell_score):
    if not PULLBACK_ENGINE_ENABLED:
        return True, {"pullback_state": "DISABLED", "pullback_quality": 0, "pullback_depth": "UNKNOWN", "pullback_depth_pct": 0, "continuation_return": False, "continuation_quality": 0, "entry_timing": "DISABLED", "runner_allowed": False, "pullback_reason": "disabled"}

    if not isinstance(decision, dict) or decision.get("decision") != "TRADE":
        return True, {"pullback_state": "REPORT_ONLY", "pullback_quality": 0, "pullback_depth": "UNKNOWN", "pullback_depth_pct": 0, "continuation_return": False, "continuation_quality": 0, "entry_timing": "NO_TRADE", "runner_allowed": False, "pullback_reason": "not trade decision"}

    bias = str(decision.get("bias", "NEUTRAL")).upper()

    # V25 Fallback Mode:
    # If market_state.json has no candle history, do not block trade.
    # Keep diagnostic fields and allow existing V23/V24 logic to continue.
    enough_candles, candle_count = has_enough_pullback_candle_history(data)
    if not enough_candles and PULLBACK_FALLBACK_ALLOW_IF_NO_CANDLES:
        return True, {
            "pullback_state": "INSUFFICIENT_DATA",
            "pullback_quality": 0,
            "pullback_depth": "UNKNOWN",
            "pullback_depth_pct": 0,
            "continuation_return": False,
            "continuation_quality": 0,
            "entry_timing": "FALLBACK_LEGACY_LOGIC",
            "runner_allowed": False,
            "pullback_reason": f"insufficient candle history count={candle_count}; fallback allows legacy logic",
        }

    pb = evaluate_pullback_quality(bias, data, market_mode, bb_state, bb_extreme, buy_score, sell_score)
    cont_ok, cont_quality, cont_reason = detect_continuation_return(bias, data)
    opens, highs, lows, closes = get_pullback_candles(data)
    chase_risk, expansion_count = detect_recent_expansion_chase(bias, opens, highs, lows, closes)

    pb["continuation_return"] = bool(cont_ok)
    pb["continuation_quality"] = cont_quality
    pb["runner_allowed"] = bool(pb.get("pullback_quality", 0) >= PULLBACK_ALLOW_RUNNER_QUALITY and cont_ok and not chase_risk and pb.get("pullback_depth") in ("SHALLOW", "MEDIUM"))

    reasons = [pb.get("pullback_reason", ""), f"continuation={cont_reason}"]

    if chase_risk and PULLBACK_BLOCK_LATE_EXPANSION:
        pb["entry_timing"] = "LATE_EXPANSION"
        reasons.append(f"expansion_count={expansion_count}")
        pb["pullback_reason"] = "; ".join([r for r in reasons if r])
        return False, pb

    if pb.get("pullback_state") != "HEALTHY_PULLBACK":
        pb["entry_timing"] = "WAIT_PULLBACK"
        pb["pullback_reason"] = "; ".join([r for r in reasons if r])
        return False, pb

    if not cont_ok:
        pb["entry_timing"] = "WAIT_CONTINUATION_RETURN"
        pb["pullback_reason"] = "; ".join([r for r in reasons if r])
        return False, pb

    pb["entry_timing"] = "EARLY_CONTINUATION"
    pb["pullback_reason"] = "; ".join([r for r in reasons if r])
    return True, pb


def apply_pullback_continuation_or_block(decision, data, market_mode, bb_state, bb_extreme, buy_score, sell_score):
    ok, info = pullback_continuation_engine(decision, data, market_mode, bb_state, bb_extreme, buy_score, sell_score)
    if isinstance(decision, dict):
        decision.update(info)

    if not isinstance(decision, dict) or decision.get("decision") != "TRADE":
        return decision

    if not ok:
        reason = f"PULLBACK BLOCK | timing={info.get('entry_timing')} quality={info.get('pullback_quality')} cont={info.get('continuation_quality')} | {info.get('pullback_reason')}"
        softened = _soften_legacy_veto_if_ai_authority_valid(
            decision, reason, "PULLBACK_BLOCK", V26_LEGACY_ALIGNMENT_PENALTY, buy_score, sell_score
        )
        if softened is not None:
            softened["pullback_block_diagnostic_only"] = True
            return softened

        blocked = no_trade(reason, market_mode, bb_state)
        for key in (
            "buy_score", "sell_score", "buyScore", "sellScore", "score_gap",
            "rsi", "macd_hist", "bb_mid", "bb_upper2", "bb_lower2", "bid", "price", "entry_price", "bb_middle", "bb_upper", "bb_lower",
            "soft_lock_state", "soft_lock_direction", "soft_lock_allowed", "soft_lock_reason",
            "transition_decay_count", "transition_decay_required", "transition_decay_active", "transition_decay_reason",
            "transition_wait_max_cycles", "transition_wait_released", "participation_release", "participation_release_reason",
            "fresh_state_reset", "fresh_state_reset_reason", "market_state_fresh", "market_state_signature",
            "candle_trend", "structure_trend", "momentum_shape", "wick_rejection",
            "exhaustion_risk", "trend_quality", "candle_filter", "candle_reason",
            "trend_exhaustion", "trend_exhaustion_score", "trend_exhaustion_reason", "late_continuation_risk",
            "market_structure", "structure_signal", "bos_signal", "choch_signal", "liquidity_sweep",
            "distribution_phase", "accumulation_phase", "momentum_decay",
            "master_gate_score", "master_gate", "master_gate_reason",
            "pullback_state", "pullback_quality", "pullback_depth", "pullback_depth_pct",
            "continuation_return", "continuation_quality", "entry_timing", "runner_allowed", "pullback_reason",
            "market_state_path", "market_state_modified_time", "market_state_age_sec", "market_state_read_signature",
        ):
            if key in decision:
                blocked[key] = decision[key]
        blocked["entry_allowed"] = False
        return blocked

    if decision.get("decision") == "TRADE":
        decision["reason"] = f"{decision.get('reason','')} | V24 PULLBACK OK timing={info.get('entry_timing')} quality={info.get('pullback_quality')}"
    return decision



def _sr_num(v):
    return safe_float(v, 0.0)

def _sr_collect(data, names):
    vals = []
    for name in names:
        v = data.get(name)
        if isinstance(v, list):
            for x in v:
                fx = safe_float(x, 0)
                if fx > 0:
                    vals.append(fx)
        else:
            fx = safe_float(v, 0)
            if fx > 0:
                vals.append(fx)
    return vals

def collect_sr_levels_v24(data):
    supports = _sr_collect(data, ["support","support1","support2","local_support","m15_support","m3_support","h1_support","h4_support","swing_low","recent_low","low1","low2","low3"])
    resistances = _sr_collect(data, ["resistance","resistance1","resistance2","local_resistance","m15_resistance","m3_resistance","h1_resistance","h4_resistance","swing_high","recent_high","high1","high2","high3"])
    bb_upper = safe_float(data.get("bb_upper", data.get("bb_upper2", 0)), 0)
    bb_mid = safe_float(data.get("bb_middle", data.get("bb_mid", 0)), 0)
    bb_lower = safe_float(data.get("bb_lower", data.get("bb_lower2", 0)), 0)
    ma50 = safe_float(data.get("ma50", 0), 0)
    ma90 = safe_float(data.get("ma90", 0), 0)
    ma200 = safe_float(data.get("ma200", 0), 0)
    for x in [bb_lower, bb_mid, ma50, ma90, ma200]:
        if x > 0:
            supports.append(x)
    for x in [bb_upper, bb_mid, ma50, ma90, ma200]:
        if x > 0:
            resistances.append(x)
    return supports, resistances

def nearest_sr_v24(bid, supports, resistances):
    bid = safe_float(bid, 0)
    below = [x for x in supports if x <= bid]
    above = [x for x in resistances if x >= bid]
    ns = max(below) if below else (min(supports, key=lambda x: abs(x-bid)) if supports else 0)
    nr = min(above) if above else (min(resistances, key=lambda x: abs(x-bid)) if resistances else 0)
    return ns, nr

def estimate_entry_location_v24(decision, data, market_mode, bb_state, bb_extreme):
    bias = str(decision.get("bias", decision.get("action", "NEUTRAL"))).upper()
    bid = safe_float(data.get("bid", 0), 0)
    ma50 = safe_float(data.get("ma50", 0), 0)
    bb_mid = safe_float(data.get("bb_middle", data.get("bb_mid", decision.get("bb_mid", 0))), 0)
    bb_upper = safe_float(data.get("bb_upper", decision.get("bb_upper2", 0)), 0)
    bb_lower = safe_float(data.get("bb_lower", decision.get("bb_lower2", 0)), 0)
    supports, resistances = collect_sr_levels_v24(data)
    ns, nr = nearest_sr_v24(bid, supports, resistances)
    ds = abs(bid - ns) if ns > 0 else 0
    dr = abs(nr - bid) if nr > 0 else 0
    dma50 = abs(bid - ma50) if ma50 > 0 else 0
    dbb = abs(bid - bb_mid) if bb_mid > 0 else 0
    width = max(bb_upper - bb_lower, 0.00001) if bb_upper > 0 and bb_lower > 0 else 0.00001
    ext_score = clamp_int(int((dbb / width) * 100), 0, 100)
    score = 65
    reasons = []
    if bias == "BUY":
        reward = dr if nr > bid else 0
        if nr > 0 and dr <= SR_DANGER_LEVEL_POINTS:
            score -= 35; reasons.append(f"BUY near resistance {dr:.2f}")
        elif nr > 0 and dr <= SR_NEAR_LEVEL_POINTS:
            score -= 20; reasons.append(f"BUY close resistance {dr:.2f}")
        if ns > 0 and ds <= SR_NEAR_LEVEL_POINTS:
            score += 12; reasons.append(f"BUY near support {ds:.2f}")
    elif bias == "SELL":
        reward = ds if ns < bid else 0
        if ns > 0 and ds <= SR_DANGER_LEVEL_POINTS:
            score -= 35; reasons.append(f"SELL near support {ds:.2f}")
        elif ns > 0 and ds <= SR_NEAR_LEVEL_POINTS:
            score -= 20; reasons.append(f"SELL close support {ds:.2f}")
        if nr > 0 and dr <= SR_NEAR_LEVEL_POINTS:
            score += 12; reasons.append(f"SELL near resistance {dr:.2f}")
    else:
        reward = 0
        reasons.append("neutral bias")
    if ext_score >= 70:
        score -= 20; reasons.append(f"price extended {ext_score}")
    elif ext_score <= 35:
        score += 6; reasons.append(f"price reset {ext_score}")
    sl = safe_float(decision.get("sl", 0), 0)
    risk = abs(bid - sl) if sl > 0 and bid > 0 else DEFAULT_RISK_POINTS
    rr = reward / max(risk, 0.00001)
    if reward <= REMAINING_REWARD_LOW_POINTS:
        score -= 20; reasons.append(f"remaining reward low {reward:.2f}")
    if rr < SR_MIN_REWARD_RISK_RATIO:
        score -= 25; reasons.append(f"RR weak {rr:.2f}")
    score = clamp_int(score, 0, 100)
    state = "GOOD_LOCATION" if score >= 60 else "WEAK_LOCATION" if score >= ENTRY_LOCATION_BLOCK_SCORE else "BAD_LOCATION"
    return {
        "nearest_support": round(ns,3), "nearest_resistance": round(nr,3),
        "distance_to_nearest_support": round(ds,3), "distance_to_nearest_resistance": round(dr,3),
        "distance_from_ma50": round(dma50,3), "distance_from_bb_mid": round(dbb,3),
        "price_extension_score": ext_score, "entry_location_score": score,
        "remaining_reward_estimate": round(reward,3), "estimated_risk_points": round(risk,3),
        "estimated_reward_risk": round(rr,3), "entry_location_state": state,
        "entry_location_reason": "; ".join(reasons) if reasons else "entry location acceptable",
        "support_resistance_reason": f"support={ns:.3f} resistance={nr:.3f}",
    }

def apply_sr_entry_location_intelligence_v24(decision, data, market_mode, bb_state, bb_extreme):
    if not SR_ENTRY_LOCATION_ENABLED or not isinstance(decision, dict) or decision.get("decision") != "TRADE":
        return decision
    info = estimate_entry_location_v24(decision, data, market_mode, bb_state, bb_extreme)
    decision.update(info)
    should_block = (
        info["entry_location_score"] < ENTRY_LOCATION_BLOCK_SCORE
        or (
            not TEMP_RELAX_SR_RR_BLOCK
            and (
                info["estimated_reward_risk"] < SR_MIN_REWARD_RISK_RATIO
                or info["remaining_reward_estimate"] <= REMAINING_REWARD_LOW_POINTS
            )
        )
    )
    if should_block and not SR_REPORT_MODE_ONLY:
        reason = f"SR_ENTRY_LOCATION_BLOCK | state={info['entry_location_state']} score={info['entry_location_score']} RR={info['estimated_reward_risk']} reward={info['remaining_reward_estimate']} | {info['entry_location_reason']} | {info['support_resistance_reason']}"
        softened = _soften_legacy_veto_if_ai_authority_valid(
            decision, reason, "SR_ENTRY_LOCATION_BLOCK", V26_5_ENTRY_LOCATION_WEAK_PENALTY
        )
        if softened is not None:
            softened["sr_entry_location_diagnostic_only"] = True
            softened["execution_timing_reason"] = reason
            return softened

        blocked = no_trade(reason, market_mode, bb_state)
        blocked.update(decision)
        blocked["decision"] = "NO_TRADE"
        blocked["entry_allowed"] = False
        blocked["execution_timing_reason"] = reason
        return blocked
    decision["execution_timing_reason"] = f"{decision.get('execution_timing_reason','')} | SR_LOCATION_OK score={info['entry_location_score']} RR={info['estimated_reward_risk']}"
    return decision

def _eti_bias(decision):
    return str(decision.get("bias", decision.get("action", "NEUTRAL"))).upper()

def _eti_pct_distance(a, b):
    a = safe_float(a, 0.0)
    b = safe_float(b, 0.0)
    return 0.0 if b <= 0 else abs(a - b) / b

def _eti_bb_mid_ratio(bid, upper, mid, lower):
    width = max(safe_float(upper, 0) - safe_float(lower, 0), 0.00001)
    return abs(safe_float(bid, 0) - safe_float(mid, 0)) / width

def _eti_bb_edge_pos(bias, bid, upper, lower):
    width = max(safe_float(upper, 0) - safe_float(lower, 0), 0.00001)
    if bias == "BUY":
        return (safe_float(bid, 0) - safe_float(lower, 0)) / width
    if bias == "SELL":
        return (safe_float(upper, 0) - safe_float(bid, 0)) / width
    return 0.5

def detect_late_entry_v24(decision, data, market_mode, bb_state, bb_extreme):
    bias = _eti_bias(decision)
    bid = safe_float(data.get("bid", 0), 0)
    ma50 = safe_float(data.get("ma50", 0), 0)
    rsi = safe_float(data.get("rsi", decision.get("rsi", 50)), 50)
    macd = safe_float(data.get("macd_hist", decision.get("macd_hist", 0)), 0)
    upper = safe_float(data.get("bb_upper", decision.get("bb_upper2", 0)), 0)
    mid = safe_float(data.get("bb_middle", data.get("bb_mid", decision.get("bb_mid", 0))), 0)
    lower = safe_float(data.get("bb_lower", decision.get("bb_lower2", 0)), 0)
    score = 0
    reasons = []
    dist_ma50 = _eti_pct_distance(bid, ma50)
    dist_mid = _eti_bb_mid_ratio(bid, upper, mid, lower)
    edge = _eti_bb_edge_pos(bias, bid, upper, lower)
    if dist_ma50 >= DIST_MA50_EXTREME_PCT:
        score += 20; reasons.append(f"far MA50={dist_ma50:.4f}")
    if dist_mid >= DIST_BB_MID_EXTREME_RATIO:
        score += 20; reasons.append(f"far BB mid={dist_mid:.2f}")
    if edge >= VERTICAL_BB_EDGE_RATIO:
        score += 20; reasons.append(f"near BB edge={edge:.2f}")
    if bb_extreme in ("DEV4_UPPER", "DEV4_LOWER"):
        score += 25; reasons.append(f"DEV4={bb_extreme}")
    if bias == "BUY" and rsi >= 68:
        score += 15; reasons.append(f"BUY RSI high={rsi:.1f}")
    if bias == "SELL" and rsi <= 32:
        score += 15; reasons.append(f"SELL RSI low={rsi:.1f}")
    if bias == "BUY" and 0 < macd <= MACD_DECAY_ABS_WEAK:
        score += 15; reasons.append(f"BUY weak MACD={macd:.2f}")
    if bias == "SELL" and -MACD_DECAY_ABS_WEAK <= macd < 0:
        score += 15; reasons.append(f"SELL weak MACD={macd:.2f}")
    score = clamp_int(score, 0, 100)
    risk = "HIGH" if score >= LATE_ENTRY_BLOCK_SCORE else "MEDIUM" if score >= 50 else "LOW"
    state = "LATE_CONTINUATION" if risk == "HIGH" else "CAUTION_CONTINUATION" if risk == "MEDIUM" else "HEALTHY_CONTINUATION"
    return {"execution_timing_state": state, "late_entry_score": score, "late_entry_risk": risk, "late_entry_reason": "; ".join(reasons) if reasons else "late risk low"}

def detect_exhaustion_v24(decision, data, market_mode, bb_state, bb_extreme):
    bias = _eti_bias(decision)
    rsi = safe_float(data.get("rsi", decision.get("rsi", 50)), 50)
    macd = safe_float(data.get("macd_hist", decision.get("macd_hist", 0)), 0)
    wick = str(decision.get("wick_rejection", "NONE")).upper()
    existing = safe_int(decision.get("trend_exhaustion_score", 0), 0)
    score = 0
    reasons = []
    if bb_extreme in ("DEV4_UPPER", "DEV4_LOWER"):
        score += 30; reasons.append(f"BB DEV4 {bb_extreme}")
    if bias == "BUY" and rsi >= RSI_BUY_BLOWOFF:
        score += 25; reasons.append(f"RSI blowoff BUY={rsi:.1f}")
    if bias == "SELL" and rsi <= RSI_SELL_BLOWOFF:
        score += 25; reasons.append(f"RSI blowoff SELL={rsi:.1f}")
    if (bias == "BUY" and wick == "UPPER_REJECTION") or (bias == "SELL" and wick == "LOWER_REJECTION"):
        score += 20; reasons.append(f"wick rejection against {bias}")
    if existing >= 50:
        score += min(30, int(existing / 2)); reasons.append(f"existing exhaustion={existing}")
    if bias == "BUY" and macd < MACD_DECAY_ABS_WEAK:
        score += 15; reasons.append(f"BUY momentum weak={macd:.2f}")
    if bias == "SELL" and macd > -MACD_DECAY_ABS_WEAK:
        score += 15; reasons.append(f"SELL momentum weak={macd:.2f}")
    score = clamp_int(score, 0, 100)
    state = "HIGH" if score >= EXHAUSTION_BLOCK_SCORE else "MEDIUM" if score >= 55 else "LOW"
    return {"exhaustion_score": score, "exhaustion_state": state, "exhaustion_reason": "; ".join(reasons) if reasons else "exhaustion low"}

def apply_execution_timing_intelligence_v24(decision, data, market_mode, bb_state, bb_extreme):
    if not EXEC_TIMING_ENABLED or not isinstance(decision, dict) or decision.get("decision") != "TRADE":
        return decision
    now_ts = int(time.time())
    late = detect_late_entry_v24(decision, data, market_mode, bb_state, bb_extreme)
    exh = detect_exhaustion_v24(decision, data, market_mode, bb_state, bb_extreme)
    decision.update(late); decision.update(exh)
    if DISABLE_RUNNER_TEMPORARILY and str(decision.get("management", "")).upper() == "HOLD_TRAIL":
        decision["runner_disabled"] = True
        decision["runner_disable_reason"] = "runner temporarily disabled during execution timing stabilization"
        decision["management"] = "SCALP_TP"
        decision["mgmt"] = "SCALP_TP"
        decision["reason"] = f"{decision.get('reason','')} | RUNNER_DISABLED_TEMP"
    cooldown_until = safe_int(execution_timing_state.get("cooldown_until", 0), 0)
    if cooldown_until > now_ts:
        remain = cooldown_until - now_ts
        reason = f"EXHAUSTION_COOLDOWN_ACTIVE | remain={remain}s | {execution_timing_state.get('cooldown_reason','')}"
        softened = _soften_legacy_veto_if_ai_authority_valid(
            decision, reason, "EXHAUSTION_COOLDOWN_ACTIVE", V26_LEGACY_ALIGNMENT_PENALTY
        )
        if softened is not None:
            softened["exhaustion_cooldown_diagnostic_only"] = True
            softened["exhaustion_cooldown_reason"] = reason
            return softened

        blocked = no_trade(reason, market_mode, bb_state)
        blocked.update(decision)
        blocked["decision"] = "NO_TRADE"; blocked["entry_allowed"] = False
        blocked["exhaustion_cooldown_active"] = True
        blocked["exhaustion_cooldown_reason"] = execution_timing_state.get("cooldown_reason", "")
        return blocked
    should_block = late["late_entry_score"] >= LATE_ENTRY_BLOCK_SCORE or exh["exhaustion_score"] >= EXHAUSTION_BLOCK_SCORE
    if should_block:
        reason = f"EXECUTION_TIMING_BLOCK | late={late['late_entry_score']} {late['late_entry_risk']} | exhaustion={exh['exhaustion_score']} {exh['exhaustion_state']} | {late['late_entry_reason']} | {exh['exhaustion_reason']}"
        softened = _soften_legacy_veto_if_ai_authority_valid(
            decision, reason, "EXECUTION_TIMING_BLOCK", V26_LEGACY_ALIGNMENT_PENALTY
        )
        if softened is not None:
            softened["execution_timing_block_diagnostic_only"] = True
            softened["execution_timing_reason"] = reason
            return softened

        execution_timing_state["cooldown_until"] = now_ts + EXHAUSTION_COOLDOWN_SECONDS
        execution_timing_state["cooldown_reason"] = reason
        blocked = no_trade(reason, market_mode, bb_state)
        blocked.update(decision)
        blocked["decision"] = "NO_TRADE"; blocked["entry_allowed"] = False
        blocked["exhaustion_cooldown_active"] = True
        blocked["exhaustion_cooldown_reason"] = reason
        return blocked
    bias = _eti_bias(decision)
    last_ts = safe_int(execution_timing_state.get("last_continuation_entry_ts", 0), 0)
    last_bias = str(execution_timing_state.get("last_bias", "NEUTRAL")).upper()
    if last_ts > 0 and last_bias == bias and now_ts - last_ts < CONTINUATION_REENTRY_COOLDOWN_SECONDS:
        remain = CONTINUATION_REENTRY_COOLDOWN_SECONDS - (now_ts - last_ts)
        reason = f"CONTINUATION_REENTRY_COOLDOWN | bias={bias} remain={remain}s"
        softened = _soften_legacy_veto_if_ai_authority_valid(
            decision, reason, "LEGACY_PARTICIPATION_REENTRY_COOLDOWN", V26_LEGACY_ALIGNMENT_PENALTY
        )
        if softened is not None:
            softened["continuation_reentry_diagnostic_only"] = True
            softened["execution_timing_reason"] = reason
            return softened

        blocked = no_trade(reason, market_mode, bb_state)
        blocked.update(decision)
        blocked["decision"] = "NO_TRADE"; blocked["entry_allowed"] = False
        blocked["continuation_reentry_block"] = True
        blocked["execution_timing_reason"] = reason
        return blocked
    execution_timing_state["last_continuation_entry_ts"] = now_ts
    execution_timing_state["last_bias"] = bias
    decision["execution_timing_reason"] = f"EXECUTION_TIMING_OK | late={late['late_entry_score']} exhaustion={exh['exhaustion_score']}"
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

    # V25 TREND WALK OVERRIDE
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

    # V25 TREND NORMAL CONTINUATION OVERRIDE
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
        decision["spike_wait_confirmation"] = True
        decision["wait_state"] = "WAIT_VALID"
        decision["suppression_active"] = True
        decision["intended_action"] = bias if bias in ("BUY", "SELL") else decision.get("intended_action", "WAIT")
        decision["wait_directional_memory"] = bias if bias in ("BUY", "SELL") else "NONE"
        return False, f"SPIKE WAIT_VALID | continuation not confirmed | {spike_reason}"

    # V19.1: TRANSITION + BB NORMAL must explicitly pass the balanced transition gate.
    if market_mode == "TRANSITION" and bb_state == "NORMAL" and not transition_strong_ok:
        # V26.4.8: strong score dominance in TRANSITION+NORMAL executes cautiously.
        # Slight RSI misses are confidence penalties, not hard vetoes, when MACD is not strongly opposite.
        transition_gap_override = score_gap >= STRONG_TRANSITION_NORMAL_SCORE_GAP and dual_direction_confirm(bias, rsi, macd_hist)
        if not (
            (dual_mode == "AGGRESSIVE" and score_gap >= DUAL_AGGRESSIVE_MIN_GAP and dual_direction_confirm(bias, rsi, macd_hist))
            or transition_gap_override
        ):
            return False, (
                f"ENTRY BLOCK | TRANSITION+NORMAL not strong enough "
                f"gap={score_gap} need={TRANSITION_NORMAL_ALLOW_GAP} "
                f"reasons={transition_reasons} | dual={dual_mode} | {learn_note}"
            )
        decision["transition_aggressive_override"] = True
        decision["transition_aggressive_reason"] = (
            "V26.4.8 strong transition-normal score gap cautious allow" if transition_gap_override else dual_mode_reason
        )
        decision["execution_state"] = "EXECUTE_CAUTIOUS"
        decision["management"] = "SCALP_TP"
        decision["mgmt"] = "SCALP_TP"

    # V25 TREND NORMAL MOMENTUM OVERRIDE
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
        ai_valid, ai_reason = _ai_authority_valid(decision, buy_score, sell_score)
        if m3_dir != "NEUTRAL" and m15_dir != "NEUTRAL" and m3_dir != m15_dir:
            reason = f"ENTRY PENALTY | M15/M3 not aligned m15={m15_dir} m3={m3_dir}"
            if ai_valid:
                add_confidence_penalty(decision, V26_LEGACY_ALIGNMENT_PENALTY, reason)
                decision["m3_timing_refinement_only"] = True
                decision["legacy_alignment_authority"] = ai_reason
            else:
                return False, reason.replace("ENTRY PENALTY", "ENTRY BLOCK")
        if bias in ("BUY", "SELL"):
            if m3_dir != "NEUTRAL" and bias != m3_dir:
                reason = f"ENTRY PENALTY | trade bias conflicts with M3 direction bias={bias} m3={m3_dir}"
                if ai_valid:
                    add_confidence_penalty(decision, V26_LEGACY_M3_CONFLICT_PENALTY, reason)
                    decision["m3_timing_refinement_only"] = True
                    decision["legacy_alignment_authority"] = ai_reason
                else:
                    return False, reason.replace("ENTRY PENALTY", "ENTRY BLOCK")
            if m15_dir != "NEUTRAL" and bias != m15_dir:
                reason = f"ENTRY PENALTY | trade bias conflicts with M15 direction bias={bias} m15={m15_dir}"
                if ai_valid:
                    add_confidence_penalty(decision, V26_LEGACY_M15_CONFLICT_PENALTY, reason)
                    decision["legacy_alignment_authority"] = ai_reason
                else:
                    return False, reason.replace("ENTRY PENALTY", "ENTRY BLOCK")

    # 4) Require momentum confirmation before trade.
    ok, reason = has_momentum_confirmation(bias, market_mode, bb_state, rsi, macd_hist, buy_score, sell_score, entry_type)
    if not ok:
        return False, reason

    return True, "ENTRY QUALITY APPROVED"


def apply_entry_quality_or_block(decision, data, market_mode, bb_state, bb_extreme, buy_score, sell_score):
    ok, gate_reason = entry_quality_gate(decision, data, market_mode, bb_state, bb_extreme, buy_score, sell_score)
    if not ok:
        print(gate_reason)
        ai_valid, ai_reason = _ai_authority_valid(decision, buy_score, sell_score)
        if ai_valid:
            softened = dict(decision)
            softened = add_confidence_penalty(softened, V26_LEGACY_ALIGNMENT_PENALTY, gate_reason)
            softened["entry_allowed"] = True
            softened["entry_quality"] = "SOFTENED_TO_CONFIDENCE_PENALTY"
            softened["entry_quality_reason"] = f"{gate_reason} | {ai_reason}; legacy quality veto converted to confidence penalty"
            softened["entry_quality_legacy_veto"] = gate_reason
            softened["entry_quality_hard_block"] = False
            softened["decision"] = "TRADE"
            softened["reason"] = f"{softened.get('reason', '')} | ENTRY_QUALITY_PENALTY_ONLY: {gate_reason}"
            return softened
        blocked = no_trade(gate_reason, market_mode, bb_state)
        for key in (
            "buy_score", "sell_score", "score_gap", "dir_m15", "dir_m3",
            "rsi", "macd_hist", "bb_mid", "bb_upper2", "bb_lower2", "bid", "price", "entry_price", "bb_middle", "bb_upper", "bb_lower",
            "analysis_quality", "adaptive_gap", "learning_enabled", "learning_key",
            "learning_gap_adjust", "learning_note", "learning_stats", "bb_extreme",
            "dual_mode", "aggressive_mode", "dual_mode_reason", "trend_priority", "trend_priority_reason",
            "transition_aggressive_override", "transition_aggressive_reason",
            "soft_lock_state", "soft_lock_direction", "soft_lock_allowed", "soft_lock_reason",
            "transition_decay_count", "transition_decay_required", "transition_decay_active", "transition_decay_reason",
            "transition_wait_max_cycles", "transition_wait_released", "participation_release", "participation_release_reason",
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
        sl_points, tp_points = SL_POINTS_TREND, TP_POINTS_TREND
    elif market_mode == "RANGE":
        sl_points, tp_points = SL_POINTS_RANGE, TP_POINTS_RANGE
    elif market_mode == "SPIKE":
        sl_points, tp_points = SL_POINTS_SPIKE, TP_POINTS_SPIKE
    else:
        sl_points, tp_points = SL_POINTS_TRANSITION, TP_POINTS_TRANSITION

    compressed_sl = min(sl_points, V26_6_2_MAX_SL_POINTS)
    return compressed_sl, max(tp_points, compressed_sl * 1.5)


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
    # V25 RP TIME SYNC STANDARD V1 freshness guard.
    # Only blocks when Writer provides heartbeat_unix and age > 5 sec.
    if is_market_state_stale_by_time_sync(data):
        stale_market_mode = str(data.get("market_mode", data.get("mode", "UNKNOWN")))
        stale_bb_state = str(data.get("bb_state", data.get("bb", "UNKNOWN")))
        decision_data = time_sync_no_trade(data, stale_market_mode, stale_bb_state)
        key = f"{data.get('bar_time', data.get('time', 'NO_BAR'))}-XAU-TIME_SYNC_STALE"
        bar_time = str(data.get("bar_time", data.get("time", "")))
        return key, bar_time, decision_data

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
    dominance_bias, dominance_reason = detect_directional_dominance(
        {
            "market_mode": market_mode,
            "bb_state": bb_state,
            "rsi": rsi,
            "macd_hist": macd_hist,
            "buy_score": buy_score,
            "sell_score": sell_score,
            "market_state_fresh": bool(data.get("market_state_fresh", True)),
            "market_state_age_sec": safe_int(data.get("market_state_age_sec", 0), 0),
            "hard_block": data.get("hard_block", "")
        }
    )

    if buy_score == sell_score and not range_reversal_bias and not dominance_bias:
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
    if dominance_bias in ("BUY", "SELL"):
        action = dominance_bias
        entry_slot = 2
        entry_type = f"XAU_{market_mode}_DOMINANCE_{dominance_bias}_SLOT2"
        management = "SCALP_TP"
        reason = f"{dominance_reason} | DOMINANCE_OVERRIDE_ACTIVE"
    elif market_mode == "SPIKE":
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
        soft_state = str(soft_lock.get("soft_lock_state", "")).upper()
        if soft_state == "TRANSITION_WAIT":
            # V26.4.3: transition governance is now a cautious execution modifier, not a kill switch.
            # Keep participation alive but conservative; execution confidence layer can still downgrade to WAIT/NO_TRADE.
            print(f"SOFT LOCK CAUTIOUS PASS | state={soft_state} dir={soft_lock.get('soft_lock_direction')} reason={soft_lock.get('soft_lock_reason')}")
            management = "SCALP_TP"
            entry_slot = min(entry_slot if entry_slot > 0 else 1, 1)
            entry_type = f"{entry_type}_TRANSITION_WAIT_CAUTIOUS"
        else:
            print(f"SOFT LOCK BLOCK | state={soft_lock.get('soft_lock_state')} dir={soft_lock.get('soft_lock_direction')} reason={soft_lock.get('soft_lock_reason')}")
            blocked = no_trade(f"SOFT LOCK BLOCK | {soft_lock.get('soft_lock_state')} | {soft_lock.get('soft_lock_reason')}", market_mode, bb_state)
            # Participation recovery: preserve directional context during suppression waits.
            # This prevents final bias collapsing to NEUTRAL when signal layer is still directional.
            blocked["bias"] = action
            blocked["action"] = action
            blocked["intended_action"] = action
            blocked["buy_score"] = buy_score
            blocked["sell_score"] = sell_score
            blocked["buyScore"] = buy_score
            blocked["sellScore"] = sell_score
            blocked["score_gap"] = abs(buy_score - sell_score)
            blocked["entry_timing"] = "WAIT_PULLBACK" if soft_lock.get("soft_lock_state") == "TRANSITION_WAIT" else blocked.get("entry_timing", "UNKNOWN")
            blocked["wait_reason"] = "soft-lock suppression active; directional bias preserved"
            blocked = attach_soft_lock_fields(blocked, soft_lock)
            return key, bar_time, blocked

    print(f"MODE:{market_mode} BB:{bb_state} EXT:{bb_extreme} SCORE BUY:{buy_score} SELL:{sell_score} RSI:{rsi:.2f} MACDHist:{macd_hist:.2f} ACTION:{action} SLOT:{entry_slot} MGMT:{management} SOFT={soft_lock.get('soft_lock_state')}")

    if action == "BUY":
        sl = bid - sl_points
        tp = 0 if management == "HOLD_TRAIL" else choose_range_tp("BUY", bid, bb_middle, bb_upper, bb_lower, tp_points)
        decision_data = trade("BUY", entry_type, sl, tp, reason, entry_slot, market_mode, bb_state, management)
        decision_data["entry_price"] = round(bid, 3)
        decision_data["price"] = round(bid, 3)
        decision_data["bid"] = round(bid, 3)
        decision_data["bb_middle"] = round(bb_middle, 3) if bb_middle > 0 else 0
        decision_data["bb_upper"] = round(bb_upper, 3) if bb_upper > 0 else 0
        decision_data["bb_lower"] = round(bb_lower, 3) if bb_lower > 0 else 0
        decision_data["ma50"] = round(ma50, 3) if ma50 > 0 else 0
        decision_data["ma90"] = round(ma90, 3) if ma90 > 0 else 0
        decision_data["ma200"] = round(ma200, 3) if ma200 > 0 else 0
        decision_data["rsi"] = round(rsi, 3)
        decision_data["macd_hist"] = round(macd_hist, 3)
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
        decision_data = apply_pullback_continuation_or_block(
            decision_data, data, market_mode, bb_state, bb_extreme, buy_score, sell_score
        )
        decision_data = apply_execution_timing_intelligence_v24(
            decision_data, data, market_mode, bb_state, bb_extreme
        )
        decision_data = enrich_late_entry_score_v26_6(decision_data, data, market_mode, bb_state, bb_extreme)
        decision_data = apply_sr_entry_location_intelligence_v24(
            decision_data, data, market_mode, bb_state, bb_extreme
        )
        return key, bar_time, decision_data

    if action == "SELL":
        sl = bid + sl_points
        tp = 0 if management == "HOLD_TRAIL" else choose_range_tp("SELL", bid, bb_middle, bb_upper, bb_lower, tp_points)
        decision_data = trade("SELL", entry_type, sl, tp, reason, entry_slot, market_mode, bb_state, management)
        decision_data["entry_price"] = round(bid, 3)
        decision_data["price"] = round(bid, 3)
        decision_data["bid"] = round(bid, 3)
        decision_data["bb_middle"] = round(bb_middle, 3) if bb_middle > 0 else 0
        decision_data["bb_upper"] = round(bb_upper, 3) if bb_upper > 0 else 0
        decision_data["bb_lower"] = round(bb_lower, 3) if bb_lower > 0 else 0
        decision_data["ma50"] = round(ma50, 3) if ma50 > 0 else 0
        decision_data["ma90"] = round(ma90, 3) if ma90 > 0 else 0
        decision_data["ma200"] = round(ma200, 3) if ma200 > 0 else 0
        decision_data["rsi"] = round(rsi, 3)
        decision_data["macd_hist"] = round(macd_hist, 3)
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
        decision_data = apply_pullback_continuation_or_block(
            decision_data, data, market_mode, bb_state, bb_extreme, buy_score, sell_score
        )
        decision_data = apply_execution_timing_intelligence_v24(
            decision_data, data, market_mode, bb_state, bb_extreme
        )
        decision_data = enrich_late_entry_score_v26_6(decision_data, data, market_mode, bb_state, bb_extreme)
        decision_data = apply_sr_entry_location_intelligence_v24(
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
    print(f"RUNTIME_BRANCH={RUNTIME_BRANCH} | ARCH_VERSION={ARCH_VERSION} | BUILD_TAG={BUILD_TAG} | RUNTIME_SIGNATURE={RUNTIME_SIGNATURE}")
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
        cycle_start = time.time()
        data = read_market()
        if data is None:
            fallback = no_trade("market_state read failed")
            fallback["loop_duration_sec"] = round(time.time() - cycle_start, 6)
            fallback["stale_prevention_timing_sec"] = fallback["loop_duration_sec"]
            fallback["decision_write_duration"] = 0.0
            fallback["file_write_latency"] = 0.0
            fallback["total_cycle_time"] = fallback["loop_duration_sec"]
            write_decision(fallback)
            time.sleep(1)
            continue
        try:
            key, bar_time, decision = build_decision(data)
            decision = attach_manual_trend_report(decision, data)
            decision["loop_duration_sec"] = round(time.time() - cycle_start, 6)
            decision["stale_prevention_timing_sec"] = decision["loop_duration_sec"]
            fire_ok, fire_reason = can_fire_or_strong_override(key, bar_time, decision, data)
            if fire_ok:
                decision["final_decision_build_sec"] = round(time.time() - cycle_start, 6)
                write_decision(decision)
            else:
                print("COOLDOWN / MAX SIGNAL BLOCK:", key, "|", fire_reason)
                blocked_decision = build_cooldown_wait_decision(decision, data, fire_reason, cycle_start)
                blocked_decision["final_decision_build_sec"] = round(time.time() - cycle_start, 6)
                write_decision(blocked_decision)
        except Exception as e:
            print("LOGIC ERROR:", e)
            err_decision = no_trade(f"logic error: {e}")
            err_decision["loop_duration_sec"] = round(time.time() - cycle_start, 6)
            err_decision["stale_prevention_timing_sec"] = err_decision["loop_duration_sec"]
            err_decision["decision_write_duration"] = 0.0
            err_decision["file_write_latency"] = 0.0
            err_decision["total_cycle_time"] = err_decision["loop_duration_sec"]
            write_decision(err_decision)
        time.sleep(1)


if __name__ == "__main__":
    run()
