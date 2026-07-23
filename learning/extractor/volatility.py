from collections.abc import Mapping
from ._helpers import bucket, enum, value
class VolatilityExtractor:
 def extract(self,evidence:Mapping[str,object])->dict[str,object]:
  return {"atr_state":enum("atr_state",value(evidence,"atr_state")),"bb_state":enum("bb_state",value(evidence,"bb_state")),"bb_width_state":enum("bb_width_state",value(evidence,"bb_width_state")),"volatility_level":enum("volatility_level",value(evidence,"volatility_level")),"expansion_state":enum("expansion_state",value(evidence,"expansion_state"))}
