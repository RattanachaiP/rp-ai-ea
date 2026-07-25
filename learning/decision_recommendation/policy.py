"""Immutable PR185 advisory recommendation policy."""

from dataclasses import dataclass
from .identity import digest, policy_uuid


POLICY_VERSION = "PR185-RECOMMENDATION-POLICY.1.0"
ENGINE_VERSION = "PR185.1.0"


@dataclass(frozen=True)
class DecisionRecommendationPolicy:
    recommendation_policy_version: str = POLICY_VERSION
    recommendation_engine_version: str = ENGINE_VERSION
    ready_quality_threshold: float = 0.75
    manual_review_quality_threshold: float = 0.50
    ready_intelligence_state: str = "DECISION_INTELLIGENCE_READY"
    insufficient_intelligence_state: str = "INSUFFICIENT_DECISION_INTELLIGENCE"

    def __post_init__(self):
        if (
            self.recommendation_policy_version != POLICY_VERSION
            or self.recommendation_engine_version != ENGINE_VERSION
            or type(self.ready_quality_threshold) is not float
            or type(self.manual_review_quality_threshold) is not float
            or not 0.0
            <= self.manual_review_quality_threshold
            <= self.ready_quality_threshold
            <= 1.0
            or self.ready_intelligence_state != "DECISION_INTELLIGENCE_READY"
            or self.insufficient_intelligence_state
            != "INSUFFICIENT_DECISION_INTELLIGENCE"
        ):
            raise ValueError("INVALID_RECOMMENDATION_POLICY")

    def to_dict(self):
        return {n: getattr(self, n) for n in self.__dataclass_fields__}

    @property
    def recommendation_policy_digest(self):
        return digest(self.to_dict())

    @property
    def recommendation_policy_uuid(self):
        return policy_uuid(self.to_dict())
