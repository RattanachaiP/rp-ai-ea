"""Immutable contracts emitted by PR174's advisory learning gate."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from math import isfinite
from typing import Any, Mapping
from uuid import UUID

from learning.common.immutable import freeze, thaw

_STATES = {"NOT_ELIGIBLE", "REQUIRES_MORE_DATA", "ELIGIBLE_FOR_PATTERN_MINING"}


def _uuid(value: object) -> bool:
    try:
        UUID(str(value))
        return True
    except (TypeError, ValueError, AttributeError):
        return False


def _timestamp(value: object) -> bool:
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00")).tzinfo is not None
    except (TypeError, ValueError, AttributeError):
        return False


def _finite(value: object) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool) and isfinite(value)


@dataclass(frozen=True)
class GovernedLearningPolicyReport:
    """An immutable, advisory classification for exactly one knowledge version."""

    policy_uuid: str
    knowledge_uuid: str
    knowledge_version: str
    eligibility_score: float
    eligibility_state: str
    sample_quality: Mapping[str, Any] = field(default_factory=dict)
    validation_summary: Mapping[str, Any] = field(default_factory=dict)
    evaluation_summary: Mapping[str, Any] = field(default_factory=dict)
    generated_at: str = ""

    def __post_init__(self) -> None:
        if (
            not _uuid(self.policy_uuid)
            or not _uuid(self.knowledge_uuid)
            or not isinstance(self.knowledge_version, str)
            or not self.knowledge_version
            or not _finite(self.eligibility_score)
            or not 0.0 <= float(self.eligibility_score) <= 1.0
            or self.eligibility_state not in _STATES
            or not _timestamp(self.generated_at)
            or any(not isinstance(getattr(self, name), Mapping) for name in (
                "sample_quality", "validation_summary", "evaluation_summary"
            ))
        ):
            raise ValueError("INVALID_GOVERNED_LEARNING_POLICY_REPORT")
        object.__setattr__(self, "eligibility_score", float(self.eligibility_score))
        for name in ("sample_quality", "validation_summary", "evaluation_summary"):
            object.__setattr__(self, name, freeze(dict(getattr(self, name))))

    def to_dict(self) -> dict[str, Any]:
        return {
            name: thaw(getattr(self, name))
            for name in self.__dataclass_fields__
        }
