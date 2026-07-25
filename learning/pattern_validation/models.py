"""Immutable, source-bound and policy-versioned PR177 artifacts."""
from __future__ import annotations
from dataclasses import dataclass
from math import isfinite
from typing import Any, Mapping
from learning.common.immutable import freeze, thaw
from learning.pattern_memory.models import json_safe, valid_digest, valid_timestamp, valid_uuid
from .identity import digest, validation_report_uuid, validation_snapshot_uuid, validation_uuid

VALIDATION_STATES = ("INVALID", "INSUFFICIENT_EVIDENCE", "STATISTICALLY_CONSISTENT")
SOURCE_ARTIFACT_TYPES = ("PATTERN_MEMORY_REPORT", "PATTERN_MEMORY_RECORD")


@dataclass(frozen=True)
class ValidationConfig:
    minimum_sample_count: int = 30
    minimum_support: float = 0.0
    minimum_confidence: float = 0.0
    minimum_expectancy: float = 0.0

    def __post_init__(self):
        numbers = (self.minimum_support, self.minimum_confidence, self.minimum_expectancy)
        if (not isinstance(self.minimum_sample_count, int) or isinstance(self.minimum_sample_count, bool)
                or self.minimum_sample_count < 0 or not all(isinstance(x, (int, float))
                and not isinstance(x, bool) and isfinite(x) for x in numbers)
                or self.minimum_support < 0 or self.minimum_confidence < 0):
            raise ValueError("INVALID_VALIDATION_CONFIG")

    def to_dict(self):
        return {name: getattr(self, name) for name in self.__dataclass_fields__}

    @property
    def config_digest(self):
        return digest(self.to_dict())


@dataclass(frozen=True)
class ValidationRecord:
    validation_uuid: str
    validation_digest: str
    validator_version: str
    validation_policy_version: str
    validation_config_digest: str
    source_memory_uuid: str
    source_memory_digest: str
    source_pattern_uuid: str
    source_pattern_hash: str
    source_report_uuid: str
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
    memory_version: str
    memory_state: str
    validation_state: str
    validation_reasons: tuple[str, ...]
    validation_statistics: Mapping[str, Any]
    validated_at: str
    advisory_only: bool = True

    def __post_init__(self):
        reasons, contract = tuple(self.validation_reasons), tuple(self.outcome_contract)
        uuids = (self.validation_uuid, self.source_memory_uuid, self.source_pattern_uuid,
                 self.source_report_uuid, self.policy_uuid, self.source_attribution_uuid,
                 self.evidence_envelope_uuid, self.knowledge_uuid)
        digests = (self.validation_digest, self.validation_config_digest, self.source_memory_digest,
                   self.source_pattern_hash, self.source_digest, self.replay_digest,
                   self.evidence_envelope_digest, self.mining_config_digest)
        versions = (self.validator_version, self.validation_policy_version, self.policy_version,
                    self.knowledge_version, self.engine_version, self.memory_version)
        statistics = thaw(self.validation_statistics)
        if (not all(valid_uuid(x) for x in uuids) or not all(valid_digest(x) for x in digests)
                or not all(isinstance(x, str) and x for x in versions)
                or len(contract) != 2 or not all(isinstance(x, str) and x for x in contract)
                or self.memory_state != "STORED" or self.validation_state not in VALIDATION_STATES
                or not reasons or not all(isinstance(x, str) and x for x in reasons)
                or not isinstance(statistics, dict) or not json_safe(statistics)
                or not valid_timestamp(self.validated_at) or self.advisory_only is not True):
            raise ValueError("INVALID_VALIDATION_RECORD")
        object.__setattr__(self, "outcome_contract", contract)
        object.__setattr__(self, "validation_reasons", reasons)
        object.__setattr__(self, "validation_statistics", freeze(statistics))
        if validation_uuid(self.identity_payload()) != self.validation_uuid:
            raise ValueError("VALIDATION_UUID_MISMATCH")
        if digest(self.digest_payload()) != self.validation_digest:
            raise ValueError("VALIDATION_DIGEST_MISMATCH")

    def identity_payload(self):
        return {name: thaw(getattr(self, name)) for name in self.__dataclass_fields__
                if name not in {"validation_uuid", "validation_digest"}}

    def digest_payload(self):
        return {"validation_uuid": self.validation_uuid, **self.identity_payload()}

    def to_dict(self):
        return {"validation_uuid": self.validation_uuid, "validation_digest": self.validation_digest,
                **self.identity_payload()}

    @classmethod
    def create(cls, **values):
        payload = {name: thaw(value) for name, value in values.items()}
        uuid = validation_uuid(payload)
        return cls(validation_uuid=uuid, validation_digest=digest({"validation_uuid": uuid, **payload}), **values)


