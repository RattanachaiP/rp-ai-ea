from __future__ import annotations
from .feature_dictionary import FEATURE_DEFINITIONS, FeatureDefinition
class FeatureRegistry:
    """Read-only single source of truth for feature definitions."""
    _definitions = {definition.name: definition for definition in FEATURE_DEFINITIONS}
    @classmethod
    def get(cls, name: str) -> FeatureDefinition:
        try: return cls._definitions[name]
        except KeyError as error: raise KeyError(f"UNKNOWN_FEATURE:{name}") from error
    @classmethod
    def all(cls) -> tuple[FeatureDefinition, ...]: return tuple(cls._definitions.values())
