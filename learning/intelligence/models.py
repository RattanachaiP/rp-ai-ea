"""Immutable contracts for PR163's offline Learning Intelligence Engine."""
from __future__ import annotations
from dataclasses import dataclass, asdict
from typing import Any

RECOMMENDATION_TYPES = frozenset({"PROMOTE", "COLLECT_MORE_DATA", "REVIEW", "REJECT", "NO_ACTION"})

@dataclass(frozen=True)
class LearningThresholds:
    minimum_trades: int = 100
    minimum_wins: int = 30
    minimum_sessions: int = 3
    minimum_confidence: float = 0.90
    promote_min_profit_factor: float = 1.20
    promote_min_expectancy: float = 0.0
    reject_max_profit_factor: float = 0.80
    drift_recent_trades: int = 20
    drift_profit_factor_drop: float = 0.50
    def __post_init__(self) -> None:
        if (any(not isinstance(v, int) or isinstance(v, bool) or v < 1 for v in
                (self.minimum_trades, self.minimum_wins, self.minimum_sessions, self.drift_recent_trades))
                or not 0 < self.minimum_confidence <= 1 or self.promote_min_profit_factor <= 0
                or self.reject_max_profit_factor < 0 or self.drift_profit_factor_drop < 0):
            raise ValueError("INVALID_LEARNING_THRESHOLDS")

@dataclass(frozen=True)
class LearningKnowledgeStatistics:
    knowledge_uuid: str
    semantic_identity: str
    usage_count: int
    wins: int
    losses: int
    win_rate: float
    loss_rate: float
    gross_profit: float
    net_profit: float
    profit_factor: float | None
    expectancy: float
    average_holding_time_seconds: float
    average_mfe: float
    average_mae: float
    max_drawdown_contribution: float
    average_reward_risk: float | None
    confidence_interval: tuple[float, float]
    confidence: float
    context: dict[str, dict[str, dict[str, float | int | None]]]
    drift_detected: bool
    def to_dict(self) -> dict[str, Any]:
        result = asdict(self); result["confidence_interval"] = list(self.confidence_interval); return result

@dataclass(frozen=True)
class LearningRecommendation:
    knowledge_uuid: str
    semantic_identity: str
    recommendation: str
    confidence: float
    reasons: tuple[str, ...]
    advisory_only: bool = True
    def __post_init__(self) -> None:
        if self.recommendation not in RECOMMENDATION_TYPES or not self.advisory_only:
            raise ValueError("INVALID_LEARNING_RECOMMENDATION")
    def to_dict(self) -> dict[str, Any]:
        result = asdict(self); result["reasons"] = list(self.reasons); return result

@dataclass(frozen=True)
class LearningCandidate:
    knowledge_uuid: str
    semantic_identity: str
    recommendation: LearningRecommendation
    statistics: LearningKnowledgeStatistics
    def to_dict(self) -> dict[str, Any]:
        return {"knowledge_uuid": self.knowledge_uuid, "semantic_identity": self.semantic_identity,
                "recommendation": self.recommendation.to_dict(), "statistics": self.statistics.to_dict()}

@dataclass(frozen=True)
class LearningSummary:
    trades: int
    knowledge_evaluated: int
    promotion_candidates: int
    review_required: int
    rejected: int
    drift_detected: bool
    replay_status: str = "PASS"
    def to_dict(self) -> dict[str, Any]: return asdict(self)

@dataclass(frozen=True)
class LearningDailyReport:
    report_date: str
    summary: LearningSummary
    statistics: tuple[LearningKnowledgeStatistics, ...]
    recommendations: tuple[LearningRecommendation, ...]
    def to_dict(self) -> dict[str, Any]:
        return {"report_date": self.report_date, "summary": self.summary.to_dict(),
                "statistics": [x.to_dict() for x in self.statistics], "recommendations": [x.to_dict() for x in self.recommendations]}

@dataclass(frozen=True)
class LearningWeeklyReport:
    week_start: str
    summary: LearningSummary
    statistics: tuple[LearningKnowledgeStatistics, ...]
    recommendations: tuple[LearningRecommendation, ...]
    def to_dict(self) -> dict[str, Any]:
        return {"week_start": self.week_start, "summary": self.summary.to_dict(),
                "statistics": [x.to_dict() for x in self.statistics], "recommendations": [x.to_dict() for x in self.recommendations]}
