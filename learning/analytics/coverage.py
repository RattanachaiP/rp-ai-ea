from __future__ import annotations

def coverage(records, config):
    dimensions={"symbol":"applicable_symbols","session":"applicable_sessions","market_state":"applicable_market_states","knowledge_version":"knowledge_version","status":"knowledge_status"}
    groups={}
    for name, attr in dimensions.items():
        counts={}
        for r in records:
            values=getattr(r,attr,())
            if not isinstance(values,(tuple,list)): values=(values,)
            for value in values: counts[str(value)]=counts.get(str(value),0)+1
        groups[name]={k:counts[k] for k in sorted(counts)}
    condition={}
    for r in records:
        key="|".join([",".join(sorted(getattr(r,"applicable_symbols",()))), ",".join(sorted(getattr(r,"applicable_sessions",()))), ",".join(sorted(getattr(r,"applicable_market_states",())))])
        condition.setdefault(key,[]).append(r.knowledge_uuid)
    return {"by_dimension":groups,"low_coverage_conditions":[k for k,v in sorted(condition.items()) if len(v)<config.low_coverage_threshold],"highly_concentrated_conditions":[k for k,v in sorted(condition.items()) if len(v)>=config.concentration_threshold],"duplicate_condition_coverage":[{"condition":k,"knowledge_ids":sorted(v)} for k,v in sorted(condition.items()) if len(v)>1],"uncovered_conditions":[]}
