import time
from pathlib import Path

from bridge.v28.clean_core import decide
from bridge.v28.dashboard_contract import DEFAULT_DASHBOARD, load_dashboard_contract
from bridge.v28.payload_contract import validate_payload


def fresh_market(**overrides):
    data = {
        "symbol": "XAUUSD",
        "price": 2300.0,
        "buy_score": 7,
        "sell_score": 3,
        "sequence_id": 42,
        "heartbeat_unix": int(time.time()),
        "open_positions": 0,
        "max_open_positions": 1,
    }
    data.update(overrides)
    return data


def dashboard(**overrides):
    cfg = DEFAULT_DASHBOARD.copy()
    cfg.update(overrides)
    return cfg


def test_trade_payload_passes_shared_contract():
    payload = decide(fresh_market(), dashboard(), score_min_required=3)
    assert payload["decision"] == "TRADE"
    assert payload["reason"] == "BUY: BUY_SCORE_DOMINANCE; V28_IMMEDIATE_EXECUTION"
    assert payload["payload_valid"] is True
    assert payload["broker_sl_required"] is False
    assert payload["stop_loss"] == 0.0
    assert payload["take_profit"] == 2301.0
    assert validate_payload(payload) == (True, "EXECUTOR_CONTRACT_PASS")


def test_score_gap_below_legacy_minimum_still_publishes_immediately():
    payload = decide(fresh_market(buy_score=5, sell_score=3), dashboard(), score_min_required=3)
    assert payload["decision"] == "TRADE"
    assert payload["direction"] == "BUY"
    assert payload["trade_block_reason"] == "NONE"
    assert payload["log_event"] == "EXECUTABLE_TRADE_PUBLISHED"


def test_dashboard_trade_toggle_is_not_a_v28_entry_gate():
    payload = decide(fresh_market(), dashboard(trade_enabled=False), score_min_required=999)
    assert payload["decision"] == "TRADE"
    assert payload["executor_contract_status"] == "EXECUTOR_CONTRACT_PASS"


def test_dashboard_can_disable_broker_sl_with_explicit_contract():
    cfg = dashboard(broker_sl={"enabled": False, "points": 0.0})
    payload = decide(fresh_market(), cfg, score_min_required=3)
    assert payload["decision"] == "TRADE"
    assert payload["broker_sl_required"] is False
    assert payload["stop_loss"] == 0.0
    assert payload["sl_suppression_reason"] == "DASHBOARD_BROKER_SL_DISABLED"
    assert validate_payload(payload) == (True, "EXECUTOR_CONTRACT_PASS")


def test_stale_market_data_blocks_with_reason():
    payload = decide(fresh_market(heartbeat_unix=int(time.time()) - 999), dashboard(), score_min_required=3)
    assert payload["decision"] == "NO_TRADE"
    assert payload["trade_block_reason"] == "STALE_MARKET_DATA"


def test_entry_uses_directional_score_gap_only():
    payload = decide(
        fresh_market(market_mode="TREND", bb_state="WALK_UP", rsi=60, macd_histogram=0.2),
        dashboard(), score_min_required=3,
    )
    assert payload["decision"] == "TRADE"
    assert payload["lot"] == 0.01


def test_non_supportive_telemetry_does_not_add_a_second_veto_or_resize():
    payload = decide(
        fresh_market(market_mode="RANGE", bb_state="MIDDLE", rsi=45, macd_histogram=-0.2),
        dashboard(), score_min_required=3,
    )
    assert payload["decision"] == "TRADE"
    assert payload["lot"] == 0.01


def test_validation_profile_disables_broker_sl_and_retains_hard_loss_cap_and_tp():
    payload = decide(fresh_market(), dashboard(), score_min_required=3)
    assert payload["broker_sl_required"] is False
    assert payload["broker_tp_required"] is True
    assert payload["risk_hard_loss_cap_usd_per_001_lot"] == 1.2
    assert payload["fixed_tp_close_usd_per_001_lot"] == 1.0
    assert payload["stop_loss"] == 0.0
    assert payload["take_profit"] == 2301.0


def test_buy_risk_package_has_no_broker_sl_and_a_100_point_tp():
    payload = decide(fresh_market(), dashboard(), score_min_required=3)
    assert payload["stop_loss"] == 0.0
    assert payload["entry_price"] < payload["take_profit"]
    assert round(payload["take_profit"] - payload["entry_price"], 2) == 1.0


def test_disabled_broker_sl_contract_rejects_any_later_sl_injection():
    payload = decide(fresh_market(), dashboard(), score_min_required=3)
    payload["stop_loss"] = 2298.8
    assert validate_payload(payload) == (False, "BROKER_STOP_LOSS_MUST_BE_ZERO_WHEN_DISABLED")


def test_executor_uses_zero_sl_for_the_disabled_broker_sl_contract():
    executor = (Path(__file__).resolve().parents[1] / "mt5/v28/RP_AI_Executor_V28_CleanCore.mq5").read_text(encoding="utf-8")
    assert 'double sl = 0.0;' in executor
    assert "g_trade.Buy(lot, symbol, 0.0, sl, tp, comment)" in executor
    assert "g_trade.Sell(lot, symbol, 0.0, sl, tp, comment)" in executor


def test_executor_reads_the_live_common_decision_payload_and_maps_action():
    executor = (Path(__file__).resolve().parents[1] / "mt5/v28/RP_AI_Executor_V28_CleanCore.mq5").read_text(encoding="utf-8")
    assert 'input string InpDecisionFile = "decision.json";' in executor
    assert 'JsonString(json, "action", JsonString(json, "direction"))' in executor
    assert 'if(!JsonBool(json, "entry_allowed")) { reason = "ENTRY_NOT_ALLOWED"; return false; }' in executor
    assert 'if(!JsonBool(json, "market_state_fresh")) { reason = "STALE_MARKET_STATE"; return false; }' in executor
    assert 'if(JsonString(json, "schema_version") != "V28_EXECUTABLE_PAYLOAD_1")' not in executor


def test_zero_broker_sl_profile_is_active_with_profile_f_as_baseline():
    contract = load_dashboard_contract(Path(__file__).resolve().parents[1])
    assert contract["active_profile"] == "ZERO_BROKER_SL_VALIDATION"
    assert contract["validation_baseline_profile"] == "Profile_F_MARKET_CLOSE_ONLY"
    assert contract["broker_sl"] == {"enabled": False, "points": 0.0}
    assert contract["fixed_tp"] == {"enabled": True, "points": 100.0}
    assert contract["breakeven"]["enabled"] is False
    assert contract["trailing"]["enabled"] is False
    assert contract["runner"]["enabled"] is False
    assert contract["profit_lock"]["enabled"] is False
    assert contract["risk_hard_loss_cap_usd_per_001_lot"] == 1.2
