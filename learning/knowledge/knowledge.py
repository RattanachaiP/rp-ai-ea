"""Canonical immutable record of a statistically verified learning outcome."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from types import MappingProxyType
from typing import Any, Mapping
from uuid import uuid4

from .schema import KNOWLEDGE_VERSION


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="microseconds").replace("+00:00", "Z")


def _freeze(value: Any) -> Any:
    """Recursively detach JSON-like values from their mutable input containers."""
    if isinstance(value, Mapping):
        return MappingProxyType({key: _freeze(item) for key, item in value.items()})
    if isinstance(value, (list, tuple)):
        return tuple(_freeze(item) for item in value)
    if isinstance(value, (set, frozenset)):
        return frozenset(_freeze(item) for item in value)
    if isinstance(value, bytearray):
        return bytes(value)
    return value


def _serialize(value: Any) -> Any:
    """Create a detached, JSON-compatible representation of frozen data."""
    if isinstance(value, Mapping):
        return {key: _serialize(item) for key, item in value.items()}
    if isinstance(value, tuple):
        return [_serialize(item) for item in value]
    if isinstance(value, frozenset):
        return [_serialize(item) for item in sorted(value, key=repr)]
    return value


@dataclass(frozen=True)
class Knowledge:
    knowledge_uuid: str
    knowledge_version: int
    pattern_uuid: str
    validation_uuid: str
    created_timestamp: str
    applicable_symbols: tuple[str, ...]
    applicable_sessions: tuple[str, ...]
    applicable_market_states: tuple[str, ...]
    sample_count: int
    verified_win_rate: float
    average_rr: float
    confidence_placeholder: Any
    knowledge_status: str = "ACTIVE"
    schema_version: str = KNOWLEDGE_VERSION

    def __post_init__(self) -> None:
        object.__setattr__(self, "applicable_symbols", tuple(_freeze(item) for item in self.applicable_symbols))
        object.__setattr__(self, "applicable_sessions", tuple(_freeze(item) for item in self.applicable_sessions))
        object.__setattr__(self, "applicable_market_states", tuple(_freeze(item) for item in self.applicable_market_states))
        object.__setattr__(self, "confidence_placeholder", _freeze(self.confidence_placeholder))

    @property
    def status(self) -> str:
        """Compatibility alias for the record's knowledge lifecycle status."""
        return self.knowledge_status

    @classmethod
    def create(cls, *, pattern_uuid: str, validation_uuid: str, applicable_symbols: tuple[str, ...] = (),
               applicable_sessions: tuple[str, ...] = (), applicable_market_states: tuple[str, ...] = (),
               sample_count: int, verified_win_rate: float, average_rr: float,
               confidence_placeholder: Any = None, knowledge_status: str = "ACTIVE",
               knowledge_uuid: str | None = None, knowledge_version: int = 1,
               created_timestamp: str | None = None) -> "Knowledge":
        return cls(knowledge_uuid or str(uuid4()), knowledge_version, pattern_uuid, validation_uuid,
                   created_timestamp or utc_now(), tuple(applicable_symbols), tuple(applicable_sessions),
                   tuple(applicable_market_states), sample_count, verified_win_rate, average_rr,
                   confidence_placeholder, knowledge_status)

    def to_dict(self) -> dict[str, Any]:
        return {
            "knowledge_uuid": self.knowledge_uuid, "knowledge_version": self.knowledge_version,
            "pattern_uuid": self.pattern_uuid, "validation_uuid": self.validation_uuid,
            "created_timestamp": self.created_timestamp, "applicable_symbols": list(self.applicable_symbols),
            "applicable_sessions": list(self.applicable_sessions),
            "applicable_market_states": list(self.applicable_market_states), "sample_count": self.sample_count,
            "verified_win_rate": self.verified_win_rate, "average_rr": self.average_rr,
            "confidence_placeholder": _serialize(self.confidence_placeholder), "knowledge_status": self.knowledge_status,
            "schema_version": self.schema_version,
        }

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> "Knowledge":
        return cls(str(value["knowledge_uuid"]), int(value["knowledge_version"]), str(value["pattern_uuid"]),
                   str(value["validation_uuid"]), str(value["created_timestamp"]),
                   tuple(str(item) for item in value["applicable_symbols"]),
                   tuple(str(item) for item in value["applicable_sessions"]),
                   tuple(str(item) for item in value["applicable_market_states"]), int(value["sample_count"]),
                   float(value["verified_win_rate"]), float(value["average_rr"]),
                   value.get("confidence_placeholder"), str(value["knowledge_status"]),
                   str(value.get("schema_version", KNOWLEDGE_VERSION)))
