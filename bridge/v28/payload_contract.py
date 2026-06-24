"""Shared V28 decision payload contract for Python AI and executor."""
from __future__ import annotations

from typing import Any, Dict, Tuple

SCHEMA_VERSION = "V28_EXECUTABLE_PAYLOAD_1"
VALID_DIRECTIONS = {"BUY", "SELL"}
VALID_DECISIONS = {"TRADE", "NO_TRADE"}

REQUIRED_TRADE_FIELDS = {
    "decision", "direction", "bias", "entry_price", "lot", "dashboard_profile",
    "management_mode", "broker_sl_required", "broker_tp_required", "payload_valid",
    "sequence_id", "heartbeat_unix", "dashboard_contract", "final_authority",
}


def validate_payload(payload: Dict[str, Any]) -> Tuple[bool, str]:
    if payload.get("schema_version") != SCHEMA_VERSION:
        return False, "INVALID_SCHEMA_VERSION"
    if payload.get("decision") not in VALID_DECISIONS:
        return False, "INVALID_DECISION"
    if payload.get("decision") == "NO_TRADE":
        return True, "NO_TRADE_PAYLOAD_VALID"

    missing = sorted(field for field in REQUIRED_TRADE_FIELDS if field not in payload)
    if missing:
        return False, "MISSING_FIELDS:" + ",".join(missing)
    if payload.get("direction") not in VALID_DIRECTIONS or payload.get("bias") not in VALID_DIRECTIONS:
        return False, "INVALID_DIRECTION"
    if not payload.get("payload_valid"):
        return False, "PAYLOAD_VALID_FALSE"
    if float(payload.get("entry_price") or 0) <= 0:
        return False, "INVALID_ENTRY_PRICE"
    if float(payload.get("lot") or 0) <= 0:
        return False, "INVALID_LOT"
    sl_required = bool(payload.get("broker_sl_required"))
    tp_required = bool(payload.get("broker_tp_required"))
    if sl_required and float(payload.get("stop_loss") or 0) <= 0:
        return False, "MISSING_REQUIRED_STOP_LOSS"
    if (not sl_required) and payload.get("sl_suppression_reason") != "DASHBOARD_BROKER_SL_DISABLED":
        return False, "MISSING_APPROVED_SL_SUPPRESSION"
    if tp_required and float(payload.get("take_profit") or 0) <= 0:
        return False, "MISSING_REQUIRED_TAKE_PROFIT"
    if (not tp_required) and payload.get("tp_contract_reason") != "DASHBOARD_TP_MANAGED_OR_DISABLED":
        return False, "MISSING_APPROVED_TP_CONTRACT"
    return True, "EXECUTOR_CONTRACT_PASS"
