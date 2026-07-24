"""Immutable contracts for the Active Knowledge Registry."""
from __future__ import annotations
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Mapping
from uuid import UUID
from learning.common.immutable import freeze, thaw

STATUSES = frozenset({"ACTIVE", "SUPERSEDED", "RETIRED", "ARCHIVED"})

def _uuid(value: object) -> bool:
    try: UUID(str(value)); return True
    except (ValueError, TypeError, AttributeError): return False

def _timestamp(value: object) -> bool:
    try: return datetime.fromisoformat(str(value).replace("Z", "+00:00")).tzinfo is not None
    except (ValueError, TypeError, AttributeError): return False

@dataclass(frozen=True)
class ActiveKnowledgeEntry:
    """One append-only registry event; consumers receive only projected records."""
    activation_uuid: str
    knowledge_uuid: str
    semantic_identity: str
    activation_timestamp: str
    activation_reason: str
    promotion_decision_uuid: str
    promotion_record_uuid: str
    schema_version: str
    configuration_version: str
    lineage_reference: str
    status: str = "ACTIVE"
    replaces_activation_uuid: str = ""
    superseded_by_knowledge_uuid: str = ""
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        required_uuids = (self.activation_uuid, self.knowledge_uuid, self.promotion_decision_uuid, self.promotion_record_uuid)
        if (not all(_uuid(value) for value in required_uuids) or not _timestamp(self.activation_timestamp)
                or self.status not in STATUSES
                or not all(isinstance(value, str) and value for value in (
                    self.semantic_identity, self.activation_reason, self.schema_version,
                    self.configuration_version, self.lineage_reference))):
            raise ValueError("INVALID_ACTIVE_REGISTRY_ENTRY")
        if self.replaces_activation_uuid and not _uuid(self.replaces_activation_uuid):
            raise ValueError("INVALID_ACTIVE_REGISTRY_ENTRY")
        if self.superseded_by_knowledge_uuid and not _uuid(self.superseded_by_knowledge_uuid):
            raise ValueError("INVALID_ACTIVE_REGISTRY_ENTRY")
        if self.status == "SUPERSEDED" and not self.superseded_by_knowledge_uuid:
            raise ValueError("INVALID_SUPERSESSION_REFERENCE")
        object.__setattr__(self, "metadata", freeze(dict(self.metadata)))

    def to_dict(self) -> dict[str, Any]:
        return {name: thaw(getattr(self, name)) for name in self.__dataclass_fields__}
