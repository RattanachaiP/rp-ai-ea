"""Regression evidence for the governed canonical V14 producer integration."""
import hashlib
import json
import re
from pathlib import Path
from uuid import UUID, uuid5

SOURCE = Path("mt5/canonical/RP_Market_State_Writer_V14_TIME_SYNC_STANDARD_V1_COMPILE_FIX.mq5")
BEFORE_FIELDS = (
    "symbol", "timeframe", "time_sync", "heartbeat_unix", "sequence_id",
    "server_time", "bar_time", "bid", "ask", "ma50", "ma90", "ma200",
    "rsi", "macd_main", "macd_signal", "macd_hist", "bb_upper",
    "bb_middle", "bb_lower", "bb3_upper", "bb3_middle", "bb3_lower",
    "bb4_upper", "bb4_middle", "bb4_lower", "buyScore", "sellScore",
)
IDENTITY = {
    "MARKET_STATE_PRODUCER": "RP_AI_MT5_MARKET_STATE",
    "MARKET_STATE_PRODUCER_VERSION": "V1",
    "MARKET_STATE_SCHEMA_VERSION": "1.0",
    "MARKET_STATE_SOURCE_UUID": "dc3777c6-cf0d-5a7b-bd58-8a5c44568475",
}
POLICY = {
    "market_liquidity_quality": "tradeable && ask > bid ? 1.0 : 0.0",
    "market_session_quality": "SYMBOL_TRADE_MODE != SYMBOL_TRADE_MODE_DISABLED ? 1.0 : 0.0",
    "policy_version": "RP_MT5_DIRECT_TELEMETRY_V1",
    "slippage_expectation": "SYMBOL_TRADE_TICK_SIZE/SYMBOL_POINT",
    "source_provenance": "MT5_SYMBOL_TRADE_MODE_TICK_AND_TICK_SIZE",
    "spread_points": "max(0,(ask-bid)/SYMBOL_POINT)",
}


def source():
    return SOURCE.read_text(encoding="utf-8")


def define(text, name):
    match = re.search(rf'^#define\s+{name}\s+"([^"]+)"$', text, re.MULTILINE)
    assert match, name
    return match.group(1)


def output_fields(text):
    return re.findall(r'json \+= "  \\"([^"\\]+)\\"', text)


def test_before_schema_is_an_ordered_compatible_subset_without_duplicates():
    fields = output_fields(source())
    assert len(fields) == len(set(fields))
    positions = [fields.index(field) for field in BEFORE_FIELDS]
    assert positions == sorted(positions)


def test_calculation_regression_preserves_canonical_indicator_and_score_formulas():
    text = source()
    expected = (
        "double macdHist = macdMain - macdSignal;",
        "if(bid > ma50) buyScore++; else sellScore++;",
        "if(ma50 > ma90) buyScore++; else sellScore++;",
        "if(ma90 > ma200) buyScore++; else sellScore++;",
        "if(rsi > 55) buyScore++;", "if(rsi < 45) sellScore++;",
        "if(macdHist > 0) buyScore++;", "if(macdHist < 0) sellScore++;",
        "if(bid <= bbLower) buyScore++;", "if(bid >= bbUpper) sellScore++;",
    )
    assert all(text.count(line) == 1 for line in expected)
    assert text.count("ok &= CopyOne(") == 15


def test_identity_is_constant_owned_and_matches_unchanged_runtime_contract():
    text = source()
    assert {name: define(text, name) for name in IDENTITY} == IDENTITY
    for name in IDENTITY:
        assert f"input string {name}" not in text
    UUID(IDENTITY["MARKET_STATE_SOURCE_UUID"])


def test_typed_governed_telemetry_has_bound_policy_and_never_uses_spread_as_slippage():
    text = source()
    canonical = json.dumps(POLICY, sort_keys=True, separators=(",", ":"))
    digest = hashlib.sha256(canonical.encode()).hexdigest()
    policy_uuid = str(uuid5(UUID(IDENTITY["MARKET_STATE_SOURCE_UUID"]), digest))
    assert define(text, "TELEMETRY_POLICY_DIGEST") == digest
    assert define(text, "TELEMETRY_POLICY_UUID") == policy_uuid
    assert "slippage_expectation = tick_size / point;" in text
    assert "slippage_expectation = spread_points" not in text
    assert "const double &" not in text  # typed outputs, no raw JSON extension point


def test_sequence_is_durable_and_advances_only_after_successful_publication():
    text = source()
    write = text.index("if(!wrote)")
    persist = text.index("if(!PersistSequence(nextSequenceId))")
    advance = text.index("g_market_state_sequence_id = nextSequenceId;")
    assert write < persist < advance
    assert "GlobalVariablesFlush()" in text
