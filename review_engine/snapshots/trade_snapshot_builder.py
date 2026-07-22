from datetime import datetime, timezone
import hashlib, json, uuid
from typing import Any, Iterable, Mapping
from review_engine.validation import validate_event, validate_snapshot

def _now(): return datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")
def _value(payload, key, default=None): return payload.get(key, default)
def _canonical_hash(value):
    value = json.loads(json.dumps(value)); value["provenance"]["snapshot_sha256"] = ""
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":")).encode()).hexdigest()

class TradeSnapshotBuilder:
    """Independent processing stage: converts a closed event stream into a snapshot."""
    builder_version = "1.0.0"
    def build(self, events: Iterable[Mapping[str, Any]]) -> dict[str, Any]:
        events = [dict(e) for e in events]
        for event in events: validate_event(event)
        closed = next((e for e in reversed(events) if e["event_type"] == "TRADE_CLOSED"), None)
        if closed is None: raise ValueError("TRADE_CLOSED event required")
        payload = closed["payload"]
        trade_id = closed["trade_id"] or _value(payload, "trade_id")
        if not trade_id: raise ValueError("trade_id required for snapshot")
        def prior(name): return next((e for e in events if e["event_type"] == name), None)
        fill, decision, request = prior("ORDER_FILL_OBSERVED"), prior("DECISION_OBSERVED"), prior("ENTRY_REQUEST_OBSERVED")
        fp, dp, rp = (fill or {}).get("payload", {}), (decision or {}).get("payload", {}), (request or {}).get("payload", {})
        missing=[]
        def optional(path, value):
            if value is None: missing.append(path)
            return value
        snapshot={"schema_version":"1.0.0", "snapshot_id":str(uuid.uuid4()), "created_at_utc":_now(),
          "trade_identity":{"trade_id":str(trade_id),"position_id":closed["position_id"],"series_id":closed["series_id"],"symbol":closed["symbol"],"side":str(_value(payload,"side","")),"volume":_value(payload,"volume")},
          "timeline":{"decision_at_utc": optional("timeline.decision_at_utc", (decision or {}).get("occurred_at_utc")),"entry_requested_at_utc":optional("timeline.entry_requested_at_utc",(request or {}).get("occurred_at_utc")),"filled_at_utc":optional("timeline.filled_at_utc",(fill or {}).get("occurred_at_utc")),"closed_at_utc":closed["occurred_at_utc"],"duration_seconds":_value(payload,"duration_seconds")},
          "decision_context":{"candidate_id":closed["candidate_id"],"sequence_id":closed["sequence_id"],"bias":optional("decision_context.bias",_value(dp,"bias")),"decision":optional("decision_context.decision",_value(dp,"decision")),"execution_state":optional("decision_context.execution_state",_value(dp,"execution_state")),"confidence":optional("decision_context.confidence",_value(dp,"confidence")),"veto_code":optional("decision_context.veto_code",_value(dp,"veto_code")),"reason_codes":_value(dp,"reason_codes",[])},
          "market_context":{"market_mode":optional("market_context.market_mode",_value(dp,"market_mode")),"market_state":optional("market_context.market_state",_value(dp,"market_state")),"session":optional("market_context.session",_value(dp,"session")),"atr":optional("market_context.atr",_value(dp,"atr")),"rsi":optional("market_context.rsi",_value(dp,"rsi")),"macd_histogram":optional("market_context.macd_histogram",_value(dp,"macd_histogram")),"bb_state":optional("market_context.bb_state",_value(dp,"bb_state")),"source_snapshot_timestamp_utc":optional("market_context.source_snapshot_timestamp_utc",_value(dp,"source_snapshot_timestamp_utc"))},
          "execution_context":{"requested_price":optional("execution_context.requested_price",_value(rp,"requested_price")),"entry_price":_value(payload,"entry_price"),"exit_price":_value(payload,"exit_price"),"spread_points_at_entry":optional("execution_context.spread_points_at_entry",_value(fp,"spread_points")),"slippage_points":optional("execution_context.slippage_points",_value(fp,"slippage_points")),"commission":_value(payload,"commission",0.0),"swap":_value(payload,"swap",0.0)},
          "outcome":{"gross_profit":_value(payload,"gross_profit",0.0),"net_profit":_value(payload,"net_profit",0.0),"profit_points":optional("outcome.profit_points",_value(payload,"profit_points")),"r_multiple":optional("outcome.r_multiple",_value(payload,"r_multiple")),"mae_points":optional("outcome.mae_points",_value(payload,"mae_points")),"mfe_points":optional("outcome.mfe_points",_value(payload,"mfe_points")),"exit_reason":optional("outcome.exit_reason",_value(payload,"exit_reason"))},
          "data_quality":{"completeness_ratio":0.0,"missing_fields":missing,"warnings":[],"source_event_count":len(events)},"provenance":{"source_event_ids":[e["event_id"] for e in events],"builder_version":self.builder_version,"snapshot_sha256":""}}
        total=25; snapshot["data_quality"]["completeness_ratio"]=(total-len(missing))/total
        snapshot["provenance"]["snapshot_sha256"]=_canonical_hash(snapshot); validate_snapshot(snapshot); return snapshot
