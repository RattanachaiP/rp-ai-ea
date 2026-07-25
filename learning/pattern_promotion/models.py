"""Immutable PR178 assessment artifacts with complete upstream provenance.

POLICY_CRITERIA_MET means only that immutable PR178 criteria were satisfied. It
never means promoted, published, registered, activated, runtime eligible,
tradable, or approved for execution.
"""
from dataclasses import dataclass
from math import isfinite
from collections.abc import Mapping
from learning.common.immutable import freeze, thaw
from learning.pattern_memory.models import json_safe, valid_digest, valid_timestamp, valid_uuid
from .identity import (digest, promotion_policy_uuid, promotion_report_uuid,
                       promotion_snapshot_uuid, promotion_uuid)

PROMOTION_STATES = ("REJECTED", "INSUFFICIENT_PROMOTION_EVIDENCE", "POLICY_CRITERIA_MET")
VALIDATION_STATES = ("INVALID", "INSUFFICIENT_EVIDENCE", "STATISTICALLY_CONSISTENT")


def _strings(values): return all(isinstance(x, str) and x for x in values)
def _mapping(value):
    raw = thaw(value)
    return isinstance(raw, dict) and all(isinstance(k, str) for k in raw) and json_safe(raw)
def _finite_tree(value):
    if isinstance(value, Mapping): return all(isinstance(k, str) and _finite_tree(v) for k, v in value.items())
    if isinstance(value, (tuple, list)): return all(_finite_tree(v) for v in value)
    return not isinstance(value, float) or isfinite(value)
def _thresholds(value):
    fields = {"minimum_sample_count", "minimum_support", "minimum_confidence", "minimum_expectancy"}
    return (set(value) == fields and isinstance(value["minimum_sample_count"], int)
            and not isinstance(value["minimum_sample_count"], bool)
            and all(isinstance(value[x], (int, float)) and not isinstance(value[x], bool)
                    and isfinite(value[x]) for x in fields - {"minimum_sample_count"}))


@dataclass(frozen=True)
class PromotionRecord:
    promotion_uuid: str
    promotion_digest: str
    promotion_engine_version: str
    promotion_policy_uuid: str
    promotion_policy_digest: str
    promotion_policy_version: str
    source_validation_uuid: str
    source_validation_digest: str
    source_validator_version: str
    source_validation_policy_version: str
    source_validation_config_digest: str
    source_memory_uuid: str
    source_memory_digest: str
    source_pattern_uuid: str
    source_pattern_hash: str
    source_report_uuid: str
    source_policy_uuid: str
    source_policy_version: str
    source_attribution_uuid: str
    source_digest: str
    replay_digest: str
    evidence_envelope_uuid: str
    evidence_envelope_digest: str
    knowledge_uuid: str
    knowledge_version: str
    source_engine_version: str
    mining_config_digest: str
    outcome_contract: tuple[str, str]
    memory_version: str
    memory_state: str
    source_validation_state: str
    source_validation_reasons: tuple[str, ...]
    source_validation_statistics: Mapping
    source_validated_at: str
    source_validation_thresholds: Mapping
    promotion_policy_thresholds: Mapping
    threshold_monotonicity_result: str
    promotion_state: str
    promotion_reasons: tuple[str, ...]
    created_at: str
    advisory_only: bool = True

    def __post_init__(self):
        for name in ("outcome_contract", "source_validation_reasons", "promotion_reasons"):
            object.__setattr__(self, name, tuple(getattr(self, name)))
        for name in ("source_validation_statistics", "source_validation_thresholds", "promotion_policy_thresholds"):
            object.__setattr__(self, name, freeze(thaw(getattr(self, name))))
        uuids = (self.promotion_uuid, self.promotion_policy_uuid, self.source_validation_uuid,
                 self.source_memory_uuid, self.source_pattern_uuid, self.source_report_uuid,
                 self.source_policy_uuid, self.source_attribution_uuid, self.evidence_envelope_uuid,
                 self.knowledge_uuid)
        digests = (self.promotion_digest, self.promotion_policy_digest, self.source_validation_digest,
                   self.source_validation_config_digest, self.source_memory_digest, self.source_pattern_hash,
                   self.source_digest, self.replay_digest, self.evidence_envelope_digest,
                   self.mining_config_digest)
        versions = (self.promotion_engine_version, self.promotion_policy_version, self.source_validator_version,
                    self.source_validation_policy_version, self.source_policy_version, self.knowledge_version,
                    self.source_engine_version, self.memory_version)
        source_thresholds = thaw(self.source_validation_thresholds)
        promotion_thresholds = thaw(self.promotion_policy_thresholds)
        policy_payload = {"promotion_policy_version": self.promotion_policy_version,
                          **promotion_thresholds,
                          "required_validation_state": "STATISTICALLY_CONSISTENT"}
        if (not all(valid_uuid(x) for x in uuids) or not all(valid_digest(x) for x in digests)
                or not _strings(versions) or len(self.outcome_contract) != 2 or not _strings(self.outcome_contract)
                or self.memory_state != "STORED" or self.source_validation_state not in VALIDATION_STATES
                or not self.source_validation_reasons or not _strings(self.source_validation_reasons)
                or not self.promotion_reasons or not _strings(self.promotion_reasons)
                or not all(_mapping(getattr(self, x)) and _finite_tree(getattr(self, x)) for x in
                           ("source_validation_statistics", "source_validation_thresholds",
                            "promotion_policy_thresholds"))
                or not _thresholds(source_thresholds) or not _thresholds(promotion_thresholds)
                or digest(source_thresholds) != self.source_validation_config_digest
                or promotion_policy_uuid(policy_payload) != self.promotion_policy_uuid
                or digest(policy_payload) != self.promotion_policy_digest
                or any(promotion_thresholds[name] < source_thresholds[name]
                       for name in source_thresholds)
                or self.threshold_monotonicity_result != "PASSED" or self.promotion_state not in PROMOTION_STATES
                or not valid_timestamp(self.source_validated_at) or not valid_timestamp(self.created_at)
                or self.advisory_only is not True or promotion_uuid(self.identity_payload()) != self.promotion_uuid
                or digest(self.digest_payload()) != self.promotion_digest):
            raise ValueError("INVALID_PROMOTION_RECORD")

    def identity_payload(self):
        return {name: thaw(getattr(self, name)) for name in self.__dataclass_fields__
                if name not in {"promotion_uuid", "promotion_digest"}}
    def digest_payload(self): return {"promotion_uuid": self.promotion_uuid, **self.identity_payload()}
    def to_dict(self): return {"promotion_uuid": self.promotion_uuid,
        "promotion_digest": self.promotion_digest, **self.identity_payload()}
    @classmethod
    def create(cls, **values):
        payload = {k: thaw(v) for k, v in values.items()}; identifier = promotion_uuid(payload)
        return cls(promotion_uuid=identifier,
                   promotion_digest=digest({"promotion_uuid": identifier, **payload}), **values)


