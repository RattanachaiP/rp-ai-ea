from __future__ import annotations
from datetime import datetime, timezone
from hashlib import sha256
import json, os
from pathlib import Path
from typing import Callable, Iterable, Mapping
class SnapshotLoader:
 def load(self,root:Path|str,date_utc:str)->list[Mapping[str,object]]:
  path=Path(root)/"snapshots"/date_utc.replace("-","/")
  records=[]
  for file in sorted(path.glob("trade_*.json")) if path.exists() else []:
   try: records.append(json.loads(file.read_text(encoding="utf-8")))
   except (OSError,json.JSONDecodeError): continue
  return records
class DailyAggregator:
 def aggregate(self,snapshots:Iterable[Mapping[str,object]])->dict[str,object]:
  items=sorted(snapshots,key=lambda item:str(item["snapshot_id"])); net=[float(x["outcome"]["net_profit"]) for x in items]; wins=[x for x in net if x>0]; losses=[x for x in net if x<0]; sides=[x["trade_identity"]["side"] for x in items]; missing={}
  for item in items:
   for field in item["data_quality"]["missing_fields"]: missing[field]=missing.get(field,0)+1
  return {"scope":{"symbols":sorted({x["trade_identity"]["symbol"] for x in items}),"trade_count":len(items),"complete_snapshot_count":sum(not x["data_quality"]["missing_fields"] for x in items),"incomplete_snapshot_count":sum(bool(x["data_quality"]["missing_fields"]) for x in items)},"performance":{"wins":len(wins),"losses":len(losses),"breakeven":len(items)-len(wins)-len(losses),"win_rate":len(wins)/len(items) if items else None,"gross_profit":sum(float(x["outcome"]["gross_profit"]) for x in items),"net_profit":sum(net),"profit_factor":sum(wins)/abs(sum(losses)) if losses else None,"average_win":sum(wins)/len(wins) if wins else None,"average_loss":sum(losses)/len(losses) if losses else None,"average_duration_seconds":sum(x["timeline"]["duration_seconds"] or 0 for x in items)/len(items) if items else None},"direction":{"buy_trades":sides.count("BUY"),"sell_trades":sides.count("SELL"),"buy_net_profit":sum(n for n,x in zip(net,items) if x["trade_identity"]["side"]=="BUY"),"sell_net_profit":sum(n for n,x in zip(net,items) if x["trade_identity"]["side"]=="SELL")},"data_quality":{"average_completeness_ratio":sum(x["data_quality"]["completeness_ratio"] for x in items)/len(items) if items else 0.0,"missing_field_counts":missing,"warnings":[]},"snapshot_ids":[x["snapshot_id"] for x in items]}
class DailyReportWriter:
 def __init__(self,root:Path|str):self.root=Path(root)
 def write(self,date_utc:str,report:Mapping[str,object])->Path:
  path=self.root/"daily"/date_utc.replace("-","/")/"daily_review.json";path.parent.mkdir(parents=True,exist_ok=True);temp=path.with_suffix(".json.tmp")
  with temp.open("wb") as stream:stream.write((json.dumps(report,sort_keys=True,indent=2)+"\n").encode());stream.flush();os.fsync(stream.fileno())
  os.replace(temp,path);return path
class DailyReviewBuilder:
 def __init__(self,loader=None,aggregator=None,writer=None,*,clock:Callable[[],datetime]|None=None):self.loader=loader or SnapshotLoader();self.aggregator=aggregator or DailyAggregator();self.writer=writer;self.clock=clock or (lambda:datetime.now(timezone.utc))
 def build(self,date_utc:str,root:Path|str)->dict[str,object]:
  data=self.aggregator.aggregate(self.loader.load(root,date_utc)); report={"schema_version":"1.0.0","date_utc":date_utc,"generated_at_utc":self.clock().astimezone(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00","Z"),**{key:data[key] for key in ("scope","performance","direction","data_quality")},"provenance":{"snapshot_ids":data["snapshot_ids"],"builder_version":"1.0.0","report_sha256":""}};report["provenance"]["report_sha256"]=sha256(json.dumps(report,sort_keys=True,separators=(",",":"),allow_nan=False).encode()).hexdigest();return report
