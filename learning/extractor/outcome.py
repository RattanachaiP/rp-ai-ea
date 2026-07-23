from collections.abc import Mapping
from ._helpers import bucket, enum, value
class OutcomeExtractor:
 def extract(self,evidence:Mapping[str,object])->dict[str,object]:
  profit=value(evidence,"net_profit")
  try: p=float(profit); pb="LARGE_WIN" if p>=100 else "SMALL_WIN" if p>0 else "LOSS" if p<0 else "BREAKEVEN"
  except (TypeError,ValueError): pb="UNKNOWN"
  return {"win_loss":enum("win_loss",value(evidence,"win_loss",value(evidence,"result"))),"profit_bucket":enum("profit_bucket",pb),"holding_bucket":bucket(value(evidence,"duration_seconds"),"holding_bucket",300,3600,("SHORT","MEDIUM","LONG")),"mae_bucket":bucket(value(evidence,"mae"),"mae_bucket",10,50,("LOW","MEDIUM","HIGH")),"mfe_bucket":bucket(value(evidence,"mfe"),"mfe_bucket",10,50,("LOW","MEDIUM","HIGH"))}
