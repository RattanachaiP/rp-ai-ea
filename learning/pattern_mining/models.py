"""Immutable contracts emitted by PR175."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from math import isfinite
from typing import Any, Mapping
from uuid import UUID

from learning.common.immutable import freeze, thaw


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


def _number(value: object) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool) and isfinite(value)


@dataclass(frozen=True)
class CandidatePattern:
    """A mining result only; it carries no learning or runtime authority."""

    pattern_uuid: str
    pattern_hash: str
    knowledge_uuid: str
    knowledge_version: str
    feature_signature: str
    market_context: Mapping[str, Any] = field(default_factory=dict)
    entry_context: Mapping[str, Any] = field(default_factory=dict)
    exit_context: Mapping[str, Any] = field(default_factory=dict)
    risk_context: Mapping[str, Any] = field(default_factory=dict)
    sample_count: int = 0
    win_count: int = 0
    loss_count: int = 0
    neutral_count: int = 0
    support: float = 0.0
    expectancy: float = 0.0
    confidence: float = 0.0
    created_at: str = ""

    def __post_init__(self) -> None:
        counts = (self.sample_count, self.win_count, self.loss_count, self.neutral_count)
        contexts = (self.market_context, self.entry_context, self.exit_context, self.risk_context)
        valid_hash = isinstance(self.pattern_hash, str) and len(self.pattern_hash) == 64 and all(c in "0123456789abcdef" for c in self.pattern_hash)
        if (not _uuid(self.pattern_uuid) or not valid_hash or not _uuid(self.knowledge_uuid)
                or not self.knowledge_version or not self.feature_signature
                or not all(isinstance(x, int) and not isinstance(x, bool) and x >= 0 for x in counts)
                or self.win_count + self.loss_count + self.neutral_count != self.sample_count
                or not all(_number(x) for x in (self.support, self.expectancy, self.confidence))
                or not 0 <= self.support <= 1 or not 0 <= self.confidence <= 1
                or not _timestamp(self.created_at) or not all(isinstance(x, Mapping) for x in contexts)):
            raise ValueError("INVALID_CANDIDATE_PATTERN")
        for name in ("market_context", "entry_context", "exit_context", "risk_context"):
            object.__setattr__(self, name, freeze(dict(getattr(self, name))))
        object.__setattr__(self, "support", float(self.support))
        object.__setattr__(self, "expectancy", float(self.expectancy))
        object.__setattr__(self, "confidence", float(self.confidence))

    def to_dict(self) -> dict[str, Any]:
        return {name: thaw(getattr(self, name)) for name in self.__dataclass_fields__}


@dataclass(frozen=True)
class PatternMiningReport:
    report_uuid: str
    policy_uuid: str
    candidate_patterns: tuple[CandidatePattern, ...]
    pattern_count: int
    statistics_summary: Mapping[str, Any]
    generated_at: str
    advisory_only: bool = True

    def __post_init__(self) -> None:
        patterns = tuple(self.candidate_patterns)
        if (not _uuid(self.report_uuid) or not _uuid(self.policy_uuid)
                or self.pattern_count != len(patterns) or not patterns
                or not isinstance(self.statistics_summary, Mapping)
                or not _timestamp(self.generated_at) or self.advisory_only is not True):
            raise ValueError("INVALID_PATTERN_MINING_REPORT")
        object.__setattr__(self, "candidate_patterns", patterns)
        object.__setattr__(self, "statistics_summary", freeze(dict(self.statistics_summary)))

    def to_dict(self) -> dict[str, Any]:
        return {
            "report_uuid": self.report_uuid,
            "policy_uuid": self.policy_uuid,
            "candidate_patterns": [pattern.to_dict() for pattern in self.candidate_patterns],
            "pattern_count": self.pattern_count,
            "statistics_summary": thaw(self.statistics_summary),
            "generated_at": self.generated_at,
            "advisory_only": self.advisory_only,
        }
