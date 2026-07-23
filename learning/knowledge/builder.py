"""Build immutable knowledge exclusively from verified pattern results."""
from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any, Iterable

from .knowledge import Knowledge


class KnowledgeBuilder:
    """Transforms a VERIFIED validation result into one knowledge version."""

    def build(self, verified_pattern: Mapping[str, Any] | Any, *, existing: Iterable[Knowledge] = (),
              knowledge_uuid: str | None = None, knowledge_status: str = "ACTIVE",
              confidence_placeholder: Any = None) -> Knowledge:
        status = self._value(verified_pattern, "status")
        if status != "VERIFIED":
            raise ValueError("PATTERN_NOT_VERIFIED")
        pattern_uuid = self._value(verified_pattern, "pattern_uuid")
        validation_uuid = self._value(verified_pattern, "validation_uuid")
        if not pattern_uuid or not validation_uuid:
            raise ValueError("VERIFIED_LINEAGE_REQUIRED")
        statistics = self._value(verified_pattern, "statistics", {}) or {}
        if not isinstance(statistics, Mapping):
            raise ValueError("INVALID_STATISTICS")
        prior_versions = [item.knowledge_version for item in existing if item.pattern_uuid == str(pattern_uuid)]
        conditions = self._value(verified_pattern, "conditions", {}) or {}
        if not isinstance(conditions, Mapping):
            raise ValueError("INVALID_CONDITIONS")
        return Knowledge.create(
            knowledge_uuid=knowledge_uuid, knowledge_version=max(prior_versions, default=0) + 1,
            pattern_uuid=str(pattern_uuid), validation_uuid=str(validation_uuid),
            applicable_symbols=self._values(verified_pattern, conditions, "applicable_symbols", "symbols", "symbol"),
            applicable_sessions=self._values(verified_pattern, conditions, "applicable_sessions", "sessions", "session"),
            applicable_market_states=self._values(verified_pattern, conditions, "applicable_market_states", "market_states", "market_state", "state"),
            sample_count=int(self._statistic(verified_pattern, statistics, "sample_count", "samples")),
            verified_win_rate=float(self._statistic(verified_pattern, statistics, "verified_win_rate", "win_rate")),
            average_rr=float(self._statistic(verified_pattern, statistics, "average_rr", "avg_rr")),
            confidence_placeholder=(self._value(verified_pattern, "confidence_placeholder")
                                    if confidence_placeholder is None else confidence_placeholder),
            knowledge_status=knowledge_status,
        )

    @staticmethod
    def _value(source: Mapping[str, Any] | Any, name: str, default: Any = None) -> Any:
        return source.get(name, default) if isinstance(source, Mapping) else getattr(source, name, default)

    def _statistic(self, source: Mapping[str, Any] | Any, statistics: Mapping[str, Any], *names: str) -> Any:
        for name in names:
            value = self._value(source, name)
            if value is not None:
                return value
            if name in statistics:
                return statistics[name]
        raise ValueError("VERIFIED_STATISTICS_REQUIRED:" + names[0])

    def _values(self, source: Mapping[str, Any] | Any, conditions: Mapping[str, Any], *names: str) -> tuple[str, ...]:
        for name in names:
            value = self._value(source, name)
            if value is None:
                value = conditions.get(name)
            if value is not None:
                if isinstance(value, str):
                    return (value,)
                if isinstance(value, Sequence) and not isinstance(value, (bytes, bytearray)):
                    return tuple(str(item) for item in value)
                raise ValueError("INVALID_APPLICABILITY")
        return ()
