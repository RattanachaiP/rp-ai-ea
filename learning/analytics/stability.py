from __future__ import annotations
from .aggregation import finite
FIELDS=("sample_count","verified_win_rate","average_rr","average_profit","average_loss","mae","mfe","consistency","statistical_significance")
def stability(records, config):
 out=[]
 by={}
 for r in records: by.setdefault(r.pattern_uuid,[]).append(r)
 for lineage, items in sorted(by.items()):
  items=sorted(items,key=lambda r:(r.knowledge_version,r.created_timestamp,r.knowledge_uuid))
  if len(items)<2: out.append({"pattern_uuid":lineage,"classification":"INSUFFICIENT_HISTORY","knowledge_ids":[items[0].knowledge_uuid]}); continue
  old,new=items[-2:]; deltas={}
  for field in FIELDS:
   a,b=finite(getattr(old,field,None)),finite(getattr(new,field,None))
   if a is not None and b is not None: deltas[field]=b-a
  wr,rr=deltas.get("verified_win_rate",0),deltas.get("average_rr",0)
  classification="IMPROVING" if wr>=config.improving_win_rate_delta or rr>=config.improving_rr_delta else "DEGRADING" if wr<=-config.improving_win_rate_delta or rr<=-config.improving_rr_delta else "STABLE"
  out.append({"pattern_uuid":lineage,"previous_knowledge_uuid":old.knowledge_uuid,"knowledge_uuid":new.knowledge_uuid,"deltas":deltas,"classification":classification})
 return {"lineages":out}
