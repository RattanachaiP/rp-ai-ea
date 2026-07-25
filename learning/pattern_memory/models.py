"""Immutable contracts for the advisory-only PR176 memory layer."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from math import isfinite
from typing import Any, Mapping
from uuid import UUID

from learning.common.immutable import freeze, thaw

from .memory_identity import digest, report_uuid as derive_report_uuid

MEMORY_STATES = ("ACTIVE", "ARCHIVED", "SUPERSEDED", "REJECTED")


def valid_uuid(value: object) -> bool:
    try:
        return str(UUID(str(value))) == str(value)
    except (TypeError, ValueError, AttributeError):
        return False


def valid_digest(value: object) -> bool:
    return isinstance(value, str) and len(value) == 64 and all(c in "0123456789abcdef" for c in value)


def valid_timestamp(value: object) -> bool:
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00")).tzinfo is not None
    except (TypeError, ValueError, AttributeError):
        return False


def finite_number(value: object) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool) and isfinite(value)


@dataclass(frozen=True)
class PatternMemoryRecord:
    memory_uuid: str
    memory_digest: str
    pattern_uuid: str
    pattern_hash: str
    report_uuid: str
    policy_uuid: str
    source_attribution_uuid: str
    evidence_envelope_uuid: str
    knowledge_uuid: str
    knowledge_version: str
    engine_version: str
    feature_signature: str
    market_context: Mapping[str, Any]
    entry_context: Mapping[str, Any]
    exit_context: Mapping[str, Any]
    risk_context: Mapping[str, Any]
    sample_count: int
    support: float
    expectancy: float
    confidence: float
    memory_version: str
    created_at: str
    advisory_only: bool = True
    memory_state: str = "ACTIVE"

    def __post_init__(self) -> None:
        uuids = (self.memory_uuid, self.pattern_uuid, self.report_uuid, self.policy_uuid,
                 self.source_attribution_uuid, self.evidence_envelope_uuid, self.knowledge_uuid)
        contexts = (self.market_context, self.entry_context, self.exit_context, self.risk_context)
        if (not all(valid_uuid(x) for x in uuids)
                or not valid_digest(self.memory_digest) or not valid_digest(self.pattern_hash)
                or not valid_digest(self.feature_signature)
                or not all(isinstance(x, str) and x for x in (self.knowledge_version, self.engine_version, self.memory_version))
                or not isinstance(self.sample_count, int) or isinstance(self.sample_count, bool) or self.sample_count < 0
                or not all(finite_number(x) for x in (self.support, self.expectancy, self.confidence))
                or not 0 <= self.support <= 1 or not 0 <= self.confidence <= 1
                or not all(isinstance(x, Mapping) for x in contexts)
                or not valid_timestamp(self.created_at) or self.advisory_only is not True
                or self.memory_state not in MEMORY_STATES):
            raise ValueError("INVALID_PATTERN_MEMORY_RECORD")
        for name in ("market_context", "entry_context", "exit_context", "risk_context"):
            object.__setattr__(self, name, freeze(dict(getattr(self, name))))
        if digest(self.digest_payload()) != self.memory_digest:
            raise ValueError("MEMORY_DIGEST_MISMATCH")

    def digest_payload(self) -> dict[str, Any]:
        return {name: thaw(getattr(self, name)) for name in self.__dataclass_fields__
                if name not in {"memory_uuid", "memory_digest"}}

    def to_dict(self) -> dict[str, Any]:
        return {name: thaw(getattr(self, name)) for name in self.__dataclass_fields__}


@dataclass(frozen=True)
class PatternMemoryReport:
    report_uuid: str
    memory_records: tuple[PatternMemoryRecord, ...]
    memory_count: int
    duplicate_count: int
    rejected_count: int
    repository_digest: str
    generated_at: str
    advisory_only: bool = True

    def __post_init__(self) -> None:
        records = tuple(self.memory_records)
        identity = {"memory_records": [x.to_dict() for x in records], "memory_count": self.memory_count,
                    "duplicate_count": self.duplicate_count, "rejected_count": self.rejected_count,
                    "repository_digest": self.repository_digest, "generated_at": self.generated_at,
                    "advisory_only": self.advisory_only}
        if (not valid_uuid(self.report_uuid) or not all(isinstance(x, PatternMemoryRecord) for x in records)
                or self.memory_count != len(records)
                or not all(isinstance(x, int) and not isinstance(x, bool) and x >= 0
                           for x in (self.memory_count, self.duplicate_count, self.rejected_count))
                or not valid_digest(self.repository_digest) or not valid_timestamp(self.generated_at)
                or self.advisory_only is not True or derive_report_uuid(identity) != self.report_uuid):
            raise ValueError("INVALID_PATTERN_MEMORY_REPORT")
        object.__setattr__(self, "memory_records", records)

    def to_dict(self) -> dict[str, Any]:
        return {"report_uuid": self.report_uuid, "memory_records": [x.to_dict() for x in self.memory_records],
                "memory_count": self.memory_count, "duplicate_count": self.duplicate_count,
                "rejected_count": self.rejected_count, "repository_digest": self.repository_digest,
                "generated_at": self.generated_at, "advisory_only": self.advisory_only}
