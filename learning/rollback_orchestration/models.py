"""Immutable, runtime-isolated contracts for PR169 rollback orchestration."""
from __future__ import annotations
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Mapping
from uuid import UUID
from learning.common.immutable import freeze, thaw

ROLLBACK_STATES = frozenset({"REQUESTED", "VALIDATING", "AWAITING_APPROVAL", "AUTHORIZED", "EXECUTION_PENDING", "COMPLETED", "FAILED", "REJECTED", "CANCELLED", "EXPIRED"})

def valid_uuid(value: object) -> bool:
    try: return str(UUID(str(value))) == str(value).lower()
    except (ValueError, TypeError, AttributeError): return False
def valid_digest(value: object) -> bool:
    return isinstance(value, str) and len(value) == 64 and all(c in "0123456789abcdef" for c in value.lower())
def valid_time(value: object) -> bool:
    try: return datetime.fromisoformat(str(value).replace("Z", "+00:00")).tzinfo is not None
    except (ValueError, TypeError, AttributeError): return False

@dataclass(frozen=True)
class RollbackRequest:
    request_uuid: str; knowledge_uuid: str; current_version_uuid: str; target_version_uuid: str; reason: str; requested_at: str
    expires_at: str = ""
    def __post_init__(self):
        if not all(valid_uuid(getattr(self, x)) for x in ("request_uuid", "knowledge_uuid", "current_version_uuid", "target_version_uuid")) or self.current_version_uuid == self.target_version_uuid or not self.reason or not valid_time(self.requested_at) or (self.expires_at and not valid_time(self.expires_at)): raise ValueError("INVALID_ROLLBACK_REQUEST")
    def to_dict(self): return {x: getattr(self, x) for x in self.__dataclass_fields__}

@dataclass(frozen=True)
class RollbackPolicy:
    version: str = "1.0"; architecture_version: str = "PR169"; approval_mode: str = "MANUAL_ONLY"; authorization_ttl_seconds: int = 86400; evaluation_timestamp: str = ""
    def __post_init__(self):
        if not self.version or not self.architecture_version or self.approval_mode != "MANUAL_ONLY" or not isinstance(self.authorization_ttl_seconds, int) or isinstance(self.authorization_ttl_seconds, bool) or self.authorization_ttl_seconds < 0 or (self.evaluation_timestamp and not valid_time(self.evaluation_timestamp)): raise ValueError("INVALID_ROLLBACK_POLICY")
    def to_dict(self): return {x: getattr(self, x) for x in self.__dataclass_fields__}

@dataclass(frozen=True)
class HumanApproval:
    approver: str; approved_at: str; reason: str
    def __post_init__(self):
        if not self.approver or not self.reason or not valid_time(self.approved_at): raise ValueError("INVALID_HUMAN_APPROVAL")
    def to_dict(self): return {x: getattr(self, x) for x in self.__dataclass_fields__}

@dataclass(frozen=True)
class RollbackAssessment:
    request_uuid: str; state: str; reason: str; replay_digest: str; assessed_at: str
    def __post_init__(self):
        if not valid_uuid(self.request_uuid) or self.state not in ROLLBACK_STATES or not self.reason or not valid_digest(self.replay_digest) or not valid_time(self.assessed_at): raise ValueError("INVALID_ROLLBACK_ASSESSMENT")
    def to_dict(self): return {x: getattr(self, x) for x in self.__dataclass_fields__}

@dataclass(frozen=True)
class RollbackDecision:
    rollback_uuid: str; request_uuid: str; knowledge_uuid: str; current_version_uuid: str; target_version_uuid: str; state: str; reason: str; policy_version: str; architecture_version: str; replay_digest: str; created_at: str
    def __post_init__(self):
        if not all(valid_uuid(getattr(self, x)) for x in ("rollback_uuid", "request_uuid", "knowledge_uuid", "current_version_uuid", "target_version_uuid")) or self.state not in ROLLBACK_STATES or not all(getattr(self, x) for x in ("reason", "policy_version", "architecture_version")) or not valid_digest(self.replay_digest) or not valid_time(self.created_at): raise ValueError("INVALID_ROLLBACK_DECISION")
    def to_dict(self): return {x: getattr(self, x) for x in self.__dataclass_fields__}

@dataclass(frozen=True)
class RollbackAuthorization:
    rollback_uuid: str; approver: str; approved_at: str; reason: str; expires_at: str
    def __post_init__(self):
        if not valid_uuid(self.rollback_uuid) or not self.approver or not self.reason or not valid_time(self.approved_at) or not valid_time(self.expires_at): raise ValueError("INVALID_ROLLBACK_AUTHORIZATION")
    def to_dict(self): return {x: getattr(self, x) for x in self.__dataclass_fields__}

@dataclass(frozen=True)
class RollbackPlan:
    rollback_uuid: str; current_version_uuid: str; target_version_uuid: str; current_registry_digest: str; target_registry_digest: str; execution_not_before: str; expiration: str
    def __post_init__(self):
        if not all(valid_uuid(getattr(self, x)) for x in ("rollback_uuid", "current_version_uuid", "target_version_uuid")) or not valid_digest(self.current_registry_digest) or not valid_digest(self.target_registry_digest) or not valid_time(self.execution_not_before) or not valid_time(self.expiration): raise ValueError("INVALID_ROLLBACK_PLAN")
    def to_dict(self): return {x: getattr(self, x) for x in self.__dataclass_fields__}

@dataclass(frozen=True)
class RollbackAudit:
    rollback_uuid: str; request_uuid: str; event: str; timestamp: str; reason: str
    def __post_init__(self):
        if not valid_uuid(self.rollback_uuid) or not valid_uuid(self.request_uuid) or not self.event or not self.reason or not valid_time(self.timestamp): raise ValueError("INVALID_ROLLBACK_AUDIT")
    def to_dict(self): return {x: getattr(self, x) for x in self.__dataclass_fields__}
RollbackHistory = RollbackAudit

@dataclass(frozen=True)
class RollbackPackage:
    decision: RollbackDecision; authorization: RollbackAuthorization | None; plan: RollbackPlan | None; audit: RollbackAudit; current_manifest: Mapping[str, Any] = field(default_factory=dict); target_manifest: Mapping[str, Any] = field(default_factory=dict); current_registry_snapshot: Mapping[str, Any] = field(default_factory=dict); target_registry_snapshot: Mapping[str, Any] = field(default_factory=dict)
    def __post_init__(self):
        for name in ("current_manifest", "target_manifest", "current_registry_snapshot", "target_registry_snapshot"):
            value = getattr(self, name)
            if not isinstance(value, Mapping): raise ValueError("INVALID_ROLLBACK_PACKAGE")
            object.__setattr__(self, name, freeze(dict(value)))
    def to_dict(self): return {x: (getattr(self, x).to_dict() if hasattr(getattr(self, x), "to_dict") else thaw(getattr(self, x))) for x in self.__dataclass_fields__}

RollbackCompletionRecord = RollbackAudit
RollbackError = ValueError
