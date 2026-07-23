from collections.abc import Mapping
from ._helpers import boolean, enum, value
class StructureExtractor:
 def extract(self,evidence:Mapping[str,object])->dict[str,object]:
  return {"market_phase":enum("market_phase",value(evidence,"market_phase",value(evidence,"classification",value(evidence,"market_state")))),"bos_detected":boolean(value(evidence,"bos_detected")),"choch_detected":boolean(value(evidence,"choch_detected")),"swing_position":enum("swing_position",value(evidence,"swing_position")),"structure_quality":enum("structure_quality",value(evidence,"structure_quality"))}
