"""Regression coverage for the single authoritative published execution state."""

import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))
sys.path.insert(0, str(REPO_ROOT / "bridge"))

from ai_decision_engine_xauusd_v26_execution_confidence_engine import (  # noqa: E402
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
