from collections.abc import Mapping
from ._helpers import bucket, enum, value
class ExecutionExtractor:
 def extract(self,evidence:Mapping[str,object])->dict[str,object]:
  def number(n):
   try:return float(value(evidence,n))
   except (TypeError,ValueError):return 0.0
  return {"spread_state":enum("spread_state",value(evidence,"spread_state")),"sl_distance":number("sl_distance"),"tp_distance":number("tp_distance"),"rr_bucket":bucket(value(evidence,"rr"),"rr_bucket",1,2,("LOW","MEDIUM","HIGH")),"entry_delay":enum("entry_delay",value(evidence,"entry_delay")),"execution_quality":enum("execution_quality",value(evidence,"execution_quality"))}
