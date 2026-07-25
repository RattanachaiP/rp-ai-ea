"""Immutable PR177 validation artifacts."""
from __future__ import annotations
from dataclasses import dataclass
from typing import Any, Mapping
from learning.common.immutable import freeze, thaw
from learning.pattern_memory.memory_identity import digest, memory_uuid
from learning.pattern_memory.models import valid_digest, valid_timestamp, valid_uuid

VALIDATION_STATES = ("INVALID", "INSUFFICIENT_EVIDENCE", "VALIDATED")


@dataclass(frozen=True)
class ValidationRecord:
    validation_uuid: str
    validation_digest: str
    memory_uuid: str
    memory_digest: str
    pattern_uuid: str
    policy_uuid: str
    knowledge_uuid: str
    validation_state: str
    validation_reasons: tuple[str, ...]
    validation_statistics: Mapping[str, Any]
    validated_at: str
    advisory_only: bool = True

    def __post_init__(self):
        reasons = tuple(self.validation_reasons)
        if (not all(valid_uuid(x) for x in (self.validation_uuid, self.memory_uuid, self.pattern_uuid,
                                            self.policy_uuid, self.knowledge_uuid))
                or not all(valid_digest(x) for x in (self.validation_digest, self.memory_digest))
                or self.validation_state not in VALIDATION_STATES or not reasons
                or not all(isinstance(x, str) and x for x in reasons)
                or not valid_timestamp(self.validated_at) or self.advisory_only is not True):
            raise ValueError("INVALID_VALIDATION_RECORD")
        object.__setattr__(self, "validation_reasons", reasons)
        object.__setattr__(self, "validation_statistics", freeze(dict(self.validation_statistics)))
        payload = self.identity_payload()
        if memory_uuid(payload) != self.validation_uuid or digest(self.digest_payload()) != self.validation_digest:
            raise ValueError("VALIDATION_IDENTITY_MISMATCH")

    def identity_payload(self):
        return {"memory_uuid": self.memory_uuid, "memory_digest": self.memory_digest,
                "pattern_uuid": self.pattern_uuid, "policy_uuid": self.policy_uuid,
                "knowledge_uuid": self.knowledge_uuid, "validation_state": self.validation_state,
                "validation_reasons": list(self.validation_reasons),
                "validation_statistics": thaw(self.validation_statistics), "validated_at": self.validated_at,
                "advisory_only": self.advisory_only}

    def digest_payload(self):
        return {"validation_uuid": self.validation_uuid, **self.identity_payload()}

    def to_dict(self):
        return {"validation_uuid": self.validation_uuid, "validation_digest": self.validation_digest,
                **self.identity_payload()}

    @classmethod
    def create(cls, **values):
        payload = {**values, "validation_reasons": list(values["validation_reasons"]),
                   "validation_statistics": thaw(values["validation_statistics"])}
        uuid = memory_uuid(payload)
        return cls(validation_uuid=uuid, validation_digest=digest({"validation_uuid": uuid, **payload}), **values)


@dataclass(frozen=True)
class PatternValidationReport:
    report_uuid: str
    validation_records: tuple[ValidationRecord, ...]
    validated_count: int
    invalid_count: int
    insufficient_count: int
    repository_digest: str
    generated_at: str
    advisory_only: bool = True

    def __post_init__(self):
        records = tuple(self.validation_records); payload = self.identity_payload(records)
        counts = (sum(x.validation_state == "VALIDATED" for x in records),
                  sum(x.validation_state == "INVALID" for x in records),
                  sum(x.validation_state == "INSUFFICIENT_EVIDENCE" for x in records))
        if (not valid_uuid(self.report_uuid) or not all(isinstance(x, ValidationRecord) for x in records)
                or counts != (self.validated_count, self.invalid_count, self.insufficient_count)
                or not valid_digest(self.repository_digest) or not valid_timestamp(self.generated_at)
                or self.advisory_only is not True or memory_uuid(payload) != self.report_uuid):
            raise ValueError("INVALID_PATTERN_VALIDATION_REPORT")
        object.__setattr__(self, "validation_records", records)

    def identity_payload(self, records=None):
        records = self.validation_records if records is None else records
        return {"validation_records": [x.to_dict() for x in records], "validated_count": self.validated_count,
                "invalid_count": self.invalid_count, "insufficient_count": self.insufficient_count,
                "repository_digest": self.repository_digest, "generated_at": self.generated_at,
                "advisory_only": self.advisory_only}

    def to_dict(self): return {"report_uuid": self.report_uuid, **self.identity_payload()}

    @classmethod
    def create(cls, records, repository_digest, generated_at):
        records = tuple(records)
        values = {"validation_records": records,
                  "validated_count": sum(x.validation_state == "VALIDATED" for x in records),
                  "invalid_count": sum(x.validation_state == "INVALID" for x in records),
                  "insufficient_count": sum(x.validation_state == "INSUFFICIENT_EVIDENCE" for x in records),
                  "repository_digest": repository_digest, "generated_at": generated_at, "advisory_only": True}
        payload = {**values, "validation_records": [x.to_dict() for x in records]}
        return cls(memory_uuid(payload), **values)
