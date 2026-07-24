"""Immutable, versioned contracts for offline knowledge policy evaluation."""
from __future__ import annotations
from dataclasses import asdict, dataclass, field
from typing import Any, Mapping
from learning.common.immutable import freeze, thaw

OUTCOMES = frozenset({"PASS", "FAIL", "WARNING", "NOT_APPLICABLE"})

@dataclass(frozen=True)
class PolicyConfig:
    version: str = "1.0"
    minimum_sample_count: int = 30
    minimum_significance: float = 0.95
    minimum_win_rate: float = 0.50
    minimum_average_rr: float = 1.0
    allowed_stability: tuple[str, ...] = ("STABLE", "IMPROVING")
    required_lifecycle_state: str = "VERIFIED"
    required_governance_status: bool = True
    maximum_conflict_severity: str = "LOW"
    supported_schema_versions: tuple[str, ...] = ("1.0",)
    maximum_analytics_age_seconds: int = 86400

    def __post_init__(self) -> None:
        import math
        if not self.version or self.minimum_sample_count < 1 or self.maximum_analytics_age_seconds < 0:
            raise ValueError("INVALID_POLICY_CONFIG")
        if not all(math.isfinite(value) for value in (self.minimum_significance, self.minimum_win_rate, self.minimum_average_rr)):
            raise ValueError("INVALID_POLICY_CONFIG")
        if not 0 <= self.minimum_significance <= 1 or not 0 <= self.minimum_win_rate <= 1:
            raise ValueError("INVALID_POLICY_CONFIG")
        if not self.allowed_stability or not self.supported_schema_versions:
            raise ValueError("INVALID_POLICY_CONFIG")
        object.__setattr__(self, "allowed_stability", tuple(sorted(set(self.allowed_stability))))
        object.__setattr__(self, "supported_schema_versions", tuple(sorted(set(self.supported_schema_versions))))

    def canonical_dict(self) -> dict[str, Any]: return asdict(self)

@dataclass(frozen=True)
class RuleResult:
    category: str
    outcome: str
    reason: str
    score: int = 0

    def __post_init__(self) -> None:
        if self.outcome not in OUTCOMES: raise ValueError("INVALID_POLICY_OUTCOME")

    def to_dict(self) -> dict[str, Any]: return asdict(self)

@dataclass(frozen=True)
class PolicyEvaluationReport:
    knowledge_uuid: str
    policy_version: str
    eligible: bool
    score: int
    failed_rules: tuple[Mapping[str, Any], ...] = ()
    passed_rules: tuple[Mapping[str, Any], ...] = ()
    warnings: tuple[Mapping[str, Any], ...] = ()
    evaluation_timestamp: str = ""
    source_baseline: str = ""
    evaluation_uuid: str = ""

    def __post_init__(self) -> None:
        for name in ("failed_rules", "passed_rules", "warnings"):
            object.__setattr__(self, name, tuple(freeze(item) for item in getattr(self, name)))
        if not self.knowledge_uuid or not self.policy_version or not self.evaluation_timestamp or not self.source_baseline or not self.evaluation_uuid:
            raise ValueError("INVALID_POLICY_REPORT")

    def to_dict(self) -> dict[str, Any]:
        return {name: thaw(getattr(self, name)) for name in self.__dataclass_fields__}
