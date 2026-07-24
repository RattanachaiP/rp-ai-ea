"""Passive governance layer for immutable verified-knowledge records."""
from .models import KnowledgeGovernance, utc_now
from .repository import GovernanceRepository
from .schema import GOVERNANCE_SCHEMA_VERSION, LIFECYCLE_STATES
from .storage import GovernanceStorage
from .validator import GovernanceValidationError, LifecycleValidator

__all__ = [
    "GOVERNANCE_SCHEMA_VERSION", "LIFECYCLE_STATES", "GovernanceRepository", "GovernanceStorage",
    "GovernanceValidationError", "KnowledgeGovernance", "LifecycleValidator", "utc_now",
]
