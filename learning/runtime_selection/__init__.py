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

__all__ = [
    "RuntimeKnowledgeSelector",
    "RuntimeKnowledgeSelection",
    "RuntimeKnowledgeSelectionReport",
    "RuntimeKnowledgeSelectionSnapshot",
    "RuntimeKnowledgeSelectionPolicy",
    "RuntimeKnowledgeSelectionRepository",
    "RuntimeKnowledgeSelectionError",
]
