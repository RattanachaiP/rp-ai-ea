import time

from bridge.v28.clean_core import decide
from bridge.v28.dashboard_contract import DEFAULT_DASHBOARD
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
    assert payload["reason"] == "EXECUTABLE_TRADE_PUBLISHED"
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
