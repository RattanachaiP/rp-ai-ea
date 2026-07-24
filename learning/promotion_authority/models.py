"""Immutable contracts for promotion execution; this module evaluates no knowledge."""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Any, Mapping
from learning.common.immutable import freeze, thaw

TRANSACTION_STATES = frozenset({"NEW", "VALIDATING", "LOCKED", "EXECUTING", "COMMITTING", "COMPLETED", "ROLLED_BACK", "FAILED"})

@dataclass(frozen=True)
class PromotionAuthorityConfig:
    version: str = "1.0"
    maximum_decision_age_seconds: int = 3600
    allowed_policy_versions: tuple[str, ...] = ("1.0",)
    operator: str = "system"
    lifecycle_version: str = "1.0"
    governance_version: str = "1.0"
    expected_schema_version: str = "1.0"
    def __post_init__(self):
        if (not self.version or not isinstance(self.maximum_decision_age_seconds, int)
                or isinstance(self.maximum_decision_age_seconds, bool) or self.maximum_decision_age_seconds < 0
                or not self.operator or not self.lifecycle_version or not self.governance_version
                or not self.expected_schema_version or not self.allowed_policy_versions
                or any(not isinstance(v, str) or not v for v in self.allowed_policy_versions)):
            raise ValueError("INVALID_PROMOTION_AUTHORITY_CONFIG")

@dataclass(frozen=True)
class PromotionRecord:
    record_uuid: str
    decision_uuid: str
    knowledge_uuid: str
    lifecycle_transition: Mapping[str, Any]
    timestamp: str
    operator: str
    authority_version: str
    transaction_uuid: str
    def __post_init__(self):
        if not all(isinstance(getattr(self, key), str) and getattr(self, key) for key in (
            "record_uuid", "decision_uuid", "knowledge_uuid", "timestamp", "operator", "authority_version", "transaction_uuid")) or not isinstance(self.lifecycle_transition, Mapping):
            raise ValueError("INVALID_PROMOTION_RECORD")
        object.__setattr__(self, "lifecycle_transition", freeze(dict(self.lifecycle_transition)))
    def to_dict(self):
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
    def set_state(self, state: str):
        if state not in TRANSACTION_STATES: raise ValueError("INVALID_TRANSACTION_STATE")
        self.state = state
