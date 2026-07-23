"""Immutable, versioned contracts for offline knowledge analytics."""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Any, Mapping
from uuid import uuid4
from learning.common.immutable import freeze, thaw

ANALYTICS_VERSION = "1.0"
STATUSES = frozenset({"COMPLETE", "EMPTY_INPUT", "PARTIAL", "INVALID_INPUT", "FAILED"})

@dataclass(frozen=True)
class AnalyticsConfig:
    version: str = "1.0"
    low_coverage_threshold: int = 2
    concentration_threshold: int = 5
    low_sample_threshold: int = 30
    stable_win_rate_delta: float = .03
    stable_rr_delta: float = .15
    improving_win_rate_delta: float = .05
    improving_rr_delta: float = .25
    conflict_win_rate_delta: float = .15
    conflict_rr_delta: float = .75
    supported_schema_versions: tuple[str, ...] = ("1.0",)
    maximum_findings: int = 100
    persistence_enabled: bool = True

    def __post_init__(self):
        object.__setattr__(self, "supported_schema_versions", tuple(sorted(self.supported_schema_versions)))

@dataclass(frozen=True)
class AnalyticsReport:
    analytics_uuid: str
    analytics_version: str
    created_at: str
    source_baseline: str
    configuration_version: str
    knowledge_snapshot: Mapping[str, Any]
    inventory: Mapping[str, Any] = field(default_factory=dict)
    coverage: Mapping[str, Any] = field(default_factory=dict)
    performance: Mapping[str, Any] = field(default_factory=dict)
    stability: Mapping[str, Any] = field(default_factory=dict)
    conflicts: tuple[Mapping[str, Any], ...] = ()
    data_quality: Mapping[str, Any] = field(default_factory=dict)
    status: str = "COMPLETE"
    completed_domains: tuple[str, ...] = ()
    failed_domains: tuple[str, ...] = ()

    def __post_init__(self):
        if self.status not in STATUSES: raise ValueError("INVALID_ANALYTICS_STATUS")
        for name in ("knowledge_snapshot", "inventory", "coverage", "performance", "stability", "data_quality"):
            object.__setattr__(self, name, freeze(getattr(self, name)))
        object.__setattr__(self, "conflicts", tuple(freeze(x) for x in self.conflicts))
        object.__setattr__(self, "completed_domains", tuple(self.completed_domains))
        object.__setattr__(self, "failed_domains", tuple(self.failed_domains))

    def to_dict(self):
        return {"analytics_uuid":self.analytics_uuid,"analytics_version":self.analytics_version,"created_at":self.created_at,"source_baseline":self.source_baseline,"configuration_version":self.configuration_version,"knowledge_snapshot":thaw(self.knowledge_snapshot),"inventory":thaw(self.inventory),"coverage":thaw(self.coverage),"performance":thaw(self.performance),"stability":thaw(self.stability),"conflicts":thaw(self.conflicts),"data_quality":thaw(self.data_quality),"status":self.status,"completed_domains":list(self.completed_domains),"failed_domains":list(self.failed_domains)}

    @classmethod
    def from_dict(cls, value): return cls(**value)
