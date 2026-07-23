from __future__ import annotations
from dataclasses import dataclass
from types import MappingProxyType
from typing import Mapping
from uuid import uuid4
from .schema import PATTERN_VERSION

@dataclass(frozen=True)
class CandidatePattern:
    pattern_uuid: str
    pattern_version: str
    conditions: Mapping[str, object]
    statistics: Mapping[str, float | int]
    status: str
    def __post_init__(self) -> None:
        object.__setattr__(self, "conditions", MappingProxyType(dict(self.conditions)))
        object.__setattr__(self, "statistics", MappingProxyType(dict(self.statistics)))
    @classmethod
    def create(cls, conditions: Mapping[str, object], statistics: Mapping[str, float | int], *, minimum_samples: int = 30, pattern_uuid: str | None = None) -> "CandidatePattern":
        status = "CANDIDATE" if int(statistics["samples"]) >= minimum_samples else "INSUFFICIENT_DATA"
        return cls(pattern_uuid or str(uuid4()), PATTERN_VERSION, conditions, statistics, status)
    def to_dict(self) -> dict[str, object]:
        return {"pattern_uuid": self.pattern_uuid, "pattern_version": self.pattern_version, "conditions": dict(self.conditions), "statistics": dict(self.statistics), "status": self.status}
    @classmethod
    def from_dict(cls, value: Mapping[str, object]) -> "CandidatePattern":
        return cls(str(value["pattern_uuid"]), str(value["pattern_version"]), value["conditions"], value["statistics"], str(value["status"])) # type: ignore[arg-type]
