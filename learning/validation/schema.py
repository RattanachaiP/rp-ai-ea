"""Immutable serialisable validation and verified-knowledge schemas."""
from __future__ import annotations
from dataclasses import dataclass
from types import MappingProxyType
from typing import Mapping

VALIDATION_VERSION = "1.0"
VALIDATION_STATUSES = frozenset({"INSUFFICIENT_DATA", "REJECTED", "VERIFIED", "ARCHIVED"})

@dataclass(frozen=True)
class ValidationResult:
    pattern_uuid: str
    status: str
    checks: Mapping[str, bool]
    metrics: Mapping[str, float | int | bool | tuple[float, float]]
    outlier_count: int = 0
    validation_version: str = VALIDATION_VERSION
    def __post_init__(self) -> None:
        if self.status not in VALIDATION_STATUSES: raise ValueError("INVALID_VALIDATION_STATUS")
        object.__setattr__(self, "checks", MappingProxyType(dict(self.checks)))
        object.__setattr__(self, "metrics", MappingProxyType(dict(self.metrics)))
    def to_dict(self) -> dict[str, object]:
        return {"pattern_uuid": self.pattern_uuid, "status": self.status, "checks": dict(self.checks),
                "metrics": dict(self.metrics), "outlier_count": self.outlier_count, "validation_version": self.validation_version}
    @classmethod
    def from_dict(cls, value: Mapping[str, object]) -> "ValidationResult":
        return cls(str(value["pattern_uuid"]), str(value["status"]), value["checks"], value["metrics"],
                   int(value.get("outlier_count", 0)), str(value.get("validation_version", VALIDATION_VERSION))) # type: ignore[arg-type]
