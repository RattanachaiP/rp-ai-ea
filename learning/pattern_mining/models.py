"""Immutable, self-describing contracts for PR175 offline pattern mining."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from math import isfinite
from typing import Any, Mapping
from uuid import UUID

from learning.common.immutable import freeze, thaw


def _uuid(value: object) -> bool:
    try:
        UUID(str(value)); return True
    except (TypeError, ValueError, AttributeError):
        return False


def _digest(value: object) -> bool:
    return isinstance(value, str) and len(value) == 64 and all(c in "0123456789abcdef" for c in value)


def _timestamp(value: object) -> bool:
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00")).tzinfo is not None
    except (TypeError, ValueError, AttributeError):
        return False


def _number(value: object) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool) and isfinite(value)


def _json_safe(value: Any) -> bool:
    if value is None or isinstance(value, (str, bool)) or _number(value): return True
    if isinstance(value, (tuple, list)): return all(_json_safe(x) for x in value)
    if isinstance(value, Mapping): return all(isinstance(k, str) and _json_safe(v) for k, v in value.items())
    return False


@dataclass(frozen=True)
class ApprovedPatternMiningSample:
    sample_uuid: str
    features: Mapping[str, Any]
    market_context: Mapping[str, Any]
    entry_context: Mapping[str, Any]
    exit_context: Mapping[str, Any]
    risk_context: Mapping[str, Any]
    outcome: float
    timestamp: str

    def __post_init__(self) -> None:
        values = (self.features, self.market_context, self.entry_context, self.exit_context, self.risk_context)
        if not _uuid(self.sample_uuid) or not self.features or not all(isinstance(x, Mapping) and _json_safe(x) for x in values) or not _number(self.outcome) or not _timestamp(self.timestamp):
            raise ValueError("INVALID_APPROVED_PATTERN_MINING_SAMPLE")
        for name in ("features", "market_context", "entry_context", "exit_context", "risk_context"):
            object.__setattr__(self, name, freeze(dict(getattr(self, name))))
        object.__setattr__(self, "outcome", float(self.outcome))

    def to_dict(self) -> dict[str, Any]:
        return {name: thaw(getattr(self, name)) for name in self.__dataclass_fields__}


@dataclass(frozen=True)
class ApprovedPatternMiningEvidenceEnvelope:
    envelope_uuid: str
    policy_uuid: str
    policy_version: str
    source_attribution_uuid: str
    source_digest: str
    replay_digest: str
    knowledge_uuid: str
    knowledge_version: str
    outcome_contract: tuple[str, str]
    approved_samples: tuple[ApprovedPatternMiningSample, ...]
    generated_at: str
    advisory_only: bool = True

    def __post_init__(self) -> None:
        samples = tuple(self.approved_samples)
        contract = tuple(self.outcome_contract)
        if (not all(_uuid(x) for x in (self.envelope_uuid, self.policy_uuid, self.source_attribution_uuid))
                or not self.policy_version or not self.knowledge_version or not _uuid(self.knowledge_uuid)
                or not _digest(self.source_digest) or not _digest(self.replay_digest)
                or len(contract) != 2 or not all(isinstance(x, str) and x for x in contract)
                or not samples or not all(isinstance(x, ApprovedPatternMiningSample) for x in samples)
                or not _timestamp(self.generated_at) or self.advisory_only is not True):
            raise ValueError("INVALID_APPROVED_PATTERN_MINING_EVIDENCE_ENVELOPE")
        object.__setattr__(self, "outcome_contract", contract)
        object.__setattr__(self, "approved_samples", samples)

    def to_dict(self) -> dict[str, Any]:
        result = {name: thaw(getattr(self, name)) for name in self.__dataclass_fields__}
        result["outcome_contract"] = list(self.outcome_contract)
        result["approved_samples"] = [x.to_dict() for x in self.approved_samples]
        return result


@dataclass(frozen=True)
class PatternMiningConfig:
    allowed_feature_fields: tuple[str, ...] = ()
    allowed_context_fields: Mapping[str, tuple[str, ...]] = field(default_factory=dict)
    excluded_volatile_fields: tuple[str, ...] = ("timestamp", "price", "bid", "ask", "atr")
    rsi_bucket_boundaries: tuple[float, float] = (30.0, 70.0)

    def __post_init__(self) -> None:
        allowed = tuple(self.allowed_feature_fields); excluded = tuple(self.excluded_volatile_fields)
        contexts = {str(k): tuple(v) for k, v in self.allowed_context_fields.items()}
        boundaries = tuple(self.rsi_bucket_boundaries)
        if (any(not isinstance(x, str) or not x for x in allowed + excluded)
                or any(k not in {"market_context", "entry_context", "exit_context", "risk_context"} or any(not isinstance(x, str) or not x for x in v) for k, v in contexts.items())
                or len(boundaries) != 2 or not all(_number(x) for x in boundaries) or boundaries[0] >= boundaries[1]):
            raise ValueError("INVALID_PATTERN_MINING_CONFIG")
        object.__setattr__(self, "allowed_feature_fields", allowed)
        object.__setattr__(self, "excluded_volatile_fields", excluded)
        object.__setattr__(self, "allowed_context_fields", freeze(contexts))
        object.__setattr__(self, "rsi_bucket_boundaries", (float(boundaries[0]), float(boundaries[1])))

    def to_dict(self) -> dict[str, Any]:
        return {"allowed_feature_fields": list(self.allowed_feature_fields), "allowed_context_fields": thaw(self.allowed_context_fields),
                "excluded_volatile_fields": list(self.excluded_volatile_fields), "rsi_bucket_boundaries": list(self.rsi_bucket_boundaries)}


@dataclass(frozen=True)
class CandidatePattern:
    pattern_uuid: str; pattern_hash: str
    policy_uuid: str; policy_version: str; source_attribution_uuid: str; replay_digest: str; engine_version: str
    knowledge_uuid: str; knowledge_version: str; outcome_contract: tuple[str, str]; feature_signature: str
    market_context: Mapping[str, Any]; entry_context: Mapping[str, Any]; exit_context: Mapping[str, Any]; risk_context: Mapping[str, Any]
    sample_count: int; win_count: int; loss_count: int; neutral_count: int
    support: float; expectancy: float; confidence: float; created_at: str; advisory_only: bool = True

    def __post_init__(self) -> None:
        counts = (self.sample_count, self.win_count, self.loss_count, self.neutral_count)
        contexts = (self.market_context, self.entry_context, self.exit_context, self.risk_context)
        contract = tuple(self.outcome_contract)
        if (not all(_uuid(x) for x in (self.pattern_uuid, self.policy_uuid, self.source_attribution_uuid, self.knowledge_uuid))
                or not _digest(self.pattern_hash) or not _digest(self.replay_digest)
                or not all(isinstance(x, str) and x for x in (self.policy_version, self.engine_version, self.knowledge_version, self.feature_signature))
                or len(contract) != 2 or not all(isinstance(x, str) and x for x in contract)
                or not all(isinstance(x, int) and not isinstance(x, bool) and x >= 0 for x in counts)
                or sum(counts[1:]) != counts[0] or not all(_number(x) for x in (self.support, self.expectancy, self.confidence))
                or not 0 <= self.support <= 1 or not 0 <= self.confidence <= 1
                or not all(isinstance(x, Mapping) and _json_safe(x) for x in contexts)
                or not _timestamp(self.created_at) or self.advisory_only is not True):
            raise ValueError("INVALID_CANDIDATE_PATTERN")
        object.__setattr__(self, "outcome_contract", contract)
        for name in ("market_context", "entry_context", "exit_context", "risk_context"):
            object.__setattr__(self, name, freeze(dict(getattr(self, name))))

    def to_dict(self) -> dict[str, Any]: return {name: thaw(getattr(self, name)) for name in self.__dataclass_fields__}


@dataclass(frozen=True)
class PatternMiningReport:
    report_uuid: str; policy_uuid: str; engine_version: str
    candidate_patterns: tuple[CandidatePattern, ...]; pattern_count: int
    statistics_summary: Mapping[str, Any]; generated_at: str; advisory_only: bool = True

    def __post_init__(self) -> None:
        patterns = tuple(self.candidate_patterns)
        expected = {"sample_count": sum(x.sample_count for x in patterns), "win_count": sum(x.win_count for x in patterns),
                    "loss_count": sum(x.loss_count for x in patterns), "neutral_count": sum(x.neutral_count for x in patterns),
                    "engine_version": self.engine_version}
        if (not _uuid(self.report_uuid) or not _uuid(self.policy_uuid) or not self.engine_version or not patterns
                or self.pattern_count != len(patterns) or dict(self.statistics_summary) != expected
                or any(x.policy_uuid != self.policy_uuid or x.engine_version != self.engine_version for x in patterns)
                or not _timestamp(self.generated_at) or self.advisory_only is not True):
            raise ValueError("INVALID_PATTERN_MINING_REPORT")
        object.__setattr__(self, "candidate_patterns", patterns); object.__setattr__(self, "statistics_summary", freeze(expected))

    def to_dict(self) -> dict[str, Any]:
        return {"report_uuid": self.report_uuid, "policy_uuid": self.policy_uuid, "engine_version": self.engine_version,
                "candidate_patterns": [x.to_dict() for x in self.candidate_patterns], "pattern_count": self.pattern_count,
                "statistics_summary": thaw(self.statistics_summary), "generated_at": self.generated_at, "advisory_only": self.advisory_only}
