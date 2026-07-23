"""Deterministic transformation from immutable evidence to a validated vector."""
from __future__ import annotations
from collections.abc import Mapping
from typing import Callable
from .feature_vector import FeatureVector
from .trend import TrendExtractor
from .momentum import MomentumExtractor
from .volatility import VolatilityExtractor
from .structure import StructureExtractor
from .liquidity import LiquidityExtractor
from .session import SessionExtractor
from .execution import ExecutionExtractor
from .outcome import OutcomeExtractor
from .validator import FeatureVectorValidator
class FeatureExtractor:
 def __init__(self, *, clock: Callable[[], str] | None = None):
  self._extractors=(TrendExtractor(),MomentumExtractor(),VolatilityExtractor(),StructureExtractor(),LiquidityExtractor(),SessionExtractor(),ExecutionExtractor(),OutcomeExtractor())
  self._clock=clock
  self._validator=FeatureVectorValidator()
 def extract(self,evidence:Mapping[str,object])->FeatureVector:
  trade_uuid=str(evidence.get("trade_uuid") or evidence.get("trade_id") or "")
  if not trade_uuid: raise ValueError("TRADE_UUID_REQUIRED")
  features={}
  for extractor in self._extractors: features.update(extractor.extract(evidence))
  vector=FeatureVector.create(trade_uuid,features,created_at=self._clock() if self._clock else None)
  self._validator.validate(vector)
  return vector
