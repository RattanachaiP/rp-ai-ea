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
    "market_liquidity_quality": "1.0 at spread<=20; linear to 0.0 at spread>=50; 0.0 when session quality is 0.0",
    "market_session_quality": "FULL=1.0; LONGONLY=0.5; SHORTONLY=0.5; CLOSEONLY=0.0; DISABLED=0.0",
    "policy_version": "RP_MT5_MODELED_TELEMETRY_V2",
    "slippage_expectation": "EWMA(alpha=0.2) of absolute successive live-tick mid-price movement in points; unavailable before first transition",
    "source_provenance": "MT5_SYMBOL_TRADE_MODE_AND_LIVE_TICK_STREAM",
    "spread_points": "max(0,(live_tick.ask-live_tick.bid)/SYMBOL_POINT)",
    "tick_validity": "bid>0; ask>=bid; tick age 0..5 seconds",
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
    assert "g_slippage_expectation_ewma = 0.2 * movement_points" in text
    assert "slippage_expectation = g_slippage_expectation_ewma;" in text
    assert "slippage_expectation = spread_points" not in text
    assert "SymbolInfoDouble(_Symbol, SYMBOL_TRADE_TICK_SIZE)" not in text
    assert "const double &" not in text  # typed outputs, no raw JSON extension point


def test_restricted_modes_wide_spread_and_stale_ticks_are_not_full_quality():
    text = source()
    assert "trade_mode == SYMBOL_TRADE_MODE_FULL" in text
    assert "SYMBOL_TRADE_MODE_LONGONLY || trade_mode == SYMBOL_TRADE_MODE_SHORTONLY" in text
    assert "market_session_quality = 0.5;" in text
    assert "CLOSEONLY and DISABLED" in text
    assert "spread_points >= 50.0" in text
    assert "market_liquidity_quality = 0.0;" in text
    assert "tick_age_seconds > 5" in text


def test_sequence_is_persisted_only_after_atomic_publication():
    text = source()
    publish = text.index("if(UseAbsoluteDBridge)", text.index("void OnTick()"))
    commit_check = text.index("if(!wrote)", publish)
    advance = text.index("g_market_state_sequence_id = nextSequenceId;", commit_check)
    persist = text.index("if(!PersistSequence(nextSequenceId))", advance)
    assert publish < commit_check < advance < persist
    assert "WriteTextCommonAtomic(commonPath, json)" in text
    assert "WriteTextAbsoluteAtomic(path, json)" in text
    assert "ExpertRemove();" in text


def _restore(journal, publication):
    """Executable model of the Writer's restart reconciliation."""
    if journal is not None and (type(journal) is not int or journal < 0):
        raise ValueError("corrupt persistent state: fail closed")
    candidates = [value for value in (journal, publication) if value is not None]
    previous = max(candidates, default=0)
    return previous, previous + 1


def test_sequence_restart_continues_after_last_committed_publication():
    assert _restore(394, 394) == (394, 395)
    # Crash after atomic publication but before journal persistence recovers
    # from the committed market_state document and still never decreases.
    assert _restore(393, 394) == (394, 395)


def test_sequence_missing_state_starts_or_recovers_safely():
    assert _restore(None, None) == (0, 1)
    assert _restore(None, 394) == (394, 395)


def test_sequence_corrupt_state_fails_closed():
    import pytest
    with pytest.raises(ValueError, match="fail closed"):
        _restore("394", 394)
    text = source()
    assert "SEQUENCE STATE CORRUPT" in text
    assert "return false; // fail closed" in text


def test_duplicate_writer_is_protected_by_terminal_wide_cas_mutex():
    text = source()
    assert "GlobalVariableSetOnCondition" in text
    assert "DUPLICATE WRITER BLOCKED" in text
    assert "GlobalVariableTemp(g_sequence_global_name)" in text
    assert text.index("if(!LoadSequence())") < text.index("return INIT_FAILED;", text.index("if(!LoadSequence())"))


def _acquire(owner, *, owner_exists=False, heartbeat_expired=False,
             cas_results=(True,), operation_error=0):
    """Executable state model for the bounded terminal-global CAS loop."""
    contender = 5163285837109
    if operation_error:
        return "MUTEX_ACCESS_FAILURE", owner
    results = iter(cas_results)
    for _ in range(4):
        if owner and owner != contender and owner_exists and not heartbeat_expired:
            return "DUPLICATE_WRITER", owner
        if next(results, False):
            return ("ACQUIRED_ZERO" if owner == 0 else "RECOVERED"), contender
        # A false CAS with error zero is a value mismatch and is retried after
        # the terminal global is read again. The model's owner is unchanged.
    return "MUTEX_ACCESS_FAILURE", owner


