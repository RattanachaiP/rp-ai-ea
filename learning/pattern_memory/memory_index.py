"""Immutable indexes over a Pattern Memory snapshot."""
from __future__ import annotations

from dataclasses import dataclass
from types import MappingProxyType
from typing import Mapping

from .models import PatternMemoryRecord


@dataclass(frozen=True)
class PatternMemoryIndex:
    by_pattern_uuid: Mapping[str, tuple[PatternMemoryRecord, ...]]
    by_knowledge_uuid: Mapping[str, tuple[PatternMemoryRecord, ...]]
    by_policy_uuid: Mapping[str, tuple[PatternMemoryRecord, ...]]
    by_memory_uuid: Mapping[str, PatternMemoryRecord]
    by_pattern_hash: Mapping[str, tuple[PatternMemoryRecord, ...]]

    @classmethod
    def build(cls, records: tuple[PatternMemoryRecord, ...]) -> "PatternMemoryIndex":
        def grouped(field: str) -> Mapping[str, tuple[PatternMemoryRecord, ...]]:
            values: dict[str, list[PatternMemoryRecord]] = {}
            for record in records:
                values.setdefault(getattr(record, field), []).append(record)
            return MappingProxyType({key: tuple(value) for key, value in sorted(values.items())})
        return cls(grouped("pattern_uuid"), grouped("knowledge_uuid"), grouped("policy_uuid"),
                   MappingProxyType({x.memory_uuid: x for x in records}), grouped("pattern_hash"))
