"""Governed, offline promotion-eligibility authority (PR274)."""
from .authority import PromotionAuthority, PromotionValidationError
from .contracts import (
    PROMOTION_DECISIONS, PROMOTION_GATES, PROMOTION_SCHEMA_VERSION,
    GovernanceQueueEntry, PromotionApprovalRequest, PromotionEvidence,
    PromotionGate, PromotionPolicy, PromotionReport, PromotionResult,
)
from .registry import PromotionRegistry, PromotionRegistryEntry

__all__ = [
    "PROMOTION_DECISIONS", "PROMOTION_GATES", "PROMOTION_SCHEMA_VERSION",
    "GovernanceQueueEntry", "PromotionApprovalRequest", "PromotionAuthority",
    "PromotionEvidence", "PromotionGate", "PromotionPolicy", "PromotionRegistry",
    "PromotionRegistryEntry", "PromotionReport", "PromotionResult",
    "PromotionValidationError",
]
