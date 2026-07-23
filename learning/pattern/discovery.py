"""Offline pattern discovery; it has no authority to execute or recommend trades."""
from __future__ import annotations
from collections.abc import Iterable, Mapping
import json
from uuid import NAMESPACE_URL, uuid5
from .aggregation import aggregate_groups
from .candidate import CandidatePattern
from .grouping import conditions_for, group_records
from .repository import PatternRepository

class PatternDiscovery:
    def __init__(self, repository: PatternRepository | None = None, *, minimum_samples: int = 30):
        if minimum_samples < 1: raise ValueError("MINIMUM_SAMPLES_MUST_BE_POSITIVE")
        self.repository = repository or PatternRepository()
        self.minimum_samples = minimum_samples
    def discover(self, records: Iterable[Mapping[str, object]]) -> list[CandidatePattern]:
        patterns = []
        for conditions, statistics in aggregate_groups(group_records(records)):
            identity = json.dumps(conditions, sort_keys=True, separators=(",", ":"), default=str)
            candidate = CandidatePattern.create(conditions, statistics, minimum_samples=self.minimum_samples,
                pattern_uuid=str(uuid5(NAMESPACE_URL, "rp-ai-ea/pattern/" + identity)))
            self.repository.save(candidate); patterns.append(candidate)
        return patterns
    def discover_incremental(self, records: Iterable[Mapping[str, object]]) -> list[CandidatePattern]:
        """Persist groups not already present; existing patterns are immutable."""
        existing = {tuple(sorted(item.conditions.items())) for item in self.repository.query_patterns()}
        fresh = (record for record in records if tuple(sorted(conditions_for(record).items())) not in existing)
        return self.discover(fresh)

def discover(records: Iterable[Mapping[str, object]], *, repository: PatternRepository | None = None, minimum_samples: int = 30) -> list[CandidatePattern]:
    return PatternDiscovery(repository, minimum_samples=minimum_samples).discover(records)
def discover_incremental(records: Iterable[Mapping[str, object]], *, repository: PatternRepository | None = None, minimum_samples: int = 30) -> list[CandidatePattern]:
    return PatternDiscovery(repository, minimum_samples=minimum_samples).discover_incremental(records)
