"""Immutable representation of one explicit Knowledge Lifecycle transition."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Mapping
from uuid import uuid4

from .schema import LIFECYCLE_SCHEMA_VERSION


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="microseconds").replace("+00:00", "Z")


@dataclass(frozen=True)
class LifecycleTransition:
    """An append-only audit event; it never grants runtime authority."""

    knowledge_uuid: str
    previous_state: str
    new_state: str
    triggering_component: str
    reason: str
    governance_version: str
    lifecycle_version: str
    timestamp: str
    transition_uuid: str
    schema_version: str = LIFECYCLE_SCHEMA_VERSION

    @classmethod
    def create(cls, *, knowledge_uuid: str, previous_state: str, new_state: str,
               triggering_component: str, reason: str, governance_version: str,
               lifecycle_version: str, timestamp: str | None = None,
               transition_uuid: str | None = None) -> "LifecycleTransition":
        return cls(
            knowledge_uuid=knowledge_uuid,
            previous_state=previous_state,
            new_state=new_state,
            triggering_component=triggering_component,
            reason=reason,
            governance_version=governance_version,
            lifecycle_version=lifecycle_version,
            timestamp=timestamp or utc_now(),
            transition_uuid=transition_uuid or str(uuid4()),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "transition_uuid": self.transition_uuid,
            "knowledge_uuid": self.knowledge_uuid,
            "timestamp": self.timestamp,
            "previous_state": self.previous_state,
            "new_state": self.new_state,
            "triggering_component": self.triggering_component,
            "reason": self.reason,
            "governance_version": self.governance_version,
            "lifecycle_version": self.lifecycle_version,
            "schema_version": self.schema_version,
        }

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> "LifecycleTransition":
        return cls(
            transition_uuid=str(value["transition_uuid"]), knowledge_uuid=str(value["knowledge_uuid"]),
            timestamp=str(value["timestamp"]), previous_state=str(value["previous_state"]),
            new_state=str(value["new_state"]), triggering_component=str(value["triggering_component"]),
            reason=str(value["reason"]), governance_version=str(value["governance_version"]),
            lifecycle_version=str(value["lifecycle_version"]),
            schema_version=str(value.get("schema_version", LIFECYCLE_SCHEMA_VERSION)),
        )
