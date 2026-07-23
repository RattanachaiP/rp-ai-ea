"""The sole Pattern -> Verified Knowledge promotion boundary."""
from __future__ import annotations
from collections.abc import Mapping
from dataclasses import dataclass
from .schema import ValidationResult
from learning.pattern.candidate import CandidatePattern
from .immutable import freeze, thaw

@dataclass(frozen=True)
class VerifiedKnowledge:
    pattern_uuid: str
    conditions: Mapping[str, object]
    statistics: Mapping[str, float | int]
    validation: ValidationResult

    def __post_init__(self) -> None:
        object.__setattr__(self, "conditions", freeze(self.conditions))
        object.__setattr__(self, "statistics", freeze(self.statistics))

    def to_dict(self) -> dict[str, object]:
        return {"pattern_uuid": self.pattern_uuid, "conditions": thaw(self.conditions), "statistics": thaw(self.statistics),
                "validation": self.validation.to_dict()}

def promote(pattern: CandidatePattern, result: ValidationResult) -> VerifiedKnowledge:
    if result.pattern_uuid != pattern.pattern_uuid: raise ValueError("PATTERN_VALIDATION_MISMATCH")
    if result.status != "VERIFIED": raise ValueError("ONLY_VERIFIED_PATTERNS_MAY_BECOME_KNOWLEDGE")
    return VerifiedKnowledge(pattern.pattern_uuid, pattern.conditions, pattern.statistics, result)
