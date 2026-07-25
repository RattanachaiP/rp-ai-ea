"""Complete immutable scoring policy for PR182 advisory confidence evaluation."""

from dataclasses import dataclass
from decimal import ROUND_HALF_EVEN
from math import isfinite

from .identity import digest, policy_uuid

DIMENSIONS = (
    "ELIGIBILITY_EVIDENCE_COMPLETENESS",
    "RUNTIME_PACKAGE_VALIDATION",
    "REGISTRY_ADMISSION",
    "PROMOTION_STATE",
    "VALIDATION_STATE",
    "UPSTREAM_REASON_SEVERITY",
    "SNAPSHOT_MEMBERSHIP_INTEGRITY",
    "LINEAGE_COMPLETENESS",
    "POLICY_PARTITION_CONSISTENCY",
)
DEFAULT_WEIGHTS = (
    ("ELIGIBILITY_EVIDENCE_COMPLETENESS", 0.15),
    ("RUNTIME_PACKAGE_VALIDATION", 0.10),
    ("REGISTRY_ADMISSION", 0.10),
    ("PROMOTION_STATE", 0.20),
    ("VALIDATION_STATE", 0.20),
    ("UPSTREAM_REASON_SEVERITY", 0.10),
    ("SNAPSHOT_MEMBERSHIP_INTEGRITY", 0.05),
    ("LINEAGE_COMPLETENESS", 0.05),
    ("POLICY_PARTITION_CONSISTENCY", 0.05),
)
DEFAULT_BANDS = (
    ("VERY_LOW", 0.00),
    ("LOW", 0.25),
    ("MODERATE", 0.50),
    ("HIGH", 0.70),
    ("VERY_HIGH", 0.85),
)
DEFAULT_REASON_ORDER = (
    "ELIGIBILITY_REJECTED",
    "ELIGIBILITY_EVIDENCE_INSUFFICIENT",
    "ELIGIBILITY_EVIDENCE_COMPLETE",
    "RUNTIME_PACKAGE_STATE_UNSATISFIED",
    "RUNTIME_PACKAGE_STATE_SATISFIED",
    "REGISTRY_ADMISSION_UNSATISFIED",
    "REGISTRY_ADMISSION_SATISFIED",
    "PROMOTION_STATE_UNSATISFIED",
    "PROMOTION_STATE_SATISFIED",
    "VALIDATION_STATE_UNSATISFIED",
    "VALIDATION_STATE_SATISFIED",
    "UPSTREAM_REASONS_SEVERE",
    "UPSTREAM_REASONS_CLEAR",
    "SNAPSHOT_MEMBERSHIP_VERIFIED",
    "LINEAGE_COMPLETE",
    "POLICY_PARTITION_CONSISTENT",
    "ADVISORY_CONFIDENCE_CALCULATED",
)


@dataclass(frozen=True)
class RuntimeConfidencePolicy:
    confidence_policy_version: str = "PR182-CONFIDENCE-POLICY.2.0"
    confidence_engine_version: str = "PR182.2.0"
    required_eligibility_state: str = "ELIGIBLE_FOR_CONFIDENCE_EVALUATION"
    dimension_definitions: tuple[str, ...] = DIMENSIONS
    dimension_weights: tuple[tuple[str, float], ...] = DEFAULT_WEIGHTS
    minimum_evidence_requirements: tuple[str, ...] = (
        "CANONICAL_PR181_RECORD",
        "VERIFIED_SNAPSHOT_MEMBERSHIP",
        "COMPLETE_RETAINED_LINEAGE",
        "CONSISTENT_GOVERNANCE_PARTITION",
    )
    missing_evidence_behavior: str = "INSUFFICIENT_CONFIDENCE_EVIDENCE"
    rejected_state_behavior: str = "REJECTED_WITH_EVIDENCE_SCORE"
    score_normalization_rule: str = "WEIGHTED_SUM_CLAMP_0_1"
    score_precision: int = 6
    rounding_mode: str = "ROUND_HALF_EVEN"
    confidence_band_thresholds: tuple[tuple[str, float], ...] = DEFAULT_BANDS
    reason_ordering_rules: tuple[str, ...] = DEFAULT_REASON_ORDER

    def __post_init__(self):
        definitions = tuple(self.dimension_definitions)
        weights = tuple(
            (name, float(weight)) for name, weight in self.dimension_weights
        )
        thresholds = tuple(
            (name, float(threshold))
            for name, threshold in self.confidence_band_thresholds
        )
        reasons = tuple(self.reason_ordering_rules)
        object.__setattr__(self, "dimension_definitions", definitions)
        object.__setattr__(self, "dimension_weights", weights)
        object.__setattr__(self, "confidence_band_thresholds", thresholds)
        object.__setattr__(self, "reason_ordering_rules", reasons)
        object.__setattr__(
            self,
            "minimum_evidence_requirements",
            tuple(self.minimum_evidence_requirements),
        )

        weight_values = [weight for _, weight in weights]
        threshold_values = [threshold for _, threshold in thresholds]
        if (
            not self.confidence_policy_version
            or self.confidence_engine_version != "PR182.2.0"
            or self.required_eligibility_state != "ELIGIBLE_FOR_CONFIDENCE_EVALUATION"
            or definitions != DIMENSIONS
            or tuple(name for name, _ in weights) != definitions
            or not all(isfinite(weight) and weight >= 0.0 for weight in weight_values)
            or round(sum(weight_values), 12) != 1.0
            or not thresholds
            or len({name for name, _ in thresholds}) != len(thresholds)
            or not all(
                isfinite(value) and 0.0 <= value <= 1.0 for value in threshold_values
            )
            or threshold_values != sorted(threshold_values)
            or threshold_values[0] != 0.0
            or type(self.score_precision) is not int
            or not 1 <= self.score_precision <= 12
            or self.rounding_mode != ROUND_HALF_EVEN
            or self.missing_evidence_behavior != "INSUFFICIENT_CONFIDENCE_EVIDENCE"
            or self.rejected_state_behavior != "REJECTED_WITH_EVIDENCE_SCORE"
            or self.score_normalization_rule != "WEIGHTED_SUM_CLAMP_0_1"
            or not reasons
            or len(set(reasons)) != len(reasons)
        ):
            raise ValueError("INVALID_CONFIDENCE_POLICY")

    def to_dict(self):
        return {
            "confidence_policy_version": self.confidence_policy_version,
            "confidence_engine_version": self.confidence_engine_version,
            "required_eligibility_state": self.required_eligibility_state,
            "dimension_definitions": list(self.dimension_definitions),
            "dimension_weights": [list(item) for item in self.dimension_weights],
            "minimum_evidence_requirements": list(self.minimum_evidence_requirements),
            "missing_evidence_behavior": self.missing_evidence_behavior,
            "rejected_state_behavior": self.rejected_state_behavior,
            "score_normalization_rule": self.score_normalization_rule,
            "score_precision": self.score_precision,
            "rounding_mode": self.rounding_mode,
            "confidence_band_thresholds": [
                list(item) for item in self.confidence_band_thresholds
            ],
            "reason_ordering_rules": list(self.reason_ordering_rules),
        }

    @property
    def confidence_policy_uuid(self):
        return policy_uuid(self.to_dict())

    @property
    def confidence_policy_digest(self):
        return digest(self.to_dict())
