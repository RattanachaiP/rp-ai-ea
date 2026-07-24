"""Immutable contracts for PR165 promotion governance.

This boundary prepares authorizations only.  It never activates knowledge or
imports runtime, registry, or promotion-authority implementations.
"""
from __future__ import annotations
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Mapping
from uuid import UUID
from learning.common.immutable import freeze, thaw

PROMOTION_STATES = frozenset({"APPROVED", "REJECTED", "DEFERRED", "EXPIRED"})
APPROVAL_MODES = frozenset({"MANUAL_ONLY", "TWO_STEP_APPROVAL", "AUTO_APPROVAL_DISABLED"})

def _uuid(value: str) -> bool:
    try: return str(UUID(value)) == value.lower()
    except (ValueError, TypeError, AttributeError): return False

def _time(value: str) -> bool:
    try: return datetime.fromisoformat(value.replace("Z", "+00:00")).tzinfo is not None
    except (ValueError, AttributeError): return False

@dataclass(frozen=True)
class PromotionPolicy:
    version: str = "1.0"
    architecture_version: str = "PR165"
    minimum_scientific_score: int = 0
    minimum_statistical_score: int = 0
    minimum_governance_score: int = 0
    approval_mode: str = "MANUAL_ONLY"
    decision_ttl_seconds: int = 86400
    evaluation_timestamp: str = ""
    def __post_init__(self) -> None:
        if (not self.version or not self.architecture_version or self.approval_mode not in APPROVAL_MODES
            or not isinstance(self.decision_ttl_seconds, int) or isinstance(self.decision_ttl_seconds, bool) or self.decision_ttl_seconds < 0
            or (self.evaluation_timestamp and not _time(self.evaluation_timestamp))
            or any(not isinstance(x, int) or isinstance(x, bool) or not 0 <= x <= 100 for x in (self.minimum_scientific_score, self.minimum_statistical_score, self.minimum_governance_score))):
            raise ValueError("INVALID_PROMOTION_POLICY")
    def canonical_dict(self) -> dict[str, Any]:
        return {name: getattr(self, name) for name in self.__dataclass_fields__}

@dataclass(frozen=True)
class PromotionDecision:
    promotion_uuid: str
    candidate_uuid: str
    knowledge_uuid: str
    state: str
    reason: str
    policy_version: str
    architecture_version: str
    qualification_digest: str
    replay_digest: str
    created_at: str
    approval_required: bool = True
    def __post_init__(self) -> None:
        if (not all(_uuid(getattr(self, key)) for key in ("promotion_uuid", "candidate_uuid", "knowledge_uuid"))
            or self.state not in PROMOTION_STATES or not all(isinstance(getattr(self, k), str) and getattr(self, k) for k in ("reason", "policy_version", "architecture_version", "qualification_digest", "replay_digest", "created_at"))
            or not _time(self.created_at) or len(self.qualification_digest) != 64 or len(self.replay_digest) != 64):
            raise ValueError("INVALID_PROMOTION_DECISION")
    def to_dict(self) -> dict[str, Any]: return {name: getattr(self, name) for name in self.__dataclass_fields__}

@dataclass(frozen=True)
class PromotionAudit:
    promotion_uuid: str; candidate_uuid: str; knowledge_uuid: str; approval_timestamp: str
    approver: str; policy_version: str; architecture_version: str; reason: str
    def __post_init__(self) -> None:
        if (not all(_uuid(getattr(self, k)) for k in ("promotion_uuid", "candidate_uuid", "knowledge_uuid")) or not _time(self.approval_timestamp)
            or any(not isinstance(getattr(self,k), str) or not getattr(self,k) for k in ("approver","policy_version","architecture_version","reason"))): raise ValueError("INVALID_PROMOTION_AUDIT")
    def to_dict(self) -> dict[str, Any]: return {name: getattr(self, name) for name in self.__dataclass_fields__}

PromotionHistory = PromotionAudit

@dataclass(frozen=True)
class PromotionPackage:
    decision: PromotionDecision
    audit: PromotionAudit | None = None
    rollout_not_before: str = ""
    def __post_init__(self) -> None:
        if self.rollout_not_before and not _time(self.rollout_not_before): raise ValueError("INVALID_PROMOTION_PACKAGE")
