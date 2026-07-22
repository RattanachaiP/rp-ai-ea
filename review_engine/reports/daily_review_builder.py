from datetime import datetime, timezone
import hashlib,json
from typing import Iterable, Mapping
from review_engine.validation import validate_snapshot, validate_daily_review
class StatisticsAggregator:
 def aggregate(self, snapshots): return list(snapshots)
class PerformanceCalculator:
 def calculate(self, snapshots):
  net=[x['outcome']['net_profit'] for x in snapshots]; wins=[n for n in net if n>0]; losses=[n for n in net if n<0]
  durations=[x['timeline']['duration_seconds'] for x in snapshots if x['timeline']['duration_seconds'] is not None]
  return {'wins':len(wins),'losses':len(losses),'breakeven':len(net)-len(wins)-len(losses),'win_rate':len(wins)/len(net) if net else None,'gross_profit':sum(x['outcome']['gross_profit'] for x in snapshots),'net_profit':sum(net),'profit_factor':sum(wins)/abs(sum(losses)) if losses else None,'average_win':sum(wins)/len(wins) if wins else None,'average_loss':sum(losses)/len(losses) if losses else None,'average_duration_seconds':sum(durations)/len(durations) if durations else None}
class DirectionCalculator:
 def calculate(self,snapshots):
  buy=[x for x in snapshots if x['trade_identity']['side']=='BUY']; sell=[x for x in snapshots if x['trade_identity']['side']=='SELL']
  return {'buy_trades':len(buy),'sell_trades':len(sell),'buy_net_profit':sum(x['outcome']['net_profit'] for x in buy),'sell_net_profit':sum(x['outcome']['net_profit'] for x in sell)}
class DataQualityCalculator:
 def calculate(self,snapshots):
  counts={}; warnings=[]
  for s in snapshots:
   for item in s['data_quality']['missing_fields']: counts[item]=counts.get(item,0)+1
   warnings.extend(s['data_quality']['warnings'])
  return {'average_completeness_ratio':sum(x['data_quality']['completeness_ratio'] for x in snapshots)/len(snapshots) if snapshots else 0.0,'missing_field_counts':counts,'warnings':sorted(set(warnings))}
class DailyReviewBuilder:
 builder_version='1.0.0'
 def __init__(self, statistics=None, performance=None, direction=None, data_quality=None): self.statistics=statistics or StatisticsAggregator();self.performance=performance or PerformanceCalculator();self.direction=direction or DirectionCalculator();self.data_quality=data_quality or DataQualityCalculator()
 def build(self, date_utc: str, snapshots: Iterable[Mapping]):
  snapshots=self.statistics.aggregate(sorted((dict(x) for x in snapshots),key=lambda x:x['snapshot_id']))
  for s in snapshots: validate_snapshot(s)
  complete=[x for x in snapshots if not x['data_quality']['missing_fields']]
  review={'schema_version':'1.0.0','date_utc':date_utc,'generated_at_utc':datetime.now(timezone.utc).isoformat(timespec='milliseconds').replace('+00:00','Z'),'scope':{'symbols':sorted(set(x['trade_identity']['symbol'] for x in snapshots)),'trade_count':len(snapshots),'complete_snapshot_count':len(complete),'incomplete_snapshot_count':len(snapshots)-len(complete)},'performance':self.performance.calculate(snapshots),'direction':self.direction.calculate(snapshots),'data_quality':self.data_quality.calculate(snapshots),'provenance':{'snapshot_ids':[x['snapshot_id'] for x in snapshots],'builder_version':self.builder_version,'report_sha256':''}}
  plain=json.loads(json.dumps(review)); plain['provenance']['report_sha256']=''; review['provenance']['report_sha256']=hashlib.sha256(json.dumps(plain,sort_keys=True,separators=(',',':')).encode()).hexdigest(); validate_daily_review(review); return review
