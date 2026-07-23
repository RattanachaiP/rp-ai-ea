from collections.abc import Mapping
from ._helpers import bucket, enum, value
class MomentumExtractor:
 def extract(self, evidence: Mapping[str, object]) -> dict[str, object]:
  rsi=value(evidence,"rsi")
  try: zone="OVERSOLD" if float(rsi)<30 else "LOW" if float(rsi)<45 else "NORMAL" if float(rsi)<=55 else "HIGH" if float(rsi)<70 else "OVERBOUGHT"
  except (TypeError,ValueError): zone="UNKNOWN"
  macd=value(evidence,"macd"); ao=value(evidence,"ao")
  def sign(v, positive, negative):
   try: return positive if float(v)>0 else negative if float(v)<0 else "NEUTRAL"
   except (TypeError,ValueError): return "UNKNOWN"
  return {"rsi_zone":enum("rsi_zone",zone),"macd_state":enum("macd_state",sign(macd,"POSITIVE","NEGATIVE")),"macd_cross":enum("macd_cross",value(evidence,"macd_cross")),"ao_state":enum("ao_state",sign(ao,"BULLISH","BEARISH")),"momentum_strength":bucket(value(evidence,"momentum"),"momentum_strength",0.25,0.75,("WEAK","MODERATE","STRONG"))}
