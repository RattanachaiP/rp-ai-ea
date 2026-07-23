from __future__ import annotations
from .aggregation import finite
def detect_conflicts(records, config):
 findings=[]
 def key(r): return (tuple(sorted(r.applicable_symbols)),tuple(sorted(r.applicable_sessions)),tuple(sorted(r.applicable_market_states)))
 groups={}
 for r in records: groups.setdefault(key(r),[]).append(r)
 for condition, rows in sorted(groups.items(),key=lambda x:repr(x[0])):
  active=[r for r in rows if r.knowledge_status=="ACTIVE"]
  for i,left in enumerate(active):
   for right in active[i+1:]:
    win=abs((finite(left.verified_win_rate) or 0)-(finite(right.verified_win_rate) or 0)); rr=abs((finite(left.average_rr) or 0)-(finite(right.average_rr) or 0))
    if win>=config.conflict_win_rate_delta or rr>=config.conflict_rr_delta:
     severity="HIGH" if win>=2*config.conflict_win_rate_delta or rr>=2*config.conflict_rr_delta else "MEDIUM"
     findings.append({"severity":severity,"condition":{"symbols":list(condition[0]),"sessions":list(condition[1]),"market_states":list(condition[2])},"knowledge_ids":sorted((left.knowledge_uuid,right.knowledge_uuid)),"win_rate_delta":win,"average_rr_delta":rr})
 return tuple(sorted(findings,key=lambda x:(x["severity"],x["knowledge_ids"])))[:config.maximum_findings]
