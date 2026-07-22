"""Evidence-only conversion of closed events into immutable snapshots."""
from __future__ import annotations
from datetime import datetime, timezone
from hashlib import sha256
from typing import Any
from uuid import uuid4
from ..collector.event_types import canonical_json, utc_timestamp, validate_event

class TradeSnapshotBuilder:
    version = "1.0.0"
    def __init__(self, clock=lambda: datetime.now(timezone.utc)): self.clock = clock
    def build(self, events: list[dict[str, Any]]) -> dict[str, Any]:
        normalized = [validate_event(event) for event in events]
        closed = [event for event in normalized if event["event_type"] == "TRADE_CLOSED"]
        if len(closed) != 1: raise ValueError("EXACTLY_ONE_TRADE_CLOSED_EVENT_REQUIRED")
        close = closed[0]; data = close["payload"]
        trade_id = close["trade_id"] or data.get("trade_id")
        if not isinstance(trade_id, str) or not trade_id: raise ValueError("TRADE_ID_REQUIRED")
        def first(*names):
            for event in normalized:
                for name in names:
                    if event["payload"].get(name) is not None: return event["payload"][name]
            return None
        filled, closed_at = first("filled_at_utc", "entry_filled_at_utc"), data.get("closed_at_utc", close["occurred_at_utc"])
        filled = utc_timestamp(filled) if filled else None; closed_at = utc_timestamp(closed_at)
        duration = int((datetime.fromisoformat(closed_at.replace("Z", "+00:00")) - datetime.fromisoformat(filled.replace("Z", "+00:00"))).total_seconds()) if filled else None
        missing = [name for name, value in {"timeline.filled_at_utc": filled, "execution_context.entry_price": first("entry_price"), "execution_context.exit_price": data.get("exit_price")}.items() if value is None]
        gross, commission, swap = data.get("gross_profit"), data.get("commission", 0.0), data.get("swap", 0.0)
        net = data.get("net_profit", (gross + commission + swap) if all(isinstance(x, (int,float)) for x in (gross,commission,swap)) else None)
        snapshot = {"schema_version":"1.0.0", "snapshot_id":str(uuid4()), "created_at_utc":self.clock().astimezone(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00","Z"), "trade_identity":{"trade_id":trade_id,"position_id":close["position_id"],"series_id":close["series_id"],"symbol":close["symbol"],"side":data.get("side"),"volume":data.get("volume")}, "timeline":{"decision_at_utc":first("decision_at_utc"),"entry_requested_at_utc":first("entry_requested_at_utc"),"filled_at_utc":filled,"closed_at_utc":closed_at,"duration_seconds":duration}, "decision_context":{key:first(key) for key in ("candidate_id","sequence_id","bias","decision","execution_state","confidence","veto_code")} | {"reason_codes":first("reason_codes") or []}, "market_context":{key:first(key) for key in ("market_mode","market_state","session","atr","rsi","macd_histogram","bb_state","source_snapshot_timestamp_utc")}, "execution_context":{"requested_price":first("requested_price"),"entry_price":first("entry_price"),"exit_price":data.get("exit_price"),"spread_points_at_entry":first("spread_points_at_entry"),"slippage_points":data.get("slippage_points"),"commission":commission,"swap":swap}, "outcome":{key:data.get(key) for key in ("gross_profit","net_profit","profit_points","r_multiple","mae_points","mfe_points","exit_reason")}, "data_quality":{"completeness_ratio":0.0,"missing_fields":missing,"warnings":[],"source_event_count":len(normalized)}, "provenance":{"source_event_ids":[event["event_id"] for event in normalized],"builder_version":self.version,"snapshot_sha256":""}}
        snapshot["outcome"]["net_profit"] = net
        snapshot["data_quality"]["completeness_ratio"] = round(1 - len(missing)/3, 6)
        snapshot["provenance"]["snapshot_sha256"] = sha256(canonical_json(snapshot).encode()).hexdigest()
        return snapshot
