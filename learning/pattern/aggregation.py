from __future__ import annotations
from collections.abc import Iterable, Mapping
from .statistics import calculate_statistics
def aggregate_groups(groups: Iterable[tuple[dict[str, object], list[Mapping[str, object]]]]) -> list[tuple[dict[str, object], dict[str, float | int]]]:
    return [(conditions, calculate_statistics(records)) for conditions, records in groups]
class AggregationEngine:
    aggregate = staticmethod(aggregate_groups)