@dataclass(frozen=True)
class PatternPromotionSnapshot:
    snapshot_uuid: str
    snapshot_digest: str
    promotion_engine_version: str
    promotion_policy_uuid: str
    promotion_policy_digest: str
    promotion_policy_version: str
    record_identities: tuple[tuple[str, str], ...]
    record_count: int
    previous_snapshot_uuid: str | None
    previous_snapshot_digest: str | None
    generated_at: str
    advisory_only: bool = True

    def __post_init__(self):
        pairs = tuple(tuple(x) for x in self.record_identities); object.__setattr__(self, "record_identities", pairs)
        payload = self.identity_payload()
        if (not valid_uuid(self.snapshot_uuid) or not valid_digest(self.snapshot_digest)
                or not valid_uuid(self.promotion_policy_uuid) or not valid_digest(self.promotion_policy_digest)
                or not _strings((self.promotion_engine_version, self.promotion_policy_version))
                or pairs != tuple(sorted(pairs)) or self.record_count != len(pairs)
                or len({x[0] for x in pairs}) != len(pairs)
                or not all(len(x) == 2 and valid_uuid(x[0]) and valid_digest(x[1]) for x in pairs)
                or (self.previous_snapshot_uuid is None) != (self.previous_snapshot_digest is None)
                or (self.previous_snapshot_uuid is not None and not valid_uuid(self.previous_snapshot_uuid))
                or (self.previous_snapshot_digest is not None and not valid_digest(self.previous_snapshot_digest))
                or not valid_timestamp(self.generated_at) or self.advisory_only is not True
                or promotion_snapshot_uuid(payload) != self.snapshot_uuid or digest(payload) != self.snapshot_digest):
            raise ValueError("INVALID_PROMOTION_SNAPSHOT")

    def identity_payload(self):
        return {name: ([list(x) for x in self.record_identities] if name == "record_identities" else getattr(self, name))
                for name in self.__dataclass_fields__ if name not in {"snapshot_uuid", "snapshot_digest"}}
    def to_dict(self): return {"snapshot_uuid": self.snapshot_uuid, "snapshot_digest": self.snapshot_digest,
                               **self.identity_payload()}
    @classmethod
    def create(cls, engine_version, policy, pairs, previous, generated_at):
        values = dict(promotion_engine_version=engine_version, promotion_policy_uuid=policy.policy_uuid,
            promotion_policy_digest=policy.policy_digest, promotion_policy_version=policy.promotion_policy_version,
            record_identities=tuple(sorted(pairs)), record_count=len(pairs),
            previous_snapshot_uuid=previous.snapshot_uuid if previous else None,
            previous_snapshot_digest=previous.snapshot_digest if previous else None,
            generated_at=generated_at, advisory_only=True)
        payload = {**values, "record_identities": [list(x) for x in values["record_identities"]]}
        return cls(snapshot_uuid=promotion_snapshot_uuid(payload), snapshot_digest=digest(payload), **values)


