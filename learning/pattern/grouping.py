"""Deterministic grouping of dataset records by their feature conditions."""
from __future__ import annotations
from collections.abc import Iterable, Mapping
import json

_OUTCOME_KEYS = frozenset({"profit", "net_profit", "pnl", "realized_profit", "result", "win_loss", "rr", "mae", "mfe", "holding", "holding_time", "duration", "duration_seconds"})

def conditions_for(record: Mapping[str, object]) -> dict[str, object]:
    """Return an ordered-independent condition mapping, excluding outcomes."""
    source = record.get("features", record.get("conditions", record))
    if not isinstance(source, Mapping):
        raise ValueError("FEATURES_REQUIRED")
    return {str(key): value for key, value in source.items() if key not in _OUTCOME_KEYS}

def group_records(records: Iterable[Mapping[str, object]]) -> list[tuple[dict[str, object], list[Mapping[str, object]]]]:
    grouped: dict[str, tuple[dict[str, object], list[Mapping[str, object]]]] = {}
    for record in records:
        conditions = conditions_for(record)
        try:
            key = json.dumps(conditions, sort_keys=True, separators=(",", ":"), allow_nan=False, default=str)
        except (TypeError, ValueError) as error:
            raise ValueError("NON_SERIALIZABLE_CONDITIONS") from error
        if key not in grouped:
            grouped[key] = (dict(sorted(conditions.items())), [])
        grouped[key][1].append(record)
    return [grouped[key] for key in sorted(grouped)]

class GroupingEngine:
    group = staticmethod(group_records)
