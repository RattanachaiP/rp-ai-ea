from __future__ import annotations
from datetime import datetime, timezone
from hashlib import sha256
import json
from typing import Callable, Mapping, Sequence
from uuid import uuid4
class TradeSnapshotBuilder:
 def __init__(self,*,clock:Callable[[],datetime]|None=None): self._clock=clock or (lambda:datetime.now(timezone.utc))
 def build(self, events:Sequence[Mapping[str,object]])->dict[str,object]:
  closed=[event for event in events if event.get("event_type")=="TRADE_CLOSED"]
  if len(closed)!=1: raise ValueError("EXACTLY_ONE_TRADE_CLOSED_EVENT_REQUIRED")
  close=closed[0]; payload=close["payload"]; trade_id=close.get("trade_id")
  if not isinstance(trade_id,str) or not trade_id: raise ValueError("TRADE_ID_REQUIRED")
  def get(key,default=None): return payload.get(key, close.get(key,default))
  filled=get("filled_at_utc"); closed_at=close["occurred_at_utc"]; duration=None
  if isinstance(filled,str): duration=max(0,(self._parse(closed_at)-self._parse(filled)).total_seconds())
  missing=[key for key,value in {"position_id":close.get("position_id"),"decision_at_utc":get("decision_at_utc"),"entry_requested_at_utc":get("entry_requested_at_utc"),"filled_at_utc":filled,"requested_price":get("requested_price"),"spread_points_at_entry":get("spread_points_at_entry"),"slippage_points":get("slippage_points"),"profit_points":get("profit_points"),"r_multiple":get("r_multiple"),"mae_points":get("mae_points"),"mfe_points":get("mfe_points"),"exit_reason":get("exit_reason")}.items() if value is None]
  snapshot={"schema_version":"1.0.0","snapshot_id":str(uuid4()),"created_at_utc":self._iso(self._clock()),"trade_identity":{"trade_id":trade_id,"position_id":close.get("position_id"),"series_id":close.get("series_id"),"symbol":close["symbol"],"side":get("side"),"volume":get("volume")},"timeline":{"decision_at_utc":get("decision_at_utc"),"entry_requested_at_utc":get("entry_requested_at_utc"),"filled_at_utc":filled,"closed_at_utc":closed_at,"duration_seconds":duration},"decision_context":{key:get(key) for key in ("candidate_id","sequence_id","bias","decision","execution_state","confidence","veto_code")} | {"reason_codes":get("reason_codes",[])},"market_context":{key:get(key) for key in ("market_mode","market_state","session","atr","rsi","macd_histogram","bb_state","source_snapshot_timestamp_utc")},"execution_context":{key:get(key) for key in ("requested_price","entry_price","exit_price","spread_points_at_entry","slippage_points","commission","swap")},"outcome":{key:get(key) for key in ("gross_profit","net_profit","profit_points","r_multiple","mae_points","mfe_points","exit_reason")},"data_quality":{"completeness_ratio":round(1-len(missing)/13,6),"missing_fields":missing,"warnings":[],"source_event_count":len(events)},"provenance":{"source_event_ids":[event["event_id"] for event in events],"builder_version":"1.0.0","snapshot_sha256":""}}
  for key in ("entry_price","exit_price","commission","swap","gross_profit","net_profit"): snapshot["execution_context" if key in {"entry_price","exit_price","commission","swap"} else "outcome"][key]=get(key,0.0)
  snapshot["provenance"]["snapshot_sha256"]=sha256(self._canon(snapshot)).hexdigest(); return snapshot
 @staticmethod
 def _parse(value): return datetime.fromisoformat(value.replace("Z","+00:00"))
 @staticmethod
 def _iso(value): return value.astimezone(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00","Z")
 @staticmethod
 def _canon(value): return json.dumps(value,sort_keys=True,separators=(",",":"),allow_nan=False).encode()