@dataclass(frozen=True)
class PatternPromotionReport:
    report_uuid: str
    source_artifact_type: str
    source_validation_report_uuid: str | None
    source_validation_report_digest: str | None
    source_validation_snapshot_uuid: str | None
    source_validation_snapshot_digest: str | None
    source_validation_repository_digest: str | None
    source_validation_uuid: str | None
    source_validation_digest: str | None
    source_validator_version: str
    source_validation_policy_version: str
    source_validation_config_digest: str
    promotion_engine_version: str
    promotion_policy_uuid: str
    promotion_policy_digest: str
    promotion_policy_version: str
    promotion_records: tuple[PromotionRecord, ...]
    processed_record_count: int
    new_promotion_count: int
    duplicate_promotion_count: int
    criteria_met_count: int
    rejected_count: int
    insufficient_promotion_evidence_count: int
    repository_digest: str
    snapshot_uuid: str
    snapshot_digest: str
    generated_at: str
    advisory_only: bool = True

    def __post_init__(self):
        records = tuple(self.promotion_records); object.__setattr__(self, "promotion_records", records)
        report_source = self.source_artifact_type == "PATTERN_VALIDATION_REPORT"
        source_ok = ((report_source and all(valid_uuid(x) for x in (self.source_validation_report_uuid,
            self.source_validation_snapshot_uuid)) and all(valid_digest(x) for x in
            (self.source_validation_report_digest, self.source_validation_snapshot_digest,
             self.source_validation_repository_digest)) and self.source_validation_uuid is None
            and self.source_validation_digest is None) or (self.source_artifact_type == "VALIDATION_RECORD"
            and valid_uuid(self.source_validation_uuid) and valid_digest(self.source_validation_digest)
            and all(x is None for x in (self.source_validation_report_uuid, self.source_validation_report_digest,
                self.source_validation_snapshot_uuid, self.source_validation_snapshot_digest,
                self.source_validation_repository_digest))))
        counts = (sum(x.promotion_state == "POLICY_CRITERIA_MET" for x in records),
                  sum(x.promotion_state == "REJECTED" for x in records),
                  sum(x.promotion_state == "INSUFFICIENT_PROMOTION_EVIDENCE" for x in records))
        if (not valid_uuid(self.report_uuid) or not source_ok or not _strings((self.source_validator_version,
                self.source_validation_policy_version, self.promotion_engine_version, self.promotion_policy_version))
                or not all(valid_digest(x) for x in (self.source_validation_config_digest,
                    self.promotion_policy_digest, self.repository_digest, self.snapshot_digest))
                or not all(valid_uuid(x) for x in (self.promotion_policy_uuid, self.snapshot_uuid))
                or not all(isinstance(x, PromotionRecord) for x in records)
                or self.processed_record_count != len(records)
                or self.new_promotion_count + self.duplicate_promotion_count != len(records)
                or counts != (self.criteria_met_count, self.rejected_count,
                              self.insufficient_promotion_evidence_count)
                or not valid_timestamp(self.generated_at) or self.advisory_only is not True
                or promotion_report_uuid(self.identity_payload()) != self.report_uuid):
            raise ValueError("INVALID_PROMOTION_REPORT")

    def identity_payload(self):
        return {name: ([x.to_dict() for x in self.promotion_records] if name == "promotion_records"
                       else getattr(self, name)) for name in self.__dataclass_fields__ if name != "report_uuid"}
    def to_dict(self): return {"report_uuid": self.report_uuid, **self.identity_payload()}
    @classmethod
    def create(cls, **values):
        payload = {**values, "promotion_records": [x.to_dict() for x in values["promotion_records"]]}
        return cls(report_uuid=promotion_report_uuid(payload), **values)
