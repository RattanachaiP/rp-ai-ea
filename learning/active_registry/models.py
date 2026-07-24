"""Immutable contracts for the trusted Active Knowledge Registry projection."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Mapping
from uuid import UUID

from learning.common.immutable import freeze, thaw

EVENT_TYPES = frozenset({"ACTIVATION", "SUPERSESSION", "RETIREMENT", "ARCHIVAL"})
STATUSES = frozenset({"ACTIVE", "SUPERSEDED", "RETIRED", "ARCHIVED"})


def _uuid(value: object) -> bool:
    try:
        UUID(str(value))
        return True
    except (ValueError, TypeError, AttributeError):
        return False


def _timestamp(value: object) -> bool:
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00")).tzinfo is not None
    except (ValueError, TypeError, AttributeError):
        return False


@dataclass(frozen=True)
class ActiveKnowledgeEntry:
    """One immutable trusted registry event or deterministic projected state."""

    activation_uuid: str
    knowledge_uuid: str
    semantic_identity: str
    activation_timestamp: str
    activation_reason: str
    source_receipt_uuid: str
    source_event_uuid: str
    source_authority: str
    schema_version: str
    configuration_version: str
    lineage_reference: str
    event_type: str = "ACTIVATION"
    sequence: int = 1
    status: str = "ACTIVE"
    previous_knowledge_uuid: str = ""
    previous_activation_uuid: str = ""
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        required_uuids = (
            self.activation_uuid,
            self.knowledge_uuid,
            self.source_receipt_uuid,
            self.source_event_uuid,
        )
        required_text = (
            self.semantic_identity,
            self.activation_reason,
            self.source_authority,
            self.schema_version,
            self.configuration_version,
            self.lineage_reference,
        )
        if (
            not all(_uuid(value) for value in required_uuids)
            or not _timestamp(self.activation_timestamp)
            or self.event_type not in EVENT_TYPES
            or self.status not in STATUSES
            or not isinstance(self.sequence, int)
            or isinstance(self.sequence, bool)
            or self.sequence < 1
            or not all(isinstance(value, str) and value.strip() for value in required_text)
            or not isinstance(self.metadata, Mapping)
        ):
            raise ValueError("INVALID_ACTIVE_REGISTRY_ENTRY")

        if self.event_type == "ACTIVATION":
            valid = self.status == "ACTIVE" and not self.previous_knowledge_uuid and not self.previous_activation_uuid
        elif self.event_type == "SUPERSESSION":
            active_replacement = (
                self.status == "ACTIVE"
                and _uuid(self.previous_knowledge_uuid)
                and _uuid(self.previous_activation_uuid)
                and self.previous_knowledge_uuid != self.knowledge_uuid
            )
            projected_prior = (
                self.status == "SUPERSEDED"
                and _uuid(self.previous_knowledge_uuid)
                and _uuid(self.previous_activation_uuid)
                and self.previous_knowledge_uuid == self.knowledge_uuid
            )
            valid = active_replacement or projected_prior
        elif self.event_type == "RETIREMENT":
            valid = self.status == "RETIRED" and not self.previous_knowledge_uuid and _uuid(self.previous_activation_uuid)
        else:
            valid = self.status == "ARCHIVED" and not self.previous_knowledge_uuid and _uuid(self.previous_activation_uuid)
        if not valid:
            raise ValueError("INVALID_ACTIVE_REGISTRY_TRANSITION")

        object.__setattr__(self, "metadata", freeze(dict(self.metadata)))

    def to_dict(self) -> dict[str, Any]:
        return {name: thaw(getattr(self, name)) for name in self.__dataclass_fields__}
