"""Immutable contracts for promotion execution; this module evaluates no knowledge."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Mapping
from uuid import UUID

from learning.common.immutable import freeze, thaw

JOURNAL_STATES = frozenset({"PREPARED", "COMMITTED", "FAILED", "IN_DOUBT"})
TRANSACTION_STATES = frozenset({"NEW", "VALIDATING", "LOCKED", "PREPARED", "EXECUTING", "COMMITTING", "COMPLETED", "FAILED", "IN_DOUBT"})


def _uuid(value: str) -> bool:
    try:
        UUID(value)
        return True
    except (ValueError, TypeError, AttributeError):
        return False


def _timestamp(value: str) -> bool:
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except (ValueError, AttributeError):
        return False
    return parsed.tzinfo is not None


@dataclass(frozen=True)
class PromotionAuthorityConfig:
    version: str = "1.1"
    maximum_decision_age_seconds: int = 3600
    allowed_policy_versions: tuple[str, ...] = ("1.0",)
    trusted_decision_signatures: Mapping[str, str] = field(default_factory=dict)
    approved_configuration_digests: tuple[str, ...] = ()
    operator: str = "system"
    lifecycle_version: str = "1.0"
    governance_version: str = "1.0"
    expected_schema_version: str = "1.0"
    lock_lease_seconds: int = 120

    def __post_init__(self) -> None:
        signatures = dict(self.trusted_decision_signatures)
        digests = (*signatures.values(), *self.approved_configuration_digests)
        if (not self.version or not isinstance(self.maximum_decision_age_seconds, int)
                or isinstance(self.maximum_decision_age_seconds, bool) or self.maximum_decision_age_seconds < 0
                or not isinstance(self.lock_lease_seconds, int) or self.lock_lease_seconds <= 0
                or not self.operator or not self.lifecycle_version or not self.governance_version
                or not self.expected_schema_version or not self.allowed_policy_versions
                or any(not isinstance(v, str) or not v for v in self.allowed_policy_versions)
                or any(not _uuid(k) for k in signatures)
                or any(not isinstance(v, str) or len(v) != 64 for v in digests)):
            raise ValueError("INVALID_PROMOTION_AUTHORITY_CONFIG")
        object.__setattr__(self, "trusted_decision_signatures", freeze(signatures))


@dataclass(frozen=True)
class PromotionRecord:
    record_uuid: str
    decision_uuid: str
    knowledge_uuid: str
    semantic_identity: str
    lifecycle_transition: Mapping[str, Any]
    timestamp: str
    status: str
    operator: str
    authority_version: str
    transaction_uuid: str
    previous_record_uuid: str = ""
    error: str = ""

    def __post_init__(self) -> None:
        transition = dict(self.lifecycle_transition)
        required = {"knowledge_uuid", "expected_current_state", "new_state", "idempotency_key", "transition_uuid"}
        if (not all(_uuid(getattr(self, key)) for key in ("record_uuid", "decision_uuid", "knowledge_uuid", "transaction_uuid"))
                or not isinstance(self.semantic_identity, str) or not self.semantic_identity
                or not _timestamp(self.timestamp) or self.status not in JOURNAL_STATES
                or not all(isinstance(getattr(self, key), str) and getattr(self, key) for key in ("operator", "authority_version"))
                or not required.issubset(transition)
                or transition["knowledge_uuid"] != self.knowledge_uuid
                or transition["expected_current_state"] != "VERIFIED"
                or transition["new_state"] != "ACTIVE"
                or transition["idempotency_key"] != self.decision_uuid):
            raise ValueError("INVALID_PROMOTION_RECORD")
        if self.previous_record_uuid and not _uuid(self.previous_record_uuid):
            raise ValueError("INVALID_PROMOTION_RECORD")
        object.__setattr__(self, "lifecycle_transition", freeze(transition))

    def to_dict(self) -> dict[str, Any]:
        return {name: thaw(getattr(self, name)) for name in self.__dataclass_fields__}


@dataclass
class PromotionTransaction:
    transaction_uuid: str
    decision_uuid: str
    knowledge_uuid: str
    semantic_identity: str
    state: str = "NEW"
    error: str = ""
    record: PromotionRecord | None = None

    def set_state(self, state: str) -> None:
        if state not in TRANSACTION_STATES:
            raise ValueError("INVALID_TRANSACTION_STATE")
        self.state = state
