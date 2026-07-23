"""The sole Pattern -> Verified Knowledge promotion boundary."""
from __future__ import annotations
from dataclasses import dataclass
from .schema import ValidationResult
from learning.pattern.candidate import CandidatePattern

@dataclass(frozen=True)
class VerifiedKnowledge:
    pattern_uuid: str
    conditions: dict[str, object]
    statistics: dict[str, float | int]
    validation: ValidationResult
    def to_dict(self) -> dict[str, object]:
        return {"pattern_uuid": self.pattern_uuid, "conditions": self.conditions, "statistics": self.statistics,
                "validation": self.validation.to_dict()}

def promote(pattern: CandidatePattern, result: ValidationResult) -> VerifiedKnowledge:
    if result.pattern_uuid != pattern.pattern_uuid: raise ValueError("PATTERN_VALIDATION_MISMATCH")
    if result.status != "VERIFIED": raise ValueError("ONLY_VERIFIED_PATTERNS_MAY_BECOME_KNOWLEDGE")
    return VerifiedKnowledge(pattern.pattern_uuid, dict(pattern.conditions), dict(pattern.statistics), result)
