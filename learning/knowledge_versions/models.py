"""Immutable contracts owned by the PR167 Knowledge Version Manager."""
from __future__ import annotations
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Mapping
from uuid import UUID
from learning.common.immutable import freeze, thaw

VERSION_STATES = frozenset({"ACTIVE", "INACTIVE", "SUPERSEDED", "RETIRED", "ROLLED_BACK", "ARCHIVED"})

def valid_uuid(value: object) -> bool:
    try: UUID(str(value)); return True
    except (ValueError, TypeError, AttributeError): return False

def valid_time(value: object) -> bool:
    try: return datetime.fromisoformat(str(value).replace("Z", "+00:00")).tzinfo is not None
    except (ValueError, TypeError, AttributeError): return False

def valid_digest(value: object) -> bool:
    return isinstance(value, str) and len(value) == 64 and all(c in "0123456789abcdef" for c in value.lower())

@dataclass(frozen=True)
class KnowledgeVersion:
    version_uuid: str
    version_digest: str
    semantic_version: str
    created_at: str
    knowledge_uuid: str
    activation_uuid: str
    architecture_version: str
    state: str
    parent_version_uuid: str = ""
    rollback_parent_uuid: str = ""
    metadata: Mapping[str, Any] = field(default_factory=dict)
    def __post_init__(self) -> None:
        if (not all(valid_uuid(getattr(self, x)) for x in ("version_uuid", "knowledge_uuid", "activation_uuid"))
            or not valid_digest(self.version_digest) or not valid_time(self.created_at)
            or not isinstance(self.semantic_version, str) or not self.semantic_version
            or not isinstance(self.architecture_version, str) or not self.architecture_version
            or self.state not in VERSION_STATES or not isinstance(self.metadata, Mapping)
            or (self.parent_version_uuid and not valid_uuid(self.parent_version_uuid))
            or (self.rollback_parent_uuid and not valid_uuid(self.rollback_parent_uuid))):
            raise ValueError("INVALID_KNOWLEDGE_VERSION")
        object.__setattr__(self, "metadata", freeze(dict(self.metadata)))
    def to_dict(self) -> dict[str, Any]: return {x: thaw(getattr(self, x)) for x in self.__dataclass_fields__}

@dataclass(frozen=True)
class KnowledgeVersionManifest:
    version_uuid: str
    manifest_digest: str
    compatibility: Mapping[str, str]
    activation_package: Mapping[str, Any]
    promotion_package: Mapping[str, Any]
    registry_snapshot: Mapping[str, Any]
    def __post_init__(self) -> None:
        required = {"architecture_version", "policy_version", "registry_version", "runtime_contract", "knowledge_contract", "applicability_contract"}
        if not valid_uuid(self.version_uuid) or not valid_digest(self.manifest_digest) or not required.issubset(self.compatibility) or any(not isinstance(self.compatibility[x], str) or not self.compatibility[x] for x in required):
            raise ValueError("INVALID_KNOWLEDGE_VERSION_MANIFEST")
        object.__setattr__(self, "compatibility", freeze(dict(self.compatibility)))
        for name in ("activation_package", "promotion_package", "registry_snapshot"):
            value = getattr(self, name)
            if not isinstance(value, Mapping): raise ValueError("INVALID_KNOWLEDGE_VERSION_MANIFEST")
            object.__setattr__(self, name, freeze(dict(value)))
    def to_dict(self) -> dict[str, Any]: return {x: thaw(getattr(self, x)) for x in self.__dataclass_fields__}

@dataclass(frozen=True)
class KnowledgeLineage:
    version_uuid: str
    parent_version_uuid: str
    children: tuple[str, ...]
    branch: tuple[str, ...]
    merge_history: tuple[str, ...] = ()
    def __post_init__(self) -> None:
        if not valid_uuid(self.version_uuid) or (self.parent_version_uuid and not valid_uuid(self.parent_version_uuid)) or any(not valid_uuid(x) for x in (*self.children, *self.branch, *self.merge_history)):
            raise ValueError("INVALID_KNOWLEDGE_LINEAGE")
    def to_dict(self) -> dict[str, Any]: return {"version_uuid": self.version_uuid, "parent_version_uuid": self.parent_version_uuid, "children": list(self.children), "branch": list(self.branch), "merge_history": list(self.merge_history)}

@dataclass(frozen=True)
class KnowledgeRollbackDescriptor:
    version_uuid: str
    rollback_parent_uuid: str
    eligible: bool
    reason: str
    compatible: bool
    def __post_init__(self) -> None:
        if not valid_uuid(self.version_uuid) or (self.rollback_parent_uuid and not valid_uuid(self.rollback_parent_uuid)) or not isinstance(self.eligible, bool) or not isinstance(self.compatible, bool) or not isinstance(self.reason, str) or not self.reason:
            raise ValueError("INVALID_KNOWLEDGE_ROLLBACK_DESCRIPTOR")
    def to_dict(self) -> dict[str, Any]: return {x: getattr(self, x) for x in self.__dataclass_fields__}

KnowledgeVersionHistory = tuple[KnowledgeVersion, ...]
