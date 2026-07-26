"""Immutable advisory-only PR188 records, reports, and snapshots."""

from collections.abc import Mapping
from dataclasses import dataclass
from learning.pattern_memory.models import valid_digest, valid_timestamp, valid_uuid
from .identity import digest, execution_feasibility_uuid, report_uuid, snapshot_uuid
from .policy import FEASIBILITY_DIMENSIONS

AUTHORITY_SCOPE = "ADVISORY_EXECUTION_FEASIBILITY_ONLY"
EXECUTION_FEASIBILITY_STATES = (
    "REJECTED", "INSUFFICIENT_EXECUTION_FEASIBILITY", "EXECUTION_FEASIBLE"
)


def _partition(uuid, dgst, version, engine):
    return (valid_uuid(uuid) and valid_digest(dgst) and
            all(isinstance(x, str) and x.strip() for x in (version, engine)))


@dataclass(frozen=True)
class ExecutionFeasibilityRecord:
    execution_feasibility_uuid: str
    execution_feasibility_digest: str
    execution_readiness_uuid: str
    execution_readiness_digest: str
    execution_environment_uuid: str
    execution_environment_digest: str
    feasibility_state: str
    feasibility_reason: str
    feasibility_dimensions: tuple[tuple[str, str], ...]
    readiness_snapshot_uuid: str
    readiness_snapshot_digest: str
    readiness_repository_digest: str
    environment_snapshot_uuid: str
    environment_snapshot_digest: str
    environment_repository_digest: str
    readiness_policy_uuid: str
    readiness_policy_digest: str
    readiness_policy_version: str
    readiness_engine_version: str
    environment_policy_uuid: str
    environment_policy_digest: str
    environment_policy_version: str
    environment_engine_version: str
    feasibility_policy_uuid: str
    feasibility_policy_digest: str
    feasibility_policy_version: str
    feasibility_engine_version: str
    created_at: str
    authority_scope: str = AUTHORITY_SCOPE
    advisory_only: bool = True

    def __post_init__(self):
        dimensions = tuple(tuple(x) for x in self.feasibility_dimensions)
        object.__setattr__(self, "feasibility_dimensions", dimensions)
        names = tuple(x[0] for x in dimensions if len(x) == 2)
        expected_state = (
            "REJECTED" if any(v == "REJECTED" for _, v in dimensions)
            else "EXECUTION_FEASIBLE" if all(v == "SATISFIED" for _, v in dimensions)
            else "INSUFFICIENT_EXECUTION_FEASIBILITY"
        )
        expected_reason = {
            "REJECTED": "UPSTREAM_REJECTED",
            "EXECUTION_FEASIBLE": "ALL_ADVISORY_PREREQUISITES_SATISFIED",
            "INSUFFICIENT_EXECUTION_FEASIBILITY": "ADVISORY_PREREQUISITES_INSUFFICIENT",
        }[expected_state]
        partitions = (
            (self.readiness_policy_uuid, self.readiness_policy_digest, self.readiness_policy_version, self.readiness_engine_version),
            (self.environment_policy_uuid, self.environment_policy_digest, self.environment_policy_version, self.environment_engine_version),
            (self.feasibility_policy_uuid, self.feasibility_policy_digest, self.feasibility_policy_version, self.feasibility_engine_version),
        )
        if (not all(valid_uuid(x) for x in (self.execution_feasibility_uuid, self.execution_readiness_uuid, self.execution_environment_uuid,
                                            self.readiness_snapshot_uuid, self.environment_snapshot_uuid))
            or not all(valid_digest(x) for x in (self.execution_feasibility_digest, self.execution_readiness_digest,
                                                  self.execution_environment_digest, self.readiness_snapshot_digest,
                                                  self.readiness_repository_digest, self.environment_snapshot_digest,
                                                  self.environment_repository_digest))
            or names != FEASIBILITY_DIMENSIONS or any(v not in {"SATISFIED", "INSUFFICIENT", "REJECTED"} for _, v in dimensions)
            or self.feasibility_state != expected_state or self.feasibility_reason != expected_reason
            or not all(_partition(*x) for x in partitions) or not valid_timestamp(self.created_at)
            or self.authority_scope != AUTHORITY_SCOPE or self.advisory_only is not True
            or execution_feasibility_uuid(self.identity_payload()) != self.execution_feasibility_uuid
            or digest(self.digest_payload()) != self.execution_feasibility_digest):
            raise ValueError("INVALID_EXECUTION_FEASIBILITY")

    def identity_payload(self):
        return {name: ([list(x) for x in self.feasibility_dimensions] if name == "feasibility_dimensions" else getattr(self, name))
                for name in self.__dataclass_fields__ if name not in {"execution_feasibility_uuid", "execution_feasibility_digest"}}

    def digest_payload(self):
        return {"execution_feasibility_uuid": self.execution_feasibility_uuid, **self.identity_payload()}

    def to_dict(self):
        return {**self.digest_payload(), "execution_feasibility_digest": self.execution_feasibility_digest}

    @classmethod
    def create(cls, **values):
        values["feasibility_dimensions"] = tuple(values["feasibility_dimensions"])
        payload = {**values, "feasibility_dimensions": [list(x) for x in values["feasibility_dimensions"]]}
        uid = execution_feasibility_uuid(payload)
        return cls(execution_feasibility_uuid=uid,
                   execution_feasibility_digest=digest({"execution_feasibility_uuid": uid, **payload}), **values)


