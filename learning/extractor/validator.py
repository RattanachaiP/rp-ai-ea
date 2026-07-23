from __future__ import annotations
import math
from .feature_vector import FeatureVector
from .registry import FeatureRegistry
class FeatureValidationError(ValueError): pass
class FeatureVectorValidator:
 SCHEMA_VERSION="1.0"
 def validate(self, vector: FeatureVector) -> None:
  if vector.schema_version != self.SCHEMA_VERSION: raise FeatureValidationError("INVALID_SCHEMA_VERSION")
  if not vector.uuid or not vector.trade_uuid: raise FeatureValidationError("IDENTITY_REQUIRED")
  names=list(vector.features)
  if len(names)!=len(set(names)): raise FeatureValidationError("DUPLICATE_FEATURE")
  for name, feature_value in vector.features.items():
   try: definition=FeatureRegistry.get(name)
   except KeyError as error: raise FeatureValidationError("UNKNOWN_FEATURE:"+name) from error
   if definition.type == "ENUM" and feature_value not in definition.allowed_values: raise FeatureValidationError("INVALID_ENUM:"+name)
   if definition.type == "BOOLEAN" and type(feature_value) is not bool: raise FeatureValidationError("INVALID_BOOLEAN:"+name)
   if definition.type == "NUMBER" and (type(feature_value) not in (int,float) or not math.isfinite(feature_value)): raise FeatureValidationError("INVALID_NUMBER:"+name)
