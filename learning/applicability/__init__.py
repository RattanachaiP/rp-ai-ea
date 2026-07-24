"""Compatibility facade for the Runtime-owned applicability boundary."""
from runtime.knowledge_applicability import (
    ApplicableKnowledge,
    ApplicabilityConfig,
    ApplicabilityEvaluationError,
    ApplicabilityReport,
    ApplicabilityReportWriter,
    KnowledgeApplicabilityEngine,
    RuntimeContext,
    canonical_digest,
)
from runtime.applicability_storage import ApplicabilityReportRepository

__all__ = [
    "ApplicableKnowledge",
    "ApplicabilityConfig",
    "ApplicabilityEvaluationError",
    "ApplicabilityReport",
    "ApplicabilityReportRepository",
    "ApplicabilityReportWriter",
    "KnowledgeApplicabilityEngine",
    "RuntimeContext",
    "canonical_digest",
]
