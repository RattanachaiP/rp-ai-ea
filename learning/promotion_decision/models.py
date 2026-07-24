"""Immutable contracts for the promotion decision boundary."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Mapping

from learning.common.immutable import freeze, thaw

_SEVERITIES = {"NONE", "LOW", "MEDIUM", "HIGH", "CRITICAL"}
_DECISIONS = {"PROMOTE", "DEFER", "REJECT", "MANUAL_REVIEW"}
_STATUSES = {"APPROVED", "DENIED", "WAITING", "BLOCKED"}


def _valid_timestamp(value: str) -> bool:
    if not value:
        return True
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return False
    return parsed.tzinfo is not None


@dataclass(frozen=True)
class PromotionPolicyConfig:
    """Explicit, versioned advisory policy supplied by the caller."""

    version: str = "1.0"
    minimum_qualification_score: int = 100
    maximum_conflict_severity: str = "LOW"
    promotion_window_open: bool = True
    freeze_window_active: bool = False
    promotion_cooldown_active: bool = False
    require_repository_healthy: bool = True
    require_control_plane_healthy: bool = True
    evaluation_timestamp: str = ""
    promotion_window_start: str = ""
    promotion_window_end: str = ""
    freeze_until: str = ""
    cooldown_until: str = ""
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        severity = str(self.maximum_conflict_severity).upper()
        timestamps = (
            self.evaluation_timestamp, self.promotion_window_start, self.promotion_window_end,
            self.freeze_until, self.cooldown_until,
        )
        if (not self.version or not isinstance(self.minimum_qualification_score, int)
                or isinstance(self.minimum_qualification_score, bool)
                or not 0 <= self.minimum_qualification_score <= 100
                or severity not in _SEVERITIES
                or not isinstance(self.promotion_window_open, bool)
                or not isinstance(self.freeze_window_active, bool)
                or not isinstance(self.promotion_cooldown_active, bool)
                or not isinstance(self.require_repository_healthy, bool)
                or not isinstance(self.require_control_plane_healthy, bool)
                or any(not isinstance(value, str) or not _valid_timestamp(value) for value in timestamps)
                or not isinstance(self.metadata, Mapping)):
            raise ValueError("INVALID_PROMOTION_POLICY_CONFIG")
        if self.promotion_window_start and self.promotion_window_end:
            start = datetime.fromisoformat(self.promotion_window_start.replace("Z", "+00:00"))
            end = datetime.fromisoformat(self.promotion_window_end.replace("Z", "+00:00"))
            if start > end:
                raise ValueError("INVALID_PROMOTION_POLICY_CONFIG")
        object.__setattr__(self, "maximum_conflict_severity", severity)
        object.__setattr__(self, "metadata", freeze(dict(self.metadata)))

    def canonical_dict(self) -> dict[str, Any]:
        return {
            "version": self.version,
            "minimum_qualification_score": self.minimum_qualification_score,
            "maximum_conflict_severity": self.maximum_conflict_severity,
            "promotion_window_open": self.promotion_window_open,
            "freeze_window_active": self.freeze_window_active,
            "promotion_cooldown_active": self.promotion_cooldown_active,
            "require_repository_healthy": self.require_repository_healthy,
            "require_control_plane_healthy": self.require_control_plane_healthy,
            "evaluation_timestamp": self.evaluation_timestamp,
            "promotion_window_start": self.promotion_window_start,
            "promotion_window_end": self.promotion_window_end,
            "freeze_until": self.freeze_until,
            "cooldown_until": self.cooldown_until,
            "metadata": thaw(self.metadata),
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
    schema_version: str = "1.0"
    configuration_digest: str = ""
    signature: str = ""

    def __post_init__(self) -> None:
        if (not self.decision_uuid or not self.knowledge_uuid or self.decision not in _DECISIONS
                or self.decision_status not in _STATUSES or not self.snapshot_digest
                or not self.qualification_digest or not self.policy_version
                or self.schema_version != "1.0" or not self.configuration_digest or not self.signature):
            raise ValueError("INVALID_PROMOTION_DECISION_REPORT")
        for field_name in ("reason", "blocking_conditions"):
            object.__setattr__(self, field_name, tuple(freeze(item) for item in getattr(self, field_name)))

    def to_dict(self) -> dict[str, Any]:
        return {name: thaw(getattr(self, name)) for name in self.__dataclass_fields__}