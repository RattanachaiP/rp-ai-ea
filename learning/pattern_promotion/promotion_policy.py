"""Immutable promotion policy and its deterministic identity."""
from dataclasses import dataclass
from math import isfinite
from .identity import digest, promotion_policy_uuid


@dataclass(frozen=True)
class PromotionPolicy:
    promotion_policy_version: str = "PR178-POLICY.1.0"
    minimum_sample_count: int = 30
    minimum_support: float = 0.0
    minimum_confidence: float = 0.0
    minimum_expectancy: float = 0.0
    required_validation_state: str = "STATISTICALLY_CONSISTENT"

    def __post_init__(self):
        values = (self.minimum_support, self.minimum_confidence, self.minimum_expectancy)
        if (not isinstance(self.promotion_policy_version, str) or not self.promotion_policy_version
                or not isinstance(self.minimum_sample_count, int) or isinstance(self.minimum_sample_count, bool)
                or self.minimum_sample_count < 0 or not all(isinstance(x, (int, float))
                and not isinstance(x, bool) and isfinite(x) for x in values)
                or self.minimum_support < 0 or self.minimum_confidence < 0
                or self.required_validation_state not in
                ("INVALID", "INSUFFICIENT_EVIDENCE", "STATISTICALLY_CONSISTENT")):
            raise ValueError("INVALID_PROMOTION_POLICY")

    def to_dict(self):
        return {name: getattr(self, name) for name in self.__dataclass_fields__}

    @property
    def policy_uuid(self): return promotion_policy_uuid(self.to_dict())

    @property
    def policy_digest(self): return digest(self.to_dict())

    def assess(self, record):
        if record.validation_state == "INVALID":
            return "REJECTED", ("SOURCE_VALIDATION_REJECTED",)
        if record.validation_state != self.required_validation_state:
            return "NOT_YET_ELIGIBLE", ("REQUIRED_VALIDATION_STATE_NOT_MET",)
        stats = dict(record.validation_statistics)
        failures = []
        for field in ("sample_count", "support", "confidence", "expectancy"):
            threshold = getattr(self, f"minimum_{field}")
            if stats[field] < threshold:
                failures.append(f"MINIMUM_{field.upper()}_NOT_MET")
        if failures:
            return "NOT_YET_ELIGIBLE", tuple(failures)
        return "PROMOTION_ELIGIBLE", ("GOVERNED_PROMOTION_POLICY_PASSED",)
