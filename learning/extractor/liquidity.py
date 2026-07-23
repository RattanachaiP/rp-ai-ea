from collections.abc import Mapping
from ._helpers import enum, value
class LiquidityExtractor:
 def extract(self,evidence:Mapping[str,object])->dict[str,object]:
  def number(n):
   try:return float(value(evidence,n))
   except (TypeError,ValueError):return 0.0
  return {"liquidity_zone":enum("liquidity_zone",value(evidence,"liquidity_zone")),"vwap_position":enum("vwap_position",value(evidence,"vwap_position")),"distance_from_vwap":number("distance_from_vwap"),"support_distance":number("support_distance"),"resistance_distance":number("resistance_distance")}
