"""Deterministically normalize observed lifecycle evidence after closure."""
from __future__ import annotations
from hashlib import sha256
from uuid import uuid5, NAMESPACE_URL
from typing import Any, Iterable, Mapping
from review_engine.snapshots.snapshot_repository import canonical_json, utc_now
from review_engine.validation.schema_validator import validate_snapshot

class TradeSnapshotBuilder:
    VERSION = "1.0.0"
    def build(self, events: Iterable[Mapping[str, Any]]) -> dict[str, Any]:
        events = sorted(events, key=lambda item: (item["occurred_at_utc"], item["event_id"]))
        closed = [item for item in events if item["event_type"] == "TRADE_CLOSED"]
        if len(closed) != 1: raise ValueError("exactly one TRADE_CLOSED event is required")
        final, payload = closed[0], closed[0]["payload"]
        trade_id = final.get("trade_id") or payload.get("trade_id")
        if not trade_id: raise ValueError("TRADE_CLOSED requires stable trade_id")
        def first(kind: str): return next((item for item in events if item["event_type"] == kind), None)
        decision, requested, filled = first("DECISION_OBSERVED"), first("ENTRY_REQUEST_OBSERVED"), first("ORDER_FILL_OBSERVED")
        merged = {}; [merged.update(item.get("payload", {})) for item in events]
        value = lambda key, default=None: payload.get(key, merged.get(key, default))
        missing = [key for key in ("position_id", "decision_at_utc", "entry_requested_at_utc", "filled_at_utc", "market_mode", "entry_price", "exit_price") if value(key) is None]
        filled_at = value("filled_at_utc", filled and filled["occurred_at_utc"]); closed_at = final["occurred_at_utc"]
        duration = None if not filled_at else int((__import__("datetime").datetime.fromisoformat(closed_at.replace("Z", "+00:00")) - __import__("datetime").datetime.fromisoformat(filled_at.replace("Z", "+00:00"))).total_seconds())
        snapshot = {"schema_version":"1.0.0", "snapshot_id":str(uuid5(NAMESPACE_URL, f"raip:snapshot:{trade_id}")), "created_at_utc":final["observed_at_utc"], "trade_identity":{"trade_id":str(trade_id),"position_id":value("position_id", final.get("position_id")),"series_id":value("series_id", final.get("series_id")),"symbol":final["symbol"],"side":value("side"),"volume":value("volume")}, "timeline":{"decision_at_utc":decision and decision["occurred_at_utc"],"entry_requested_at_utc":requested and requested["occurred_at_utc"],"filled_at_utc":filled_at,"closed_at_utc":closed_at,"duration_seconds":duration}, "decision_context":{key:value(key) for key in ("candidate_id","sequence_id","bias","decision","execution_state","confidence","veto_code")} | {"reason_codes":value("reason_codes", [])}, "market_context":{key:value(key) for key in ("market_mode","market_state","session","atr","rsi","macd_histogram","bb_state","source_snapshot_timestamp_utc")}, "execution_context":{key:value(key) for key in ("requested_price","entry_price","exit_price","spread_points_at_entry","slippage_points","commission","swap")}, "outcome":{key:value(key) for key in ("gross_profit","net_profit","profit_points","r_multiple","mae_points","mfe_points","exit_reason")}, "data_quality":{"completeness_ratio":0.0,"missing_fields":missing,"warnings":[],"source_event_count":len(events)}, "provenance":{"source_event_ids":[item["event_id"] for item in events],"builder_version":self.VERSION,"snapshot_sha256":""}}
        # Source financial semantics are preserved. No cost recomputation occurs.
        snapshot["data_quality"]["completeness_ratio"] = round(1 - len(missing) / 7, 6)
        snapshot["provenance"]["snapshot_sha256"] = sha256(canonical_json(snapshot)).hexdigest()
        errors = validate_snapshot(snapshot)
        if errors: raise ValueError(", ".join(errors))
        return snapshot
