"""Immutable, versioned qualification contracts."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Mapping

from learning.common.immutable import freeze, thaw

_ALLOWED_SEVERITIES = {"NONE", "LOW", "MEDIUM", "HIGH", "CRITICAL"}
_REQUIRED_CHECKS = {
    "policy", "governance", "lifecycle", "analytics", "health",
    "lineage", "snapshot", "schema", "configuration",
}
_ALLOWED_STATUSES = {
    "QUALIFIED", "CONDITIONALLY_QUALIFIED", "NOT_QUALIFIED",
    "INSUFFICIENT_INFORMATION", "INVALID_SNAPSHOT",
}


def _valid_timestamp(value: str | None) -> bool:
    if value is None:
        return True
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except (TypeError, ValueError):
        return False
    return parsed.tzinfo is not None


@dataclass(frozen=True)
class QualificationConfig:
    """All readiness scoring inputs, explicitly versioned."""

    version: str = "1.0"
    maximum_conflict_severity: str = "LOW"
    allowed_stability: tuple[str, ...] = ("STABLE", "IMPROVING")
    maximum_analytics_age_seconds: int = 86400
    evaluation_timestamp: str | None = None
    check_weights: Mapping[str, int] = field(default_factory=lambda: {
        "policy": 15, "governance": 15, "lifecycle": 15, "analytics": 10,
        "health": 10, "lineage": 10, "snapshot": 20, "schema": 3,
        "configuration": 2,
    })

    def __post_init__(self) -> None:
        weights = dict(self.check_weights)
        severity = str(self.maximum_conflict_severity).upper()
        stability = tuple(sorted(set(self.allowed_stability)))
        invalid = (
            not self.version
            or severity not in _ALLOWED_SEVERITIES
            or not stability
            or any(not isinstance(item, str) or not item for item in stability)
            or not isinstance(self.maximum_analytics_age_seconds, int)
            or isinstance(self.maximum_analytics_age_seconds, bool)
            or self.maximum_analytics_age_seconds < 0
            or not _valid_timestamp(self.evaluation_timestamp)
            or set(weights) != _REQUIRED_CHECKS
            or any(not isinstance(value, int) or isinstance(value, bool) or value < 0 for value in weights.values())
            or sum(weights.values()) != 100
        )
        if invalid:
            raise ValueError("INVALID_QUALIFICATION_CONFIG")
        object.__setattr__(self, "maximum_conflict_severity", severity)
        object.__setattr__(self, "check_weights", freeze(weights))
        object.__setattr__(self, "allowed_stability", stability)

    def canonical_dict(self) -> dict[str, Any]:
        return {
            "version": self.version,
            "maximum_conflict_severity": self.maximum_conflict_severity,
            "allowed_stability": list(self.allowed_stability),
            "maximum_analytics_age_seconds": self.maximum_analytics_age_seconds,
            "evaluation_timestamp": self.evaluation_timestamp,
            "check_weights": thaw(self.check_weights),
        }


@dataclass(frozen=True)
class QualificationReport:
    qualification_uuid: str
    knowledge_uuid: str
    qualified: bool
    qualification_score: int
    status: str
    reasons: tuple[Mapping[str, Any], ...] = ()
    warnings: tuple[Mapping[str, Any], ...] = ()
    failed_checks: tuple[Mapping[str, Any], ...] = ()
    unknown_checks: tuple[Mapping[str, Any], ...] = ()
    control_plane_digest: str = ""
    configuration_version: str = ""
    created_at: str = ""

    def __post_init__(self) -> None:
        if self.status not in _ALLOWED_STATUSES:
            raise ValueError("INVALID_QUALIFICATION_REPORT")
        if not self.qualification_uuid or not self.knowledge_uuid or not self.control_plane_digest or not self.configuration_version:
            raise ValueError("INVALID_QUALIFICATION_REPORT")
        if not isinstance(self.qualification_score, int) or isinstance(self.qualification_score, bool) or not 0 <= self.qualification_score <= 100:
            raise ValueError("INVALID_QUALIFICATION_REPORT")
        if self.qualified != (self.status == "QUALIFIED"):
            raise ValueError("INVALID_QUALIFICATION_REPORT")
        for name in ("reasons", "warnings", "failed_checks", "unknown_checks"):
            object.__setattr__(self, name, tuple(freeze(item) for item in getattr(self, name)))

    def to_dict(self) -> dict[str, Any]:
        return {name: thaw(getattr(self, name)) for name in self.__dataclass_fields__}
