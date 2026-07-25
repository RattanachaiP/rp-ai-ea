"""Immutable grouping-only indexes over a Pattern Memory snapshot."""
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
    by_report_uuid: Mapping[str, tuple[PatternMemoryRecord, ...]]
    by_source_attribution_uuid: Mapping[str, tuple[PatternMemoryRecord, ...]]
    by_evidence_envelope_uuid: Mapping[str, tuple[PatternMemoryRecord, ...]]
    by_source_digest: Mapping[str, tuple[PatternMemoryRecord, ...]]
    by_replay_digest: Mapping[str, tuple[PatternMemoryRecord, ...]]
    by_mining_config_digest: Mapping[str, tuple[PatternMemoryRecord, ...]]
    by_memory_state: Mapping[str, tuple[PatternMemoryRecord, ...]]

    @classmethod
    def build(cls, records: tuple[PatternMemoryRecord, ...]) -> "PatternMemoryIndex":
        def grouped(field: str):
            values: dict[str, list[PatternMemoryRecord]] = {}
            for record in records:
                values.setdefault(getattr(record, field), []).append(record)
            return MappingProxyType({key: tuple(value) for key, value in sorted(values.items())})
        fields = ("pattern_uuid", "knowledge_uuid", "policy_uuid", "pattern_hash", "report_uuid",
                  "source_attribution_uuid", "evidence_envelope_uuid", "source_digest", "replay_digest",
                  "mining_config_digest", "memory_state")
        grouped_indexes = [grouped(field) for field in fields]
        return cls(grouped_indexes[0], grouped_indexes[1], grouped_indexes[2],
                   MappingProxyType({item.memory_uuid: item for item in records}), *grouped_indexes[3:])
