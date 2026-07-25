"""PR181 governed advisory knowledge eligibility public API.

``evaluate_eligibility()`` records advisory eligibility only. It does not
activate, apply, weight, rank, score, or authorize Runtime knowledge.
"""

from .engine import RuntimeKnowledgeSelector
from .exceptions import RuntimeKnowledgeSelectionError
from .models import (
    RuntimeKnowledgeSelection,
    RuntimeKnowledgeSelectionReport,
    RuntimeKnowledgeSelectionSnapshot,
)
from .policy import RuntimeKnowledgeSelectionPolicy
from .repository import RuntimeKnowledgeSelectionRepository

# Architecture-facing PR181 names consumed by PR182.  These are aliases, not
# wrappers, so the confidence boundary can enforce exact canonical types.
KnowledgeEligibilityRecord = RuntimeKnowledgeSelection
KnowledgeEligibilityReport = RuntimeKnowledgeSelectionReport
KnowledgeEligibilitySnapshot = RuntimeKnowledgeSelectionSnapshot

__all__ = [
    "RuntimeKnowledgeSelector",
    "RuntimeKnowledgeSelection",
    "RuntimeKnowledgeSelectionReport",
    "RuntimeKnowledgeSelectionSnapshot",
    "RuntimeKnowledgeSelectionPolicy",
    "RuntimeKnowledgeSelectionRepository",
    "RuntimeKnowledgeSelectionError",
    "KnowledgeEligibilityRecord",
    "KnowledgeEligibilityReport",
    "KnowledgeEligibilitySnapshot",
]
