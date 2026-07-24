"""Immutable contracts for the promotion decision boundary."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping

from learning.common.immutable import freeze, thaw

_SEVERITIES = {"NONE", "LOW", "MEDIUM", "HIGH", "CRITICAL"}
_DECISIONS = {"PROMOTE", "DEFER", "REJECT", "MANUAL_REVIEW"}
_STATUSES = {"APPROVED", "DENIED", "WAITING", "BLOCKED"}


@dataclass(frozen=True)
class PromotionPolicyConfig:
    """Explicit, versioned policy supplied by the caller; it has no authority itself."""

    version: str = "1.0"
    minimum_qualification_score: int = 100
    maximum_conflict_severity: str = "LOW"
    promotion_window_open: bool = True
    freeze_window_active: bool = False
    promotion_cooldown_active: bool = False
    require_repository_healthy: bool = True
    require_control_plane_healthy: bool = True
    evaluation_timestamp: str = ""
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        severity = str(self.maximum_conflict_severity).upper()
        if (not self.version or not isinstance(self.minimum_qualification_score, int)
                or isinstance(self.minimum_qualification_score, bool)
                or not 0 <= self.minimum_qualification_score <= 100
                or severity not in _SEVERITIES
                or not isinstance(self.promotion_window_open, bool)
                or not isinstance(self.freeze_window_active, bool)
                or not isinstance(self.promotion_cooldown_active, bool)
                or not isinstance(self.require_repository_healthy, bool)
                or not isinstance(self.require_control_plane_healthy, bool)
                or not isinstance(self.evaluation_timestamp, str)):
            raise ValueError("INVALID_PROMOTION_POLICY_CONFIG")
        object.__setattr__(self, "maximum_conflict_severity", severity)
        object.__setattr__(self, "metadata", freeze(dict(self.metadata)))

    def canonical_dict(self) -> dict[str, Any]:
        return {
            "version": self.version, "minimum_qualification_score": self.minimum_qualification_score,
            "maximum_conflict_severity": self.maximum_conflict_severity,
            "promotion_window_open": self.promotion_window_open,
            "freeze_window_active": self.freeze_window_active,
            "promotion_cooldown_active": self.promotion_cooldown_active,
            "require_repository_healthy": self.require_repository_healthy,
            "require_control_plane_healthy": self.require_control_plane_healthy,
            "evaluation_timestamp": self.evaluation_timestamp, "metadata": thaw(self.metadata),
        }


@dataclass(frozen=True)
class PromotionDecisionReport:
    """A deeply immutable advisory report, never a promotion instruction."""

    decision_uuid: str
    knowledge_uuid: str
    decision: str
    decision_status: str
    reason: tuple[Mapping[str, Any], ...] = ()
    blocking_conditions: tuple[Mapping[str, Any], ...] = ()
    snapshot_digest: str = ""
    qualification_digest: str = ""
    policy_version: str = ""
    created_at: str = ""

    def __post_init__(self) -> None:
        if (not self.decision_uuid or not self.knowledge_uuid or self.decision not in _DECISIONS
                or self.decision_status not in _STATUSES or not self.snapshot_digest
                or not self.qualification_digest or not self.policy_version):
            raise ValueError("INVALID_PROMOTION_DECISION_REPORT")
        for field_name in ("reason", "blocking_conditions"):
            object.__setattr__(self, field_name, tuple(freeze(item) for item in getattr(self, field_name)))

    def to_dict(self) -> dict[str, Any]:
        return {name: thaw(getattr(self, name)) for name in self.__dataclass_fields__}
