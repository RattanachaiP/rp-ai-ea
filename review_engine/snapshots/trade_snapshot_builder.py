import hashlib, json, uuid
from datetime import datetime, timezone
from review_engine.collector.event_types import utc_now
from review_engine.validation import validate_snapshot

def _hash(value): return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
def _value(events, key, default=None):
    for event in reversed(events):
        if key in event.get("payload",{}): return event["payload"][key]
    return default
class TradeSnapshotBuilder:
    version="1.0.0"
    def build(self, closed_event, related_events=()):
        events=[*related_events, closed_event]; p=closed_event["payload"]
        missing=[]
        def val(name, default=None):
            result=_value(events,name,default)
            if result is None: missing.append(name)
            return result
        filled=val("filled_at_utc"); closed=closed_event["occurred_at_utc"]
        duration=None
        if filled:
            duration=int((datetime.fromisoformat(closed.replace("Z","+00:00"))-datetime.fromisoformat(filled.replace("Z","+00:00"))).total_seconds())
        data={"schema_version":"1.0.0","snapshot_id":str(uuid.uuid4()),"created_at_utc":utc_now(),"trade_identity":{"trade_id":closed_event["trade_id"],"position_id":closed_event.get("position_id"),"series_id":closed_event.get("series_id"),"symbol":closed_event.get("symbol"),"side":val("side"),"volume":val("volume")},"timeline":{"decision_at_utc":_value(events,"decision_at_utc"),"entry_requested_at_utc":_value(events,"entry_requested_at_utc"),"filled_at_utc":filled,"closed_at_utc":closed,"duration_seconds":duration},"decision_context":{"candidate_id":closed_event.get("candidate_id"),"sequence_id":closed_event.get("sequence_id"),"bias":_value(events,"bias"),"decision":_value(events,"decision"),"execution_state":_value(events,"execution_state"),"confidence":_value(events,"confidence"),"veto_code":_value(events,"veto_code"),"reason_codes":_value(events,"reason_codes",[])},"market_context":{k:_value(events,k) for k in ("market_mode","market_state","session","atr","rsi","macd_histogram","bb_state","source_snapshot_timestamp_utc")},"execution_context":{k:val(k, 0.0 if k in {"entry_price","exit_price","commission","swap"} else None) for k in ("requested_price","entry_price","exit_price","spread_points_at_entry","slippage_points","commission","swap")},"outcome":{k:val(k, 0.0 if k in {"gross_profit","net_profit"} else None) for k in ("gross_profit","net_profit","profit_points","r_multiple","mae_points","mfe_points","exit_reason")},"data_quality":{"completeness_ratio":0,"missing_fields":sorted(set(missing)),"warnings":[],"source_event_count":len(events)},"provenance":{"source_event_ids":[e["event_id"] for e in events],"builder_version":self.version,"snapshot_sha256":""}}
        total=39; data["data_quality"]["completeness_ratio"]=round((total-len(set(missing)))/total,4)
        data["provenance"]["snapshot_sha256"]=_hash({**data,"provenance":{**data["provenance"],"snapshot_sha256":""}})
        return validate_snapshot(data)
