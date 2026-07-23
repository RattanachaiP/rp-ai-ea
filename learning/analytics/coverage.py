"""Deterministic coverage; no expected universe is inferred in v1."""
from __future__ import annotations
def coverage(records, config):
    dimensions={"symbol":"applicable_symbols","session":"applicable_sessions","market_state":"applicable_market_states","knowledge_version":"knowledge_version","status":"knowledge_status"}; groups={}
    for name, attr in dimensions.items():
        counts={}
        for record in records:
            values=getattr(record,attr,()); values=values if isinstance(values,(tuple,list)) else (values,)
            for value in values: counts[str(value)]=counts.get(str(value),0)+1
        groups[name]={key:counts[key] for key in sorted(counts)}
    conditions={}
    for record in records:
        key=(tuple(sorted(record.applicable_symbols)),tuple(sorted(record.applicable_sessions)),tuple(sorted(record.applicable_market_states)))
        conditions.setdefault(key,[]).append(record.knowledge_uuid)
    def item(key, ids): return {"condition":{"symbols":list(key[0]),"sessions":list(key[1]),"market_states":list(key[2])},"record_count":len(ids),"knowledge_ids":sorted(ids)}
    return {"by_dimension":groups,"low_coverage_conditions":[item(k,v) for k,v in sorted(conditions.items(),key=repr) if len(v)<config.low_coverage_threshold],"highly_concentrated_conditions":[item(k,v) for k,v in sorted(conditions.items(),key=repr) if len(v)>=config.concentration_threshold],"duplicate_condition_coverage":[item(k,v) for k,v in sorted(conditions.items(),key=repr) if len(v)>1],"uncovered_conditions":None,"uncovered_conditions_status":"NOT_COMPUTED_NO_EXPECTED_UNIVERSE"}
