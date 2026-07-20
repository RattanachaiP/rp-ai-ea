"""Regression coverage for the bounded V29.1 entry-quality layer."""
from bridge.v29.decision_core import decide
from bridge.v29.entry_quality_engine import evaluate_entry_quality
from bridge.v28.clean_core import decide as v28_decide
from bridge.v28.dashboard_contract import DEFAULT_DASHBOARD


def market(**overrides):
    state = {
        "symbol": "XAUUSD", "price": 2300.0, "buy_score": 8, "sell_score": 3,
        "structure_trend": "UP", "bb_state": "WALK_UP", "rsi": 60,
        "macd_histogram": 0.2, "market_mode": "TREND", "sequence_id": 1,
        "heartbeat_unix": 1, "initial_r_points": 100,
    }
    state.update(overrides)
    return state


def test_high_quality_entry_executes_with_all_component_scores():
    payload = decide(market(), now=2)
    assert payload["decision"] == "TRADE"
    assert payload["entry_score"] == 97
    assert payload["entry_confidence"] == "HIGH"
    assert payload["entry_components"] == {
        "structure": 100, "momentum": 100, "location": 85,
        "exhaustion": 100, "market_quality": 100,
    }
    assert "direction=BUY" in payload["entry_quality_telemetry"]
    assert "action=EXECUTE" in payload["entry_quality_telemetry"]


def test_poor_momentum_waits_without_changing_direction():
    payload = decide(market(macd_histogram=-0.2), now=2)
    assert payload["decision"] == "WAIT_FOR_BETTER_ENTRY"
    assert payload["direction"] == "BUY"
    assert payload["entry_components"]["momentum"] == 20
    assert "MOMENTUM_NOT_ALIGNED" in payload["waiting_reason"]


def test_poor_location_waits():
    payload = decide(market(bb_state="EXTREME_UP"), now=2)
    assert payload["decision"] == "WAIT_FOR_BETTER_ENTRY"
    assert payload["entry_components"]["location"] == 0
    assert "LOCATION_EXTENDED" in payload["waiting_reason"]


def test_exhausted_move_waits():
    payload = decide(market(rsi=80), now=2)
    assert payload["decision"] == "WAIT_FOR_BETTER_ENTRY"
    assert payload["entry_components"]["exhaustion"] == 0
    assert "MOVE_EXHAUSTED" in payload["waiting_reason"]


def test_low_total_score_waits_and_high_total_score_executes():
    low = evaluate_entry_quality("BUY", market(structure_trend="", bb_state="MIDDLE", rsi=50, macd_histogram=0, market_mode="RANGE"))
    high = evaluate_entry_quality("SELL", market(structure_trend="DOWN", bb_state="WALK_DOWN", rsi=40, macd_histogram=-0.2, market_mode="TREND"))
    assert low["entry_score"] < 70 and low["action"] == "WAIT_FOR_BETTER_ENTRY"
    assert high["entry_score"] >= 70 and high["action"] == "EXECUTE"


def test_quality_engine_returns_exact_original_direction():
    assert evaluate_entry_quality("BUY", market())["direction"] == "BUY"
    assert evaluate_entry_quality("SELL", market())["direction"] == "SELL"


def test_v29_payload_is_additive_and_v28_remains_untouched():
    payload = decide(market(), now=2)
    for field in ("entry_intelligence_status", "candidate_direction", "entry_allowed", "entry_confirmations", "progressive_tp_be"):
        assert field in payload
    for field in ("entry_score", "entry_confidence", "waiting_reason", "entry_components"):
        assert field in payload
    v28 = v28_decide({"symbol": "XAUUSD", "price": 2300.0, "buy_score": 7, "sell_score": 3,
                      "sequence_id": 1, "heartbeat_unix": 1}, DEFAULT_DASHBOARD, now=1)
    assert v28["decision"] == "TRADE"
    assert "entry_score" not in v28
