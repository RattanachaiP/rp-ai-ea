"""V28 clean expectancy-first decision core.

This module deliberately contains a single decision path.  It consumes the
market-state contract, classifies the directional evidence into A/B/C, builds
the complete initial risk package, and atomically publishes its result.  It
never imports V27 strategy or final-decision code.
"""
from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any, Dict

from .dashboard_contract import load_dashboard_contract
from .payload_contract import SCHEMA_VERSION, validate_payload

DEFAULT_SCORE_MIN_REQUIRED = 3.0
DEFAULT_LOT = 0.01


def _num(data: Dict[str, Any], key: str, default: float = 0.0) -> float:
    try:
        return float(data.get(key, default))
    except (TypeError, ValueError):
        return default


def load_market_state(path: Path) -> Dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        data = json.load(handle)
    return data if isinstance(data, dict) else {}


def market_is_fresh(market: Dict[str, Any], max_age_seconds: int = 15, now: int | None = None) -> bool:
    if "market_state_fresh" in market and not bool(market["market_state_fresh"]):
        return False
    heartbeat = int(_num(market, "heartbeat_unix", 0))
    age = (now if now is not None else int(time.time())) - heartbeat
    return heartbeat > 0 and 0 <= age <= max_age_seconds


def calculate_direction_and_gap(market: Dict[str, Any]) -> tuple[str | None, float, str]:
    buy_score = _num(market, "buy_score", _num(market, "score_buy", 0.0))
    sell_score = _num(market, "sell_score", _num(market, "score_sell", 0.0))
    gap = abs(buy_score - sell_score)
    if buy_score > sell_score:
        return "BUY", gap, "BUY_SCORE_DOMINANCE"
    if sell_score > buy_score:
        return "SELL", gap, "SELL_SCORE_DOMINANCE"
    return None, 0.0, "NO_DIRECTIONAL_EDGE"


def build_risk_package(direction: str, entry_price: float, dashboard: Dict[str, Any]) -> Dict[str, Any]:
    point = float(dashboard.get("point", 0.01) or 0.01)
    sl_enabled = bool(dashboard.get("broker_sl", {}).get("enabled", True))
    tp_enabled = bool(dashboard.get("fixed_tp", {}).get("enabled", True))
    sl_points = float(dashboard.get("broker_sl", {}).get("points", 0.0) or 0.0)
    tp_points = float(dashboard.get("fixed_tp", {}).get("points", 100.0) or 0.0)
    risk: Dict[str, Any] = {
        "broker_sl_required": sl_enabled,
        "broker_tp_required": tp_enabled,
        "risk_hard_loss_cap_usd_per_001_lot": float(dashboard.get("risk_hard_loss_cap_usd_per_001_lot", 1.0)),
        "fixed_tp_close_usd_per_001_lot": float(dashboard.get("fixed_tp_close_usd_per_001_lot", 1.0)),
    }
    if sl_enabled and sl_points > 0:
        risk["stop_loss"] = entry_price - sl_points * point if direction == "BUY" else entry_price + sl_points * point
    else:
        risk["stop_loss"] = 0.0
        risk["sl_suppression_reason"] = "DASHBOARD_BROKER_SL_DISABLED"
    if tp_enabled and tp_points > 0:
        risk["take_profit"] = entry_price + tp_points * point if direction == "BUY" else entry_price - tp_points * point
    else:
        risk["take_profit"] = 0.0
        risk["tp_contract_reason"] = "DASHBOARD_TP_MANAGED_OR_DISABLED"
    return risk


def decide(market: Dict[str, Any], dashboard: Dict[str, Any], score_min_required: float = DEFAULT_SCORE_MIN_REQUIRED, now: int | None = None) -> Dict[str, Any]:
    now = int(time.time()) if now is None else now
    sequence_id = int(_num(market, "sequence_id", 0))
    heartbeat = int(_num(market, "heartbeat_unix", now))
    direction, score_gap, edge_reason = calculate_direction_and_gap(market)
    base: Dict[str, Any] = {
        "schema_version": SCHEMA_VERSION, "runtime_version": "V28_CLEAN_EXPECTANCY_CORE",
        "symbol": market.get("symbol", "XAUUSD"), "sequence_id": sequence_id, "heartbeat_unix": heartbeat,
        "score_gap": score_gap, "score_min_required": score_min_required,
        "market_evidence": {key: market.get(key) for key in ("buy_score", "sell_score", "spread", "price", "bid")},
        "final_authority": "PYTHON_AI_V28_CLEAN_CORE", "dashboard_profile": dashboard.get("active_profile", "Profile_F_MARKET_CLOSE_ONLY"),
        "management_mode": dashboard.get("management_mode", "DASHBOARD_MANAGED"), "dashboard_contract": dashboard,
        "executor_contract_status": "NOT_EVALUATED",
    }
    block = None
    if not direction:
        block = edge_reason
    elif score_gap < score_min_required:
        block = "SCORE_GAP_BELOW_MINIMUM"
    elif not market_is_fresh(market, now=now):
        block = "STALE_MARKET_DATA"
    elif not bool(dashboard.get("trade_enabled", True)) or bool(dashboard.get("emergency", {}).get("entries_disabled", False)):
        block = "DASHBOARD_TRADE_DISABLED"
    elif int(_num(market, "open_positions", 0)) >= int(_num(market, "max_open_positions", 1)):
        block = "OPEN_POSITION_LIMIT"
    if block:
        base.update({"decision": "NO_TRADE", "direction": direction or "NONE", "bias": direction or "NEUTRAL", "reason": f"NO_TRADE: {block}", "trade_block_reason": block, "payload_valid": False, "log_event": "NO_TRADE_REASON"})
        base["executor_contract_status"] = validate_payload(base)[1]
        return base
    entry_price = _num(market, "price", _num(market, "bid", 0.0))
    payload = {**base, "decision": "TRADE", "direction": direction, "bias": direction,
               "reason": f"{direction}: {edge_reason}; SCORE_GAP {score_gap:g} >= {score_min_required:g}",
               "entry_reason": edge_reason, "trade_block_reason": "NONE", "entry_price": entry_price,
               "lot": _num(market, "lot", DEFAULT_LOT), "payload_valid": True}
    payload.update(build_risk_package(direction, entry_price, dashboard))
    ok, status = validate_payload(payload)
    payload["payload_valid"], payload["executor_contract_status"] = ok, status
    if not ok:
        payload.update({"decision": "NO_TRADE", "reason": "NO_TRADE: INVALID_RISK_PACKAGE", "trade_block_reason": "INVALID_RISK_PACKAGE", "log_event": "NO_TRADE_REASON"})
    else:
        payload["log_event"] = "EXECUTABLE_TRADE_PUBLISHED"
    return payload


def write_decision(payload: Dict[str, Any], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    with tmp.open("w", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=2, sort_keys=True)
    tmp.replace(path)
