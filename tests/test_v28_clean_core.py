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
    assert payload["reason"] == "BUY: BUY_SCORE_DOMINANCE; SCORE_GAP 4 >= 3"
    assert payload["payload_valid"] is True
    assert validate_payload(payload) == (True, "EXECUTOR_CONTRACT_PASS")


def test_score_gap_below_minimum_is_explained_no_trade():
    payload = decide(fresh_market(buy_score=5, sell_score=3), dashboard(), score_min_required=3)
    assert payload["decision"] == "NO_TRADE"
    assert payload["trade_block_reason"] == "SCORE_GAP_BELOW_MINIMUM"
    assert payload["log_event"] == "NO_TRADE_REASON"


def test_dashboard_can_disable_broker_sl_with_explicit_contract():
    cfg = dashboard(broker_sl={"enabled": False, "points": 0.0})
    payload = decide(fresh_market(), cfg, score_min_required=3)
    assert payload["decision"] == "TRADE"
    assert payload["broker_sl_required"] is False
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


def test_symmetric_validation_contract_has_complete_tp_and_sl():
    payload = decide(fresh_market(), dashboard(), score_min_required=3)
    assert payload["broker_sl_required"] is True
    assert payload["broker_tp_required"] is True
    assert payload["risk_hard_loss_cap_usd_per_001_lot"] == 1.2
    assert payload["fixed_tp_close_usd_per_001_lot"] == 1.0
    assert payload["stop_loss"] > 0
    assert payload["take_profit"] > 0


def test_buy_risk_package_has_the_correct_price_sides():
    payload = decide(fresh_market(), dashboard(), score_min_required=3)
    assert payload["stop_loss"] < payload["entry_price"] < payload["take_profit"]
    assert round(payload["entry_price"] - payload["stop_loss"], 2) == 1.2


def test_profile_f_is_the_dashboard_validation_baseline():
    contract = load_dashboard_contract(Path(__file__).resolve().parents[1])
    assert contract["active_profile"] == "Profile_F_MARKET_CLOSE_ONLY"
    assert contract["validation_baseline_profile"] == "Profile_F_MARKET_CLOSE_ONLY"
