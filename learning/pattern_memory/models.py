"""Immutable, independently replay-verifiable PR176 contracts."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from math import isfinite
from typing import Any, Mapping
from uuid import UUID

from learning.common.immutable import freeze, thaw
from .memory_identity import digest, memory_uuid, report_uuid

MEMORY_STATES = ("STORED",)


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


def json_safe(value: Any) -> bool:
    if value is None or isinstance(value, (str, bool)):
        return True
    if isinstance(value, (int, float)):
        return not isinstance(value, bool) and isfinite(value)
    if isinstance(value, (tuple, list)):
        return all(json_safe(item) for item in value)
    if isinstance(value, Mapping):
        return all(isinstance(key, str) and json_safe(item) for key, item in value.items())
    return False


@dataclass(frozen=True)
class PatternMemoryRecord:
    """One stored historical pattern; STORED never means runtime-active.

    ``memory_identity_digest`` protects governance identity and derives the UUID.
    ``memory_digest`` protects the complete record except its UUID and itself.
    """
    memory_uuid: str
    memory_identity_digest: str
    memory_digest: str
    pattern_uuid: str
    pattern_hash: str
    report_uuid: str
    policy_uuid: str
    policy_version: str
    source_attribution_uuid: str
    source_digest: str
    replay_digest: str
    evidence_envelope_uuid: str
    evidence_envelope_digest: str
    knowledge_uuid: str
    knowledge_version: str
    engine_version: str
    mining_config_digest: str
    outcome_contract: tuple[str, str]
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
    memory_state: str = "STORED"

    def __post_init__(self) -> None:
        uuids = (self.memory_uuid, self.pattern_uuid, self.report_uuid, self.policy_uuid,
                 self.source_attribution_uuid, self.evidence_envelope_uuid, self.knowledge_uuid)
        digests = (self.memory_identity_digest, self.memory_digest, self.pattern_hash, self.source_digest,
                   self.replay_digest, self.evidence_envelope_digest, self.mining_config_digest,
                   self.feature_signature)
        contexts = (self.market_context, self.entry_context, self.exit_context, self.risk_context)
        contract = tuple(self.outcome_contract)
        if not all(valid_uuid(item) for item in uuids) or not all(valid_digest(item) for item in digests):
            raise ValueError("INVALID_PATTERN_MEMORY_RECORD")
        if (not all(isinstance(item, str) and item for item in
                    (self.policy_version, self.knowledge_version, self.engine_version, self.memory_version))
                or len(contract) != 2 or not all(isinstance(item, str) and item for item in contract)
                or not isinstance(self.sample_count, int) or isinstance(self.sample_count, bool) or self.sample_count < 0
                or not all(finite_number(item) for item in (self.support, self.expectancy, self.confidence))
                or not 0 <= self.support <= 1 or not 0 <= self.confidence <= 1
                or not valid_timestamp(self.created_at) or self.advisory_only is not True
                or self.memory_state not in MEMORY_STATES):
            raise ValueError("INVALID_PATTERN_MEMORY_RECORD")
        if not all(isinstance(item, Mapping) and json_safe(item) for item in contexts):
            raise ValueError("INVALID_PATTERN_MEMORY_CONTEXT")
        object.__setattr__(self, "outcome_contract", contract)
        for name in ("market_context", "entry_context", "exit_context", "risk_context"):
            object.__setattr__(self, name, freeze(dict(getattr(self, name))))
        identity = self.memory_identity_payload()
        if digest(identity) != self.memory_identity_digest:
            raise ValueError("MEMORY_IDENTITY_DIGEST_MISMATCH")
        if memory_uuid(identity) != self.memory_uuid:
            raise ValueError("MEMORY_UUID_MISMATCH")
        if digest(self.digest_payload()) != self.memory_digest:
            raise ValueError("MEMORY_DIGEST_MISMATCH")

    def memory_identity_payload(self) -> dict[str, Any]:
        return {"memory_version": self.memory_version, "report_uuid": self.report_uuid,
                "pattern_uuid": self.pattern_uuid, "pattern_hash": self.pattern_hash,
                "policy_uuid": self.policy_uuid, "policy_version": self.policy_version,
                "source_attribution_uuid": self.source_attribution_uuid, "source_digest": self.source_digest,
                "replay_digest": self.replay_digest, "evidence_envelope_uuid": self.evidence_envelope_uuid,
                "evidence_envelope_digest": self.evidence_envelope_digest, "knowledge_uuid": self.knowledge_uuid,
                "knowledge_version": self.knowledge_version, "engine_version": self.engine_version,
                "mining_config_digest": self.mining_config_digest,
                "outcome_contract": list(self.outcome_contract)}

    def digest_payload(self) -> dict[str, Any]:
        return {name: thaw(getattr(self, name)) for name in self.__dataclass_fields__
                if name not in {"memory_uuid", "memory_digest"}}

    def to_dict(self) -> dict[str, Any]:
        result = {name: thaw(getattr(self, name)) for name in self.__dataclass_fields__}
        result["outcome_contract"] = list(self.outcome_contract)
        return result

    @classmethod
    def create(cls, **values: Any) -> "PatternMemoryRecord":
        values = dict(values)
        values["outcome_contract"] = tuple(values["outcome_contract"])
        for name in ("market_context", "entry_context", "exit_context", "risk_context"):
            values[name] = thaw(values[name])
        # Validate source values without allowing independently supplied identities.
        identity_fields = ("memory_uuid", "memory_identity_digest", "memory_digest")
        if any(name in values for name in identity_fields):
            raise ValueError("PRECOMPUTED_MEMORY_IDENTITY_FORBIDDEN")
        identity_names = ("memory_version", "report_uuid", "pattern_uuid", "pattern_hash", "policy_uuid",
                          "policy_version", "source_attribution_uuid", "source_digest", "replay_digest",
                          "evidence_envelope_uuid", "evidence_envelope_digest", "knowledge_uuid",
                          "knowledge_version", "engine_version", "mining_config_digest", "outcome_contract")
        identity = {name: list(values[name]) if name == "outcome_contract" else values[name] for name in identity_names}
        identity_digest = digest(identity)
        uuid = memory_uuid(identity)
        digest_payload = {"memory_identity_digest": identity_digest, **values}
        return cls(memory_uuid=uuid, memory_identity_digest=identity_digest,
                   memory_digest=digest(digest_payload), **values)


@dataclass(frozen=True)
class PatternMemorySnapshot:
    snapshot_uuid: str
    snapshot_digest: str
    memory_version: str
    record_count: int
    record_identities: tuple[tuple[str, str], ...]
    previous_snapshot_uuid: str | None
    previous_snapshot_digest: str | None
    generated_at: str
    advisory_only: bool = True

    def __post_init__(self) -> None:
        pairs = tuple(tuple(item) for item in self.record_identities)
        payload = self.payload()
        if (not valid_uuid(self.snapshot_uuid) or not valid_digest(self.snapshot_digest)
                or not self.memory_version or self.record_count != len(pairs)
                or pairs != tuple(sorted(pairs)) or len({item[0] for item in pairs}) != len(pairs)
                or not all(len(item) == 2 and valid_uuid(item[0]) and valid_digest(item[1]) for item in pairs)
                or (self.previous_snapshot_uuid is None) != (self.previous_snapshot_digest is None)
                or (self.previous_snapshot_uuid is not None and not valid_uuid(self.previous_snapshot_uuid))
                or (self.previous_snapshot_digest is not None and not valid_digest(self.previous_snapshot_digest))
                or not valid_timestamp(self.generated_at) or self.advisory_only is not True):
            raise ValueError("INVALID_PATTERN_MEMORY_SNAPSHOT")
        if digest(payload) != self.snapshot_digest or memory_uuid(payload) != self.snapshot_uuid:
            raise ValueError("PATTERN_MEMORY_SNAPSHOT_IDENTITY_MISMATCH")
        object.__setattr__(self, "record_identities", pairs)

    def payload(self) -> dict[str, Any]:
        return {"memory_version": self.memory_version, "record_count": self.record_count,
                "record_identities": [list(item) for item in self.record_identities],
                "previous_snapshot_uuid": self.previous_snapshot_uuid,
                "previous_snapshot_digest": self.previous_snapshot_digest,
                "generated_at": self.generated_at, "advisory_only": self.advisory_only}

    def to_dict(self) -> dict[str, Any]:
        return {"snapshot_uuid": self.snapshot_uuid, "snapshot_digest": self.snapshot_digest, **self.payload()}

    @classmethod
    def create(cls, *, memory_version: str, record_identities: tuple[tuple[str, str], ...],
               previous: "PatternMemorySnapshot | None", generated_at: str) -> "PatternMemorySnapshot":
        pairs = tuple(sorted(tuple(item) for item in record_identities))
        payload = {"memory_version": memory_version, "record_count": len(pairs),
                   "record_identities": [list(item) for item in pairs],
                   "previous_snapshot_uuid": previous.snapshot_uuid if previous else None,
                   "previous_snapshot_digest": previous.snapshot_digest if previous else None,
                   "generated_at": generated_at, "advisory_only": True}
        return cls(memory_uuid(payload), digest(payload), memory_version, len(pairs), pairs,
                   payload["previous_snapshot_uuid"], payload["previous_snapshot_digest"], generated_at, True)


@dataclass(frozen=True)
class PatternMemoryReport:
    report_uuid: str
    source_pattern_mining_report_uuid: str
    source_pattern_mining_report_digest: str
    memory_version: str
    memory_records: tuple[PatternMemoryRecord, ...]
    memory_count: int
    duplicate_count: int
    rejected_count: int
    repository_digest: str
    repository_record_count: int
    repository_record_identities: tuple[tuple[str, str], ...]
    snapshot_uuid: str
    snapshot_digest: str
    generated_at: str
    advisory_only: bool = True

    def __post_init__(self) -> None:
        records = tuple(self.memory_records)
        pairs = tuple(tuple(item) for item in self.repository_record_identities)
        identity = self.identity_payload(records, pairs)
        if (not valid_uuid(self.report_uuid) or not valid_uuid(self.source_pattern_mining_report_uuid)
                or not valid_digest(self.source_pattern_mining_report_digest) or not self.memory_version
                or not all(isinstance(item, PatternMemoryRecord) for item in records)
                or self.memory_count != len(records)
                or not all(isinstance(item, int) and not isinstance(item, bool) and item >= 0
                           for item in (self.memory_count, self.duplicate_count, self.rejected_count,
                                        self.repository_record_count))
                or self.repository_record_count != len(pairs) or pairs != tuple(sorted(pairs))
                or not all(len(item) == 2 and valid_uuid(item[0]) and valid_digest(item[1]) for item in pairs)
                or digest([list(item) for item in pairs]) != self.repository_digest
                or not valid_uuid(self.snapshot_uuid) or not valid_digest(self.snapshot_digest)
                or not valid_timestamp(self.generated_at) or self.advisory_only is not True
                or report_uuid(identity) != self.report_uuid):
            raise ValueError("INVALID_PATTERN_MEMORY_REPORT")
        object.__setattr__(self, "memory_records", records)
        object.__setattr__(self, "repository_record_identities", pairs)

    def identity_payload(self, records=None, pairs=None) -> dict[str, Any]:
        records = self.memory_records if records is None else records
        pairs = self.repository_record_identities if pairs is None else pairs
        return {"memory_version": self.memory_version,
                "source_pattern_mining_report_uuid": self.source_pattern_mining_report_uuid,
                "source_pattern_mining_report_digest": self.source_pattern_mining_report_digest,
                "memory_records": [item.to_dict() for item in records], "memory_count": self.memory_count,
                "duplicate_count": self.duplicate_count, "rejected_count": self.rejected_count,
                "repository_digest": self.repository_digest,
                "repository_record_count": self.repository_record_count,
                "repository_record_identities": [list(item) for item in pairs],
                "snapshot_uuid": self.snapshot_uuid, "snapshot_digest": self.snapshot_digest,
                "generated_at": self.generated_at, "advisory_only": self.advisory_only}

    def to_dict(self) -> dict[str, Any]:
        return {"report_uuid": self.report_uuid, **self.identity_payload()}
