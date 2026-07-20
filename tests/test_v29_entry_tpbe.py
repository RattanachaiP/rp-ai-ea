from bridge.v29.decision_core import decide
from bridge.v29.progressive_tp_be import management_instruction
from pathlib import Path


def market(**overrides):
    state = {"symbol": "XAUUSD", "price": 2300.0, "buy_score": 8, "sell_score": 3,
             "structure_trend": "UP", "bb_state": "WALK_UP", "rsi": 60, "macd_histogram": 0.2,
             "sequence_id": 1, "heartbeat_unix": 1, "initial_r_points": 100}
    state.update(overrides)
    return state


def test_entry_requires_all_three_confirmations_and_publishes_ladder():
    payload = decide(market(), now=2)
    assert payload["decision"] == "TRADE"
    assert payload["entry_confirmations"] == {"structure": True, "momentum": True, "location": True}
    assert [level["trigger_r"] for level in payload["progressive_tp_be"]["levels"]] == [1.0, 2.0, 3.0]


def test_entry_rejection_is_explicit_without_score_tuning():
    payload = decide(market(rsi=80), now=2)
    assert payload["decision"] == "NO_TRADE"
    assert payload["reason"] == "ENTRY_LOCATION_NOT_CONFIRMED"


def test_progressive_ladder_is_idempotent_and_advances_be_only_after_target():
    assert management_instruction(0.99)["management_action"] == "HOLD"
    assert management_instruction(1.0)["level"] == "TP1"
    tp2 = management_instruction(2.0, ["TP1"])
    assert (tp2["level"], tp2["close_fraction"], tp2["breakeven_offset_r"]) == ("TP2", 0.25, 0.5)


def test_mt5_manager_is_limited_to_progressive_partial_tp_and_one_way_be():
    source = Path("mt5/v29/RP_AI_ProgressiveTPBE_V29.mq5").read_text(encoding="utf-8")
    assert "PositionClosePartial" in source
    assert "PositionModify" in source
    assert "GlobalVariableSet" in source
    assert "TP1R" in source and "TP2R" in source and "TP3R" in source