def test_zero_owner_mutex_acquisition_regressions():
    # GlobalVariableTemp creates a missing mutex with the unowned value zero;
    # an already-existing zero mutex follows exactly the same guarded CAS path.
    assert _acquire(0) == ("ACQUIRED_ZERO", 5163285837109)
    assert _acquire(0) == ("ACQUIRED_ZERO", 5163285837109)
    # A comparison mismatch is contention rather than an API error and retries.
    assert _acquire(0, cas_results=(False, True)) == ("ACQUIRED_ZERO", 5163285837109)


def test_active_and_abandoned_owner_regressions():
    assert _acquire(123, owner_exists=True) == ("DUPLICATE_WRITER", 123)
    assert _acquire(123, owner_exists=False) == ("RECOVERED", 5163285837109)
    assert _acquire(123, owner_exists=True, heartbeat_expired=True) == (
        "RECOVERED", 5163285837109
    )


def test_terminal_global_failure_and_cleanup_regressions():
    assert _acquire(0, operation_error=4501) == ("MUTEX_ACCESS_FAILURE", 0)
    text = source()
    assert "ResetLastError();\n      if(GlobalVariableSetOnCondition" in text
    assert "int cas_error = GetLastError();" in text
    assert "if(cas_error != 0)" in text
    release = text[text.index("void ReleaseWriterOwnership()") : text.index("bool ExactChartIDFromDouble")]
    assert "owner_value == (double)ChartID()" in release
    assert "GlobalVariableSetOnCondition(g_sequence_global_name, 0.0, owner_value)" in release


def test_mutex_owner_conversion_and_required_logs_are_explicit():
    text = source()
    assert "MAX_EXACT_DOUBLE_INTEGER" in text
    assert "MathFloor(value) != value" in text
    assert "(double)chart_id == value" in text
    assert "if(owner_chart <= 0)" in text
    assert 'Print("WRITER OWNERSHIP ACQUIRED | previous_owner=0 | new_owner="' in text
    assert 'Print("DUPLICATE WRITER BLOCKED | active_owner="' in text


def test_restore_log_is_explicit_and_identifies_storage_source():
    text = source()
    assert 'Print("SEQUENCE RESTORE OK | previous="' in text
    assert '" next="' in text
    assert '" source="' in text
    assert all(source_name in text for source_name in (
        "FILE_COMMON_JOURNAL", "MARKET_STATE_RECOVERY", "EMPTY_STATE"
    ))


def test_init_failures_are_explicitly_categorized_and_release_ownership():
    text = source()
    on_init = text[text.index("int OnInit()") : text.index("void OnTimer()")]
    assert on_init.count("return INIT_FAILED;") == 2
    assert on_init.count('Print("INIT FAILED | category=') == 2
    assert all(category in on_init for category in (
        "DUPLICATE_WRITER", "MUTEX_CREATION_FAILURE",
        "SEQUENCE_JOURNAL_CORRUPTION", "PUBLISHED_STATE_RECOVERY_FAILURE",
    ))
    sequence_failure = on_init[on_init.index("if(!LoadSequence())") :]
    assert sequence_failure.index("ReleaseWriterOwnership();") < sequence_failure.index("return INIT_FAILED;")


def test_owner_lock_supports_clean_release_and_abandoned_lease_recovery():
    text = source()
    assert "owner == contender" in text  # same-chart EX5 replacement/recompile
    assert "!OwnerChartExists(owner)" in text  # closed/replaced chart
    assert "lease_expired" in text  # live chart left behind without its Writer
    assert "ABANDONED OWNER LOCK RECOVERED" in text
    assert "EventSetTimer(5);" in text
    assert "GlobalVariableSet(g_writer_heartbeat_global_name, (double)TimeLocal())" in text
    deinit = text[text.index("void OnDeinit") : text.index("void OnTick")]
    assert "EventKillTimer();" in deinit
    assert "ReleaseWriterOwnership();" in deinit


def test_corrupt_journal_log_is_actionable_and_fail_closed():
    text = source()
    assert 'Print("SEQUENCE STATE CORRUPT | path=FILE_COMMON:"' in text
    assert '" | content=\\\"", state, "\\\" | validation=' in text
    assert "reconciling market_state.json; then reattach the Writer" in text
    assert "PUBLISHED-STATE RECOVERY FAILURE | path=" in text
