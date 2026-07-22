import hashlib,json
from review_engine.collector.event_types import utc_now
from review_engine.validation import validate_daily_review
def _hash(value): return hashlib.sha256(json.dumps(value,sort_keys=True,separators=(",",":")).encode()).hexdigest()
class DailyReviewBuilder:
    version="1.0.0"
    def build(self,date_utc,snapshots):
        net=[s["outcome"]["net_profit"] for s in snapshots]; wins=[x for x in net if x>0]; losses=[x for x in net if x<0]; zero=[x for x in net if x==0]
        complete=[s for s in snapshots if not s["data_quality"]["missing_fields"]]; symbols=sorted({s["trade_identity"]["symbol"] for s in snapshots if s["trade_identity"]["symbol"]})
        durations=[s["timeline"]["duration_seconds"] for s in snapshots if s["timeline"]["duration_seconds"] is not None]
        missing={}
        for s in snapshots:
            for field in s["data_quality"]["missing_fields"]: missing[field]=missing.get(field,0)+1
        buy=[s for s in snapshots if s["trade_identity"]["side"]=="BUY"]; sell=[s for s in snapshots if s["trade_identity"]["side"]=="SELL"]
        r={"schema_version":"1.0.0","date_utc":date_utc,"generated_at_utc":utc_now(),"scope":{"symbols":symbols,"trade_count":len(snapshots),"complete_snapshot_count":len(complete),"incomplete_snapshot_count":len(snapshots)-len(complete)},"performance":{"wins":len(wins),"losses":len(losses),"breakeven":len(zero),"win_rate":len(wins)/len(net) if net else None,"gross_profit":sum(s["outcome"]["gross_profit"] for s in snapshots),"net_profit":sum(net),"profit_factor":sum(wins)/abs(sum(losses)) if losses else None,"average_win":sum(wins)/len(wins) if wins else None,"average_loss":sum(losses)/len(losses) if losses else None,"average_duration_seconds":sum(durations)/len(durations) if durations else None},"direction":{"buy_trades":len(buy),"sell_trades":len(sell),"buy_net_profit":sum(s["outcome"]["net_profit"] for s in buy),"sell_net_profit":sum(s["outcome"]["net_profit"] for s in sell)},"data_quality":{"average_completeness_ratio":sum(s["data_quality"]["completeness_ratio"] for s in snapshots)/len(snapshots) if snapshots else 0.0,"missing_field_counts":missing,"warnings":[]},"provenance":{"snapshot_ids":[s["snapshot_id"] for s in snapshots],"builder_version":self.version,"report_sha256":""}}
        r["provenance"]["report_sha256"]=_hash({**r,"provenance":{**r["provenance"],"report_sha256":""}}); return validate_daily_review(r)
