"""Versioned, deeply immutable contracts for offline analytics artifacts."""
from __future__ import annotations
from dataclasses import asdict, dataclass, field
from typing import Any, Mapping
from learning.common.immutable import freeze, thaw

ANALYTICS_VERSION = "1.0"
STATUSES = frozenset({"COMPLETE", "EMPTY_INPUT", "PARTIAL", "INVALID_INPUT", "FAILED"})

@dataclass(frozen=True)
class AnalyticsConfig:
    """All analytical thresholds are explicit inputs to artifact identity."""
    version: str = "1.0"
    low_coverage_threshold: int = 2
    concentration_threshold: int = 5
    low_sample_threshold: int = 30
    stable_win_rate_delta: float = 0.03
    stable_rr_delta: float = 0.15
    improving_win_rate_delta: float = 0.05
    improving_rr_delta: float = 0.25
    conflict_win_rate_delta: float = 0.15
    conflict_rr_delta: float = 0.75
    supported_schema_versions: tuple[str, ...] = ("1.0",)
    maximum_findings: int = 100
    persistence_enabled: bool = True

    def __post_init__(self) -> None:
        object.__setattr__(self, "supported_schema_versions", tuple(sorted(self.supported_schema_versions)))

    def canonical_dict(self) -> dict[str, Any]:
        return asdict(self)

@dataclass(frozen=True)
class AnalyticsReport:
    analytics_uuid: str
    analytics_version: str
    created_at: str | None
    source_baseline: str
    configuration_version: str
    configuration_digest: str
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
    failure_diagnostics: tuple[Mapping[str, str], ...] = ()

    def __post_init__(self) -> None:
        if self.status not in STATUSES:
            raise ValueError("INVALID_ANALYTICS_STATUS")
        for name in ("knowledge_snapshot", "inventory", "coverage", "performance", "stability", "data_quality"):
            object.__setattr__(self, name, freeze(getattr(self, name)))
        object.__setattr__(self, "conflicts", tuple(freeze(item) for item in self.conflicts))
        object.__setattr__(self, "failure_diagnostics", tuple(freeze(item) for item in self.failure_diagnostics))
        object.__setattr__(self, "completed_domains", tuple(self.completed_domains))
        object.__setattr__(self, "failed_domains", tuple(self.failed_domains))

    def to_dict(self) -> dict[str, Any]:
        return {name: thaw(getattr(self, name)) for name in self.__dataclass_fields__}

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> "AnalyticsReport":
        return cls(**value)
