from collections.abc import Mapping
from ._helpers import bucket, enum, value
class TrendExtractor:
 def extract(self, evidence: Mapping[str, object]) -> dict[str, object]:
  direction = enum("trend_direction", value(evidence, "trend_direction", value(evidence, "market_state")))
  return {"trend_direction": direction, "trend_strength": bucket(value(evidence, "adx"), "trend_strength", 20, 35, ("WEAK", "MODERATE", "STRONG")), "trend_persistence": bucket(value(evidence, "trend_bars"), "trend_persistence", 3, 8, ("LOW", "MEDIUM", "HIGH")), "higher_tf_alignment": enum("higher_tf_alignment", value(evidence, "higher_tf_alignment"))}
