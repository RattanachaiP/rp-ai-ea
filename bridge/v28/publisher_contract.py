"""Immutable contracts at the PR264 execution-integration boundary."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

from .execution_plan import _finite, identity, parse_utc


@dataclass(frozen=True)
class RuntimeHealthSnapshot:
    healthy: bool
    sequence_id: int
    observed_at: str
    boundary_age_seconds: float

    def __post_init__(self) -> None:
        if type(self.healthy) is not bool or type(self.sequence_id) is not int or self.sequence_id < 0:
            raise ValueError("RUNTIME_HEALTH_INVALID")
        parse_utc(self.observed_at)
        _finite(self.boundary_age_seconds, nonnegative=True)


@dataclass(frozen=True)
class BrokerSnapshot:
    symbol: str
    sequence_id: int
    observed_at: str
    available: bool

    def __post_init__(self) -> None:
        if not self.symbol or type(self.sequence_id) is not int or self.sequence_id < 0 or type(self.available) is not bool:
            raise ValueError("BROKER_SNAPSHOT_INVALID")
        parse_utc(self.observed_at)


@dataclass(frozen=True)
class PublishedExecutionPlan:
    """Integrity envelope; ``payload`` is the unchanged canonical plan payload."""

    payload: Mapping[str, Any]
    execution_plan_replay_identity: str
    decision_replay_identity: str
    runtime_sequence_id: int
    execution_replay_identity: str
    schema_version: str = "V28.PUBLISHED_EXECUTION_PLAN.1.0"

    def canonical_payload(self) -> dict[str, Any]:
        return {
            "payload": dict(self.payload),
            "execution_plan_replay_identity": self.execution_plan_replay_identity,
            "decision_replay_identity": self.decision_replay_identity,
            "runtime_sequence_id": self.runtime_sequence_id,
            "schema_version": self.schema_version,
        }

    def __post_init__(self) -> None:
        from types import MappingProxyType
        if type(self.runtime_sequence_id) is not int or self.runtime_sequence_id < 0:
            raise ValueError("PUBLISHER_LINEAGE_INVALID")
        if not self.execution_plan_replay_identity or not self.decision_replay_identity:
            raise ValueError("PUBLISHER_LINEAGE_INVALID")
        object.__setattr__(self, "payload", MappingProxyType(dict(self.payload)))
        expected = identity("V28_EXECUTION_PUBLICATION_REPLAY", self.canonical_payload())
        if self.execution_replay_identity != expected:
            raise ValueError("PUBLISHED_PAYLOAD_INTEGRITY_INVALID")

