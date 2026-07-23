"""Statistical Validation: the exclusive authority for verified knowledge."""
from .validator import StatisticalValidator, validate, validate_pattern, validate_incremental
from .schema import ValidationResult, VALIDATION_STATUSES
from .repository import ValidationRepository
from .verifier import VerifiedKnowledge, promote
from .sample_size import DEFAULT_MINIMUM_SAMPLES, validate_sample_size
from .outlier import detect_outliers, mark_outliers
from .consistency import coefficient_of_variation, consistency_score, stability_score
__all__ = ["StatisticalValidator", "ValidationResult", "ValidationRepository", "VerifiedKnowledge", "VALIDATION_STATUSES", "DEFAULT_MINIMUM_SAMPLES", "validate", "validate_pattern", "validate_incremental", "promote", "validate_sample_size", "detect_outliers", "mark_outliers", "coefficient_of_variation", "consistency_score", "stability_score"]
