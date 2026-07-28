"""Deeply immutable context passed across the V28 foundation pipeline."""
from __future__ import annotations
from dataclasses import dataclass
from types import MappingProxyType
from typing import Any, Mapping


def deep_freeze(value: Any) -> Any:
    if isinstance(value, Mapping):
        return MappingProxyType({key: deep_freeze(item) for key, item in value.items()})
    if isinstance(value, (list, tuple)):
        return tuple(deep_freeze(item) for item in value)
    if isinstance(value, set):
        return frozenset(deep_freeze(item) for item in value)
    return value


@dataclass(frozen=True)
class RuntimeContext:
    market: Mapping[str, Any]
    observed_at: float
    heartbeat_age_seconds: float
    source_heartbeat_unix: float
    runtime_version: str = "V28.PR-A"

    def __post_init__(self) -> None:
        object.__setattr__(self, "market", deep_freeze(self.market))


def construct_runtime_context(market: Mapping[str, Any], *, now: float) -> RuntimeContext:
    heartbeat = float(market["heartbeat_unix"])
    return RuntimeContext(market, now, max(0.0, now - heartbeat), heartbeat)
