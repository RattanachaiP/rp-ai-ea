"""PR229 Demo runtime preparation and publication-identity checks."""

import importlib
from datetime import datetime
from pathlib import Path
from uuid import UUID

import pytest


MODULE = "bridge.ai_decision_engine_xauusd_v26_execution_confidence_engine"
DEFAULT_SHARED_ROOT = Path(
    r"C:\Users\rp_fu\AppData\Roaming\MetaQuotes\Terminal\Common\Files\RP_AI_EA\shared"
)


@pytest.fixture
def engine():
    return importlib.import_module(MODULE)


def publication(decision="TRADE", direction="BUY", confidence=72):
    return {"decision": decision, "direction": direction, "confidence": confidence}


def test_identity_is_created_once_and_retry_is_idempotent(engine):
    first = engine.attach_decision_identity(publication(), lifecycle="NORMAL_TRADE")
    identity = tuple(first[field] for field in (
        "decision_uuid", "decision_timestamp", "timestamp"
    ))
    second = engine.attach_decision_identity(first, lifecycle="NORMAL_TRADE")
    assert second is first
    assert tuple(second[field] for field in (
        "decision_uuid", "decision_timestamp", "timestamp"
    )) == identity
    UUID(first["decision_uuid"])
    assert datetime.fromisoformat(first["timestamp"].replace("Z", "+00:00")).tzinfo


def test_existing_identity_and_timestamp_are_preserved(engine):
    payload = publication() | {
        "decision_uuid": "00000000-0000-4000-8000-000000000229",
        "decision_timestamp": "2026-07-27T12:00:00Z",
        "timestamp": "2026-07-27T12:00:00Z",
    }
    result = engine.attach_decision_identity(payload, lifecycle="NORMAL_TRADE")
    assert result["decision_uuid"] == "00000000-0000-4000-8000-000000000229"
    assert result["timestamp"] == "2026-07-27T12:00:00Z"


def test_two_logical_decisions_receive_different_uuids(engine):
    first = engine.attach_decision_identity(publication(), lifecycle="NORMAL_TRADE")
    second = engine.attach_decision_identity(
        publication(direction="SELL"), lifecycle="NORMAL_TRADE"
    )
    assert first["decision_uuid"] != second["decision_uuid"]


@pytest.mark.parametrize("direction", ["WAIT", "HOLD", "BLOCKED", "", None])
def test_malformed_or_missing_trade_direction_fails_closed(engine, direction):
    with pytest.raises(ValueError, match="INVALID_TRADE_DIRECTION"):
        engine.attach_decision_identity(
            publication(direction=direction), lifecycle="NORMAL_TRADE"
        )


@pytest.mark.parametrize("confidence", [None, "72", float("nan"), -1, 101, True])
def test_malformed_confidence_fails_closed(engine, confidence):
    with pytest.raises(ValueError, match="INVALID_DECISION_CONFIDENCE"):
        engine.attach_decision_identity(
            publication(confidence=confidence), lifecycle="NORMAL_TRADE"
        )


def test_missing_confidence_is_distinct_from_legitimate_zero(engine):
    with pytest.raises(ValueError, match="MISSING_DECISION_CONFIDENCE"):
        engine.attach_decision_identity(
            {"decision": "TRADE", "direction": "BUY"}, lifecycle="NORMAL_TRADE"
        )
    result = engine.attach_decision_identity(
        publication(confidence=0), lifecycle="NORMAL_TRADE"
    )
    assert result["confidence"] == 0


@pytest.mark.parametrize("lifecycle", [
    "GOVERNED_NO_TRADE", "STALE_INPUT_FALLBACK", "LOGIC_ERROR_REJECTION",
])
def test_non_trade_lifecycles_receive_one_non_executable_identity(engine, lifecycle):
    payload = publication(decision="NO_TRADE", direction="NONE", confidence=0)
    first = engine.attach_decision_identity(payload, lifecycle=lifecycle)
    decision_uuid = first["decision_uuid"]
    second = engine.attach_decision_identity(first, lifecycle=lifecycle)
    assert second["direction"] == "NONE"
    assert second["decision_uuid"] == decision_uuid
    assert second["decision_lifecycle"] == lifecycle


def test_no_trade_rejects_executable_or_missing_direction(engine):
    for direction in ("BUY", "SELL", None):
        with pytest.raises(ValueError, match="INVALID_NO_TRADE_DIRECTION"):
            engine.attach_decision_identity(
                publication("NO_TRADE", direction, 0),
                lifecycle="GOVERNED_NO_TRADE",
            )


def test_final_publication_uses_v26_canonical_bias_authority(engine):
    trade = engine.final_decision_publication(
        {"decision": "TRADE", "bias": "SELL", "confidence": 80},
        lifecycle="NORMAL_TRADE",
    )
    no_trade = engine.final_decision_publication(
        {"decision": "NO_TRADE", "bias": "NEUTRAL", "confidence": 0},
        lifecycle="GOVERNED_NO_TRADE",
    )
    assert trade["direction"] == "SELL"
    assert no_trade["direction"] == "NONE"


def test_runtime_shared_root_override_and_default_restoration(monkeypatch, tmp_path):
    engine = importlib.import_module(MODULE)
    monkeypatch.setenv("RP_AI_SHARED_ROOT", str(tmp_path))
    engine = importlib.reload(engine)
    assert engine.BASE_PATH == tmp_path / "XAUUSD"
    assert engine.FILE_PATH == tmp_path / "XAUUSD" / "market_state.json"
    assert engine.OUTPUT_PATH == tmp_path / "XAUUSD" / "decision.json"

    monkeypatch.delenv("RP_AI_SHARED_ROOT")
    engine = importlib.reload(engine)
    assert engine.COMMON_SHARED_ROOT == DEFAULT_SHARED_ROOT
    assert engine.BASE_PATH == DEFAULT_SHARED_ROOT / "XAUUSD"