ExecutionFeasibility = ExecutionFeasibilityRecord


@dataclass(frozen=True)
class ExecutionFeasibilitySnapshot:
    snapshot_uuid: str
    snapshot_digest: str
    feasibility_identities: tuple[tuple[str, str], ...]
    record_count: int
    repository_digest: str
    previous_snapshot_uuid: str | None
    previous_snapshot_digest: str | None
    generated_at: str
    feasibility_policy_uuid: str
    feasibility_policy_digest: str
    feasibility_policy_version: str
    feasibility_engine_version: str
    advisory_only: bool = True

    def __post_init__(self):
        ids = tuple(tuple(x) for x in self.feasibility_identities)
        object.__setattr__(self, "feasibility_identities", ids)
        previous = ((self.previous_snapshot_uuid is None and self.previous_snapshot_digest is None) or
                    (valid_uuid(self.previous_snapshot_uuid) and valid_digest(self.previous_snapshot_digest)))
        if (not valid_uuid(self.snapshot_uuid) or not valid_digest(self.snapshot_digest) or not valid_digest(self.repository_digest)
            or ids != tuple(sorted(ids)) or self.record_count != len(ids) or len({x[0] for x in ids}) != len(ids)
            or any(not valid_uuid(u) or not valid_digest(d) for u, d in ids) or not previous
            or not _partition(self.feasibility_policy_uuid, self.feasibility_policy_digest,
                              self.feasibility_policy_version, self.feasibility_engine_version)
            or not valid_timestamp(self.generated_at) or self.advisory_only is not True
            or snapshot_uuid(self.identity_payload()) != self.snapshot_uuid or digest(self.identity_payload()) != self.snapshot_digest):
            raise ValueError("INVALID_EXECUTION_FEASIBILITY_SNAPSHOT")

    def identity_payload(self):
        return {name: ([list(x) for x in self.feasibility_identities] if name == "feasibility_identities" else getattr(self, name))
                for name in self.__dataclass_fields__ if name not in {"snapshot_uuid", "snapshot_digest"}}

    def to_dict(self):
        return {"snapshot_uuid": self.snapshot_uuid, "snapshot_digest": self.snapshot_digest, **self.identity_payload()}

    @classmethod
    def create(cls, **values):
        values["feasibility_identities"] = tuple(values["feasibility_identities"])
        payload = {**values, "feasibility_identities": [list(x) for x in values["feasibility_identities"]]}
        return cls(snapshot_uuid=snapshot_uuid(payload), snapshot_digest=digest(payload), **values)


@dataclass(frozen=True)
class ExecutionFeasibilityReport:
    report_uuid: str
    report_digest: str
    execution_feasibility_records: tuple[ExecutionFeasibilityRecord, ...]
    processed_count: int
    feasible_count: int
    insufficient_count: int
    rejected_count: int
    duplicate_count: int
    repository_digest: str
    snapshot_uuid: str
    snapshot_digest: str
    generated_at: str
    advisory_only: bool = True

    def __post_init__(self):
        records = tuple(ExecutionFeasibilityRecord(**x) if isinstance(x, Mapping) else x for x in self.execution_feasibility_records)
        object.__setattr__(self, "execution_feasibility_records", records)
        if (any(type(x) is not ExecutionFeasibilityRecord for x in records) or self.processed_count != len(records)
            or self.feasible_count != sum(x.feasibility_state == "EXECUTION_FEASIBLE" for x in records)
            or self.insufficient_count != sum(x.feasibility_state == "INSUFFICIENT_EXECUTION_FEASIBILITY" for x in records)
            or self.rejected_count != sum(x.feasibility_state == "REJECTED" for x in records)
            or len({x.execution_feasibility_uuid for x in records}) != len(records)
            or type(self.duplicate_count) is not int or not 0 <= self.duplicate_count <= len(records)
            or not valid_uuid(self.report_uuid) or not valid_digest(self.report_digest) or not valid_digest(self.repository_digest)
            or not valid_uuid(self.snapshot_uuid) or not valid_digest(self.snapshot_digest) or not valid_timestamp(self.generated_at)
            or self.advisory_only is not True or report_uuid(self.identity_payload()) != self.report_uuid
            or digest(self.digest_payload()) != self.report_digest):
            raise ValueError("INVALID_EXECUTION_FEASIBILITY_REPORT")

    def identity_payload(self):
        return {name: ([x.to_dict() for x in self.execution_feasibility_records] if name == "execution_feasibility_records" else getattr(self, name))
                for name in self.__dataclass_fields__ if name not in {"report_uuid", "report_digest"}}

    def digest_payload(self):
        return {"report_uuid": self.report_uuid, **self.identity_payload()}

    def to_dict(self):
        return {"report_uuid": self.report_uuid, "report_digest": self.report_digest, **self.identity_payload()}

    @classmethod
    def create(cls, **values):
        values["execution_feasibility_records"] = tuple(values["execution_feasibility_records"])
        payload = {**values, "execution_feasibility_records": [x.to_dict() for x in values["execution_feasibility_records"]]}
        uid = report_uuid(payload)
        return cls(report_uuid=uid, report_digest=digest({"report_uuid": uid, **payload}), **values)