@dataclass(frozen=True)
class PatternValidationSnapshot:
    snapshot_uuid: str
    snapshot_digest: str
    validator_version: str
    record_identities: tuple[tuple[str, str], ...]
    previous_snapshot_uuid: str | None
    previous_snapshot_digest: str | None
    generated_at: str
    advisory_only: bool = True

    def __post_init__(self):
        pairs = tuple(tuple(x) for x in self.record_identities); payload = self.identity_payload(pairs)
        if (not valid_uuid(self.snapshot_uuid) or not valid_digest(self.snapshot_digest)
                or not self.validator_version or pairs != tuple(sorted(pairs))
                or len({x[0] for x in pairs}) != len(pairs)
                or not all(len(x) == 2 and valid_uuid(x[0]) and valid_digest(x[1]) for x in pairs)
                or (self.previous_snapshot_uuid is None) != (self.previous_snapshot_digest is None)
                or (self.previous_snapshot_uuid is not None and not valid_uuid(self.previous_snapshot_uuid))
                or (self.previous_snapshot_digest is not None and not valid_digest(self.previous_snapshot_digest))
                or not valid_timestamp(self.generated_at) or self.advisory_only is not True
                or validation_snapshot_uuid(payload) != self.snapshot_uuid or digest(payload) != self.snapshot_digest):
            raise ValueError("INVALID_VALIDATION_SNAPSHOT")
        object.__setattr__(self, "record_identities", pairs)

    def identity_payload(self, pairs=None):
        pairs = self.record_identities if pairs is None else pairs
        return {"validator_version": self.validator_version, "record_identities": [list(x) for x in pairs],
                "previous_snapshot_uuid": self.previous_snapshot_uuid,
                "previous_snapshot_digest": self.previous_snapshot_digest,
                "generated_at": self.generated_at, "advisory_only": self.advisory_only}

    def to_dict(self):
        return {"snapshot_uuid": self.snapshot_uuid, "snapshot_digest": self.snapshot_digest,
                **self.identity_payload()}

    @classmethod
    def create(cls, validator_version, pairs, previous, generated_at):
        pairs = tuple(sorted(pairs))
        payload = {"validator_version": validator_version, "record_identities": [list(x) for x in pairs],
                   "previous_snapshot_uuid": previous.snapshot_uuid if previous else None,
                   "previous_snapshot_digest": previous.snapshot_digest if previous else None,
                   "generated_at": generated_at, "advisory_only": True}
        return cls(validation_snapshot_uuid(payload), digest(payload), validator_version, pairs,
                   payload["previous_snapshot_uuid"], payload["previous_snapshot_digest"], generated_at, True)


@dataclass(frozen=True)
class PatternValidationReport:
    report_uuid: str
    validator_version: str
    validation_policy_version: str
    validation_config_digest: str
    source_artifact_type: str
    source_pattern_memory_report_uuid: str | None
    source_pattern_memory_report_digest: str | None
    source_snapshot_uuid: str | None
    source_snapshot_digest: str | None
    source_memory_uuid: str | None
    source_memory_digest: str | None
    validation_records: tuple[ValidationRecord, ...]
    processed_record_count: int
    new_validation_count: int
    duplicate_validation_count: int
    statistically_consistent_count: int
    invalid_count: int
    insufficient_count: int
    repository_digest: str
    snapshot_uuid: str
    snapshot_digest: str
    generated_at: str
    advisory_only: bool = True

    def __post_init__(self):
        records = tuple(self.validation_records); payload = self.identity_payload(records)
        counts = (sum(x.validation_state == "STATISTICALLY_CONSISTENT" for x in records),
                  sum(x.validation_state == "INVALID" for x in records),
                  sum(x.validation_state == "INSUFFICIENT_EVIDENCE" for x in records))
        report_source = self.source_artifact_type == "PATTERN_MEMORY_REPORT"
        source_valid = ((report_source and valid_uuid(self.source_pattern_memory_report_uuid)
                         and valid_digest(self.source_pattern_memory_report_digest)
                         and valid_uuid(self.source_snapshot_uuid) and valid_digest(self.source_snapshot_digest)
                         and self.source_memory_uuid is None and self.source_memory_digest is None)
                        or (not report_source and self.source_artifact_type == "PATTERN_MEMORY_RECORD"
                            and valid_uuid(self.source_memory_uuid) and valid_digest(self.source_memory_digest)
                            and all(x is None for x in (self.source_pattern_memory_report_uuid,
                                self.source_pattern_memory_report_digest, self.source_snapshot_uuid,
                                self.source_snapshot_digest))))
        if (not valid_uuid(self.report_uuid) or not source_valid
                or not all(isinstance(x, ValidationRecord) for x in records)
                or self.processed_record_count != len(records)
                or self.new_validation_count + self.duplicate_validation_count != len(records)
                or counts != (self.statistically_consistent_count, self.invalid_count, self.insufficient_count)
                or not all(valid_digest(x) for x in (self.validation_config_digest, self.repository_digest,
                                                     self.snapshot_digest))
                or not valid_uuid(self.snapshot_uuid) or not valid_timestamp(self.generated_at)
                or self.advisory_only is not True or validation_report_uuid(payload) != self.report_uuid):
            raise ValueError("INVALID_PATTERN_VALIDATION_REPORT")
        object.__setattr__(self, "validation_records", records)

    def identity_payload(self, records=None):
        records = self.validation_records if records is None else records
        return {name: ([x.to_dict() for x in records] if name == "validation_records" else getattr(self, name))
                for name in self.__dataclass_fields__ if name != "report_uuid"}

    def to_dict(self):
        return {"report_uuid": self.report_uuid, **self.identity_payload()}

    @classmethod
    def create(cls, **values):
        payload = {**values, "validation_records": [x.to_dict() for x in values["validation_records"]]}
        return cls(report_uuid=validation_report_uuid(payload), **values)
