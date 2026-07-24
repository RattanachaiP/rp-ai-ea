"""Immutable, read-only contracts for PR173 Knowledge Analytics."""
from __future__ import annotations
from dataclasses import dataclass, field, asdict
from typing import Any, Mapping
from learning.common.immutable import freeze, thaw

@dataclass(frozen=True)
class FeatureContribution:
    feature_id: str
    sample_count: int
    success_count: int
    failure_count: int
    average_outcome: float
    contribution: float
    def to_dict(self): return asdict(self)

@dataclass(frozen=True)
class IndicatorContribution:
    indicator_id: str
    sample_count: int
    contribution: float
    success_rate: float
    def to_dict(self): return asdict(self)

@dataclass(frozen=True)
class RiskContribution:
    risk_factor: str
    sample_count: int
    average_outcome: float
    failure_rate: float
    def to_dict(self): return asdict(self)

@dataclass(frozen=True)
class FailurePattern:
    pattern_id: str
    conditions: tuple[str, ...]
    occurrence_count: int
    failure_rate: float
    def to_dict(self): return asdict(self)

@dataclass(frozen=True)
class SuccessPattern:
    pattern_id: str
    conditions: tuple[str, ...]
    occurrence_count: int
    success_rate: float
    def to_dict(self): return asdict(self)

@dataclass(frozen=True)
class KnowledgePerformanceProfile:
    knowledge_uuid: str
    knowledge_version: str
    sample_count: int
    wins: int
    losses: int
    win_rate: float
    total_outcome: float
    average_outcome: float
    def to_dict(self): return asdict(self)

@dataclass(frozen=True)
class MarketRegimeProfile:
    regime_id: str
    sample_count: int
    wins: int
    losses: int
    average_outcome: float
    def to_dict(self): return asdict(self)

@dataclass(frozen=True)
class KnowledgeConfidence:
    knowledge_uuid: str
    knowledge_version: str
    sample_count: int
    confidence: float
    classification: str
    def to_dict(self): return asdict(self)

@dataclass(frozen=True)
class AnalyticsSummary:
    trade_count: int
    winning_trade_count: int
    losing_trade_count: int
    total_outcome: float
    average_outcome: float
    knowledge_version_count: int
    replay_digest: str
    def to_dict(self): return asdict(self)

@dataclass(frozen=True)
class KnowledgeAnalyticsReport:
    analytics_uuid: str
    analytics_version: str
    created_at: str
    source_digest: str
    replay_digest: str
    knowledge_versions: tuple[tuple[str, str], ...]
    summary: AnalyticsSummary
    feature_contributions: tuple[FeatureContribution, ...] = ()
    failure_patterns: tuple[FailurePattern, ...] = ()
    success_patterns: tuple[SuccessPattern, ...] = ()
    performance_profiles: tuple[KnowledgePerformanceProfile, ...] = ()
    market_regimes: tuple[MarketRegimeProfile, ...] = ()
    indicator_contributions: tuple[IndicatorContribution, ...] = ()
    risk_contributions: tuple[RiskContribution, ...] = ()
    confidence: tuple[KnowledgeConfidence, ...] = ()
    context_attribution: Mapping[str, Any] = field(default_factory=dict)
    advisory_only: bool = True
    def __post_init__(self):
        if not self.advisory_only: raise ValueError('PR173_ANALYTICS_MUST_BE_ADVISORY_ONLY')
        object.__setattr__(self, 'knowledge_versions', tuple(sorted(tuple(v) for v in self.knowledge_versions)))
        object.__setattr__(self, 'context_attribution', freeze(dict(self.context_attribution)))
    def to_dict(self):
        return {
            'analytics_uuid': self.analytics_uuid, 'analytics_version': self.analytics_version, 'created_at': self.created_at,
            'source_digest': self.source_digest, 'replay_digest': self.replay_digest, 'knowledge_versions': [list(v) for v in self.knowledge_versions],
            'summary': self.summary.to_dict(), 'feature_contributions': [x.to_dict() for x in self.feature_contributions],
            'failure_patterns': [x.to_dict() for x in self.failure_patterns], 'success_patterns': [x.to_dict() for x in self.success_patterns],
            'performance_profiles': [x.to_dict() for x in self.performance_profiles], 'market_regimes': [x.to_dict() for x in self.market_regimes],
            'indicator_contributions': [x.to_dict() for x in self.indicator_contributions], 'risk_contributions': [x.to_dict() for x in self.risk_contributions],
            'confidence': [x.to_dict() for x in self.confidence], 'context_attribution': thaw(self.context_attribution), 'advisory_only': self.advisory_only,
        }

    @classmethod
    def from_dict(cls, value):
        value = dict(value)
        value['knowledge_versions'] = tuple(tuple(x) for x in value.get('knowledge_versions', ()))
        value['summary'] = AnalyticsSummary(**value['summary'])
        value['feature_contributions'] = tuple(FeatureContribution(**x) for x in value.get('feature_contributions', ()))
        value['failure_patterns'] = tuple(FailurePattern(**x) for x in value.get('failure_patterns', ()))
        value['success_patterns'] = tuple(SuccessPattern(**x) for x in value.get('success_patterns', ()))
        value['performance_profiles'] = tuple(KnowledgePerformanceProfile(**x) for x in value.get('performance_profiles', ()))
        value['market_regimes'] = tuple(MarketRegimeProfile(**x) for x in value.get('market_regimes', ()))
        value['indicator_contributions'] = tuple(IndicatorContribution(**x) for x in value.get('indicator_contributions', ()))
        value['risk_contributions'] = tuple(RiskContribution(**x) for x in value.get('risk_contributions', ()))
        value['confidence'] = tuple(KnowledgeConfidence(**x) for x in value.get('confidence', ()))
        return cls(**value)
