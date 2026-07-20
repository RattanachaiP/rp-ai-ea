from bridge.v29.decision_core import decide
from bridge.v29.progressive_tp_be import adaptive_contract, management_instruction
from pathlib import Path


def market(**overrides):
    state = {"symbol": "XAUUSD", "price": 2300.0, "buy_score": 8, "sell_score": 3,
             "structure_trend": "UP", "bb_state": "WALK_UP", "rsi": 60, "macd_histogram": 0.2,
             "sequence_id": 1, "heartbeat_unix": 1, "initial_r_points": 100}
    state.update(overrides)
    return state


def test_entry_requires_all_three_confirmations_and_publishes_ai_base_contract():
    payload = decide(market(), now=2)
    assert payload["decision"] == "TRADE"
    assert payload["entry_confirmations"] == {"structure": True, "momentum": True, "location": True}
    assert payload["base_take_profit_points"] == 500.0
    assert payload["base_break_even_points"] == 300.0
    contract = payload["adaptive_tp_be_contract"]
    assert contract["ai_owned"] is True
    assert [level["trigger_points"] for level in contract["levels"]] == [250.0, 500.0, 750.0]


def test_entry_rejection_is_explicit_without_score_tuning():
    payload = decide(market(rsi=80), now=2)
    assert payload["decision"] == "WAIT_FOR_BETTER_ENTRY"
    assert payload["direction"] == "BUY"
    assert "MOVE_EXHAUSTED" in payload["waiting_reason"]


def test_progressive_ladder_is_idempotent_and_advances_be_only_after_target():
    assert management_instruction(0.99)["management_action"] == "HOLD"
    assert management_instruction(1.0)["level"] == "TP1"
    tp2 = management_instruction(2.0, ["TP1"])
    assert (tp2["level"], tp2["close_fraction"], tp2["breakeven_offset_r"]) == ("TP2", 0.25, 0.5)


def test_adaptive_contract_owns_target_be_and_lock_ladders_from_base_values():
    contract = adaptive_contract(500, 300, 100, trend_strength=8, entry_quality=80)
    assert [level["trigger_points"] for level in contract["levels"]] == [300.0, 500.0, 700.0]
    assert [level["lock_points"] for level in contract["levels"]] == [300, 300, 300.0]
    action = management_instruction(5.0, contract=contract, initial_r_points=100)
    assert action["level"] == "AI_TP1"


def test_contract_can_be_omitted_for_legacy_v29_fallback_compatibility():
    payload = decide(market(EnableAIProgressiveTP=False, EnableAIProgressiveBE=False), now=2)
    assert "adaptive_tp_be_contract" not in payload
    assert management_instruction(1.0)["level"] == "TP1"


def test_mt5_executor_exposes_only_base_configuration_and_keeps_legacy_fallback():
    source = Path("mt5/v29/RP_AI_ProgressiveTPBE_V29.mq5").read_text(encoding="utf-8")
    assert "PositionClosePartial" in source
    assert "PositionModify" in source
    assert "GlobalVariableSet" in source
    assert "InpEnableAIProgressiveTP" in source and "InpEnableAIProgressiveBE" in source
    assert "InpBaseTakeProfitPoints" in source and "InpBaseBreakEvenPoints" in source
    assert "adaptive_tp_be_contract" in source
    assert "LEGACY_V29_FALLBACK" in source


def test_mt5_legacy_fallback_reconstructs_and_verifies_a_nonzero_base_tp():
    source = Path("mt5/v29/RP_AI_ProgressiveTPBE_V29.mq5").read_text(encoding="utf-8")
    # Contract-present orders retain adaptive ownership; only its absence enters
    # the deterministic BaseTakeProfit path.
    assert "bool adaptive_present=payload.has_adaptive_tp_be_contract" in source
    assert "base_take_profit_points" in source
    assert "LegacyTakeProfitPrice" in source
    assert '"V29_LEGACY_TP_RECONSTRUCTED' in source
    assert 'g_trade.Buy(payload.lot,_Symbol,0.0,0.0,order_tp)' in source
    assert 'g_trade.Sell(payload.lot,_Symbol,0.0,0.0,order_tp)' in source
    # A broker that accepts an entry but drops TP is repaired on later
    # execution cycles, with the resulting position read back for verification.
    assert "RecoverBrokerTakeProfit" in source
    assert "g_trade.PositionModify(ticket,PositionGetDouble(POSITION_SL),target_tp)" in source
    assert '"V29_TP_BROKER_VERIFIED' in source


def test_mt5_tp_source_selection_makes_adaptive_authority_and_fallbacks_explicit():
    source = Path("mt5/v29/RP_AI_ProgressiveTPBE_V29.mq5").read_text(encoding="utf-8")
    assert 'TP_SOURCE_ADAPTIVE_CONTRACT "ADAPTIVE_CONTRACT"' in source
    assert 'TP_SOURCE_LEGACY_RECONSTRUCTION "LEGACY_RECONSTRUCTION"' in source
    assert 'TP_SOURCE_TERMINAL_BASE_DEFAULT "TERMINAL_BASE_DEFAULT"' in source
    assert "bool legacy_available=!adaptive_present" in source
    assert "AssertAdaptiveAuthority(adaptive_present,legacy_executed,tp_source,0)" in source
    assert '"V29_ASSERT_ADAPTIVE_OVERRIDE' in source
    assert '"V29_ASSERT_INVALID_TP_SOURCE' in source
    assert '"V29_TP_TRACE' in source


def test_mt5_tp_recovery_is_per_ticket_and_bounded_to_three_attempts():
    source = Path("mt5/v29/RP_AI_ProgressiveTPBE_V29.mq5").read_text(encoding="utf-8")
    assert "#define V29_TP_RECOVERY_MAX_ATTEMPTS 3" in source
    assert '"tp_recovery_attempt_count"' in source
    assert '"tp_recovery_completed"' in source
    assert '"tp_recovery_failed"' in source
    assert '"V29_TP_RECOVERY_ATTEMPT' in source
    assert '"V29_TP_RECOVERY_FAILED' in source
    assert '"V29_TP_RECOVERY_ABORTED' in source
    assert '"V29_ASSERT_RECOVERY_LIMIT' in source
    assert "if(attempts>=V29_TP_RECOVERY_MAX_ATTEMPTS)" in source
