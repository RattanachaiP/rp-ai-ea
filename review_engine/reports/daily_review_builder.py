from datetime import datetime, timezone
from ..validation.schema_validator import canonical_sha256, validate_snapshot
class DailyReviewBuilder:
 def build(self, date_utc, snapshots, generated_at_utc=None):
  s=sorted(snapshots,key=lambda x:x['snapshot_id']); [validate_snapshot(x) for x in s]; net=[x['outcome']['net_profit'] for x in s]; wins=[x for x in net if x>0]; losses=[x for x in net if x<0]; symbols=sorted({x['trade_identity']['symbol'] for x in s}); dur=[x['timeline']['duration_seconds'] for x in s if x['timeline']['duration_seconds'] is not None]; miss={}
  for x in s:
   for f in x['data_quality']['missing_fields']: miss[f]=miss.get(f,0)+1
  gross=sum(x['outcome']['gross_profit'] for x in s); profit=sum(wins); loss=abs(sum(losses)); p={"wins":len(wins),"losses":len(losses),"breakeven":len(s)-len(wins)-len(losses),"win_rate":len(wins)/len(s) if s else None,"gross_profit":gross,"net_profit":sum(net),"profit_factor":profit/loss if loss else None,"average_win":profit/len(wins) if wins else None,"average_loss":sum(losses)/len(losses) if losses else None,"average_duration_seconds":sum(dur)/len(dur) if dur else None}; d={"buy_trades":sum(x['trade_identity']['side']=='BUY' for x in s),"sell_trades":sum(x['trade_identity']['side']=='SELL' for x in s),"buy_net_profit":sum(x['outcome']['net_profit'] for x in s if x['trade_identity']['side']=='BUY'),"sell_net_profit":sum(x['outcome']['net_profit'] for x in s if x['trade_identity']['side']=='SELL')}; r={"schema_version":"1.0.0","date_utc":date_utc,"generated_at_utc":generated_at_utc or datetime.now(timezone.utc).isoformat(timespec='milliseconds').replace('+00:00','Z'),"scope":{"symbols":symbols,"trade_count":len(s),"complete_snapshot_count":sum(not x['data_quality']['missing_fields'] for x in s),"incomplete_snapshot_count":sum(bool(x['data_quality']['missing_fields']) for x in s)},"performance":p,"direction":d,"data_quality":{"average_completeness_ratio":sum(x['data_quality']['completeness_ratio'] for x in s)/len(s) if s else 0.0,"missing_field_counts":miss,"warnings":[]},"provenance":{"snapshot_ids":[x['snapshot_id'] for x in s],"builder_version":"1.0.0","report_sha256":""}}; r['provenance']['report_sha256']=canonical_sha256(r); return r

 def write(self, root, report):
  """Atomically persist a deterministic review without touching source artifacts."""
  import json, os
  from pathlib import Path
  from ..validation.schema_validator import validate_daily_review
  validate_daily_review(report); path=Path(root)/'daily'/report['date_utc'].replace('-', '/')/'daily_review.json'; path.parent.mkdir(parents=True,exist_ok=True); tmp=path.with_suffix('.json.tmp'); data=json.dumps(report,sort_keys=True,separators=(',',':')).encode()
  with open(tmp,'wb') as f: f.write(data); f.flush(); os.fsync(f.fileno())
  os.replace(tmp,path); return path
