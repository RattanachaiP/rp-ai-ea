"""Immutable context passed across the V28 foundation pipeline."""
from dataclasses import dataclass
from types import MappingProxyType
from typing import Any, Mapping


@dataclass(frozen=True)
class RuntimeContext:
    market: Mapping[str, Any]
    observed_at: float
    heartbeat_age_seconds: float
    runtime_version: str = "V28.PR-A"

    def __post_init__(self) -> None:
        object.__setattr__(self, "market", MappingProxyType(dict(self.market)))


def construct_runtime_context(market: Mapping[str, Any], *, now: float) -> RuntimeContext:
    return RuntimeContext(market, now, max(0.0, now - float(market["heartbeat_unix"])))
