"""Regression coverage for the single authoritative published execution state."""

import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))
sys.path.insert(0, str(REPO_ROOT / "bridge"))

from ai_decision_engine_xauusd_v26_execution_confidence_engine import (  # noqa: E402
    apply_expectancy_entry_filters_v26_6_2,
    build_cooldown_wait_decision,
    enforce_final_execution_state_v28,
)


def test_cooldown_block_is_not_published_as_a_trade():
    blocked = build_cooldown_wait_decision(
        {
            "decision": "TRADE",
            "entry_allowed": True,
            "bias": "BUY",
            "action": "BUY",
            "execution_state": "EXECUTE_AGGRESSIVE",
            "buy_score": 9,
            "sell_score": 1,
        },
        {},
        "normal fire unavailable",
        0,
    )

    final = enforce_final_execution_state_v28(blocked)

    assert final["decision"] == "NO_TRADE"
    assert final["entry_allowed"] is False
    assert final["allowed"] is False
    assert final["action"] == "WAIT"
    assert final["execution_state"] == "WAIT"
    assert final["intended_action"] == "BUY"
    assert final["cooldown_active"] is True
    assert final["suppression_active"] is True


def test_executable_buy_clears_stale_cooldown_suppression():
    final = enforce_final_execution_state_v28(
        {
            "decision": "TRADE",
            "entry_allowed": True,
            "action": "BUY",
            "cooldown_active": False,
            "cooldown_wait_active": False,
            "suppression_active": True,
        }
    )

    assert final["decision"] == "TRADE"
    assert final["entry_allowed"] is True
    assert final["suppression_active"] is False


def test_final_publish_does_not_downgrade_validated_trade_from_stale_cooldown():
    """Regression: final publication may clean telemetry but may not veto TRADE."""
    final = enforce_final_execution_state_v28(
        {
            "decision": "TRADE",
            "allowed": True,
            "entry_allowed": True,
            "payload_valid": True,
            "action": "BUY",
            "execution_state": "EXECUTE_AGGRESSIVE",
            # These are stale fields injected by an earlier enrichment layer.
            "cooldown_active": True,
            "cooldown_wait_active": True,
            "suppression_active": True,
        }
    )

    assert final["decision"] == "TRADE"
    assert final["allowed"] is True
    assert final["entry_allowed"] is True
    assert final["action"] == "BUY"
    assert final["execution_state"] == "EXECUTE_AGGRESSIVE"
    assert final["cooldown_active"] is False
    assert final["cooldown_wait_active"] is False
    assert final["suppression_active"] is False
    assert final["final_publish_state_guard"] == "TRADE_PRESERVED_STALE_COOLDOWN_CLEARED"


def _v28_trade(score_gap):
    return {
        "schema_version": "V28_EXECUTABLE_PAYLOAD_1",
        "runtime_version": "V28_CLEAN_EXPECTANCY_CORE",
        "decision": "TRADE",
        "action": "BUY",
        "bias": "BUY",
        "score_gap": score_gap,
        "entry_allowed": True,
        "allowed": True,
        "execution_state": "TRADE",
        "payload_valid": True,
    }


def test_v28_gap1_is_advisory_and_reaches_executable_final_state():
    final = enforce_final_execution_state_v28(apply_expectancy_entry_filters_v26_6_2(_v28_trade(1)))

    assert final["decision"] == "TRADE"
    assert final["entry_allowed"] is True
    assert final["execution_state"] == "TRADE"
    assert final.get("effective_veto_code") != "V26_6_2_WEAK_GAP_NO_TRADE"
    assert final["expectancy_gap_advisory"] == "WEAK_GAP"
    assert final["expectancy_gap_execution_blocked"] is False


def test_v28_gap2_is_executable_without_legacy_emergency_recovery():
    result = apply_expectancy_entry_filters_v26_6_2(_v28_trade(2))

    assert result["decision"] == "TRADE"
    assert result["entry_allowed"] is True
    assert result["execution_state"] == "TRADE"
    assert "EMERGENCY_GAP2_APPROVED" not in result


def test_v28_gap3_trade_is_unchanged_except_for_advisory_telemetry():
    result = apply_expectancy_entry_filters_v26_6_2(_v28_trade(3))

    assert result["decision"] == "TRADE"
    assert result["entry_allowed"] is True
    assert result["execution_state"] == "TRADE"
    assert result["expectancy_gap_advisory"] == "GAP_ACCEPTABLE"


def test_v28_preexisting_no_trade_is_unchanged_by_legacy_filter():
    payload = _v28_trade(1)
    payload.update({"decision": "NO_TRADE", "entry_allowed": False, "execution_state": "NO_TRADE"})

    assert apply_expectancy_entry_filters_v26_6_2(payload) == payload


def test_v28_explicit_hard_safety_veto_remains_authoritative():
    payload = _v28_trade(1)
    payload.update({
        "final_veto_owner": "BROKER_SAFETY",
        "effective_veto_code": "ABNORMAL_SPREAD",
        "final_veto_reason": "Spread exceeds hard safety limit",
    })

    result = apply_expectancy_entry_filters_v26_6_2(payload)

    assert result["final_veto_owner"] == "BROKER_SAFETY"
    assert result["effective_veto_code"] == "ABNORMAL_SPREAD"
    assert result["final_veto_reason"] == "Spread exceeds hard safety limit"
    assert result["expectancy_gap_execution_blocked"] is False
