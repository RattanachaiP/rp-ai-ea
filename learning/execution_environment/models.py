"""Immutable, independently validated PR187 advisory ExecutionEnvironment artifacts."""

from dataclasses import dataclass
from collections.abc import Mapping
from learning.pattern_memory.models import valid_digest, valid_timestamp, valid_uuid
from learning.execution_readiness.models import EXECUTION_READINESS_STATES
from .identity import digest, execution_environment_uuid, report_uuid, snapshot_uuid
from .policy import ExecutionEnvironmentPolicy

AUTHORITY_SCOPE = "ADVISORY_EXECUTION_ENVIRONMENT_ONLY"
EXECUTION_ENVIRONMENT_STATES = (
    "REJECTED",
    "INSUFFICIENT_ENVIRONMENT_INFORMATION",
    "ENVIRONMENT_READY_FOR_FEASIBILITY",
)
EXECUTION_ENVIRONMENT_CLASSIFICATIONS = (
    "READY_FOR_FEASIBILITY",
    "INSUFFICIENT_ENVIRONMENT_INFORMATION",
    "REJECTED",
)


def _version(v):
    return isinstance(v, str) and bool(v) and v == v.strip()


@dataclass(frozen=True)
class ExecutionEnvironment:
    execution_environment_uuid: str
    execution_environment_digest: str
    execution_readiness_uuid: str
    execution_readiness_digest: str
    readiness_state: str
    environment_state: str
    environment_classification: str
    environment_reason: str
    environment_profile: tuple[tuple[str, str], ...]
    environment_quality: float
    readiness_snapshot_uuid: str
    readiness_snapshot_digest: str
    readiness_repository_digest: str
    environment_policy_uuid: str
    environment_policy_digest: str
    environment_policy_version: str
    environment_engine_version: str
    created_at: str
    authority_scope: str = AUTHORITY_SCOPE
    advisory_only: bool = True

    def __post_init__(self):
        environment_policy = ExecutionEnvironmentPolicy()
        profile = tuple(tuple(item) for item in self.environment_profile)
        object.__setattr__(self, "environment_profile", profile)
        allowed = {
            "REJECTED": {("REJECTED", "READINESS_REJECTED")},
            "INSUFFICIENT_EXECUTION_READINESS": {("INSUFFICIENT_ENVIRONMENT_INFORMATION", "READINESS_INFORMATION_INSUFFICIENT")},
            "EXECUTION_READY_FOR_ENVIRONMENT_CHECK": {
                ("ENVIRONMENT_READY_FOR_FEASIBILITY", "ENVIRONMENT_QUALITY_VERIFIED"),
            },
        }
        expected_class = {
            "READINESS_REJECTED": "REJECTED",
            "READINESS_INFORMATION_INSUFFICIENT": "INSUFFICIENT_ENVIRONMENT_INFORMATION",
            "ENVIRONMENT_QUALITY_VERIFIED": "READY_FOR_FEASIBILITY",
        }
        if (
            not all(
                valid_uuid(x)
                for x in (
                    self.execution_environment_uuid,
                    self.execution_readiness_uuid,
                    self.readiness_snapshot_uuid,
                    self.environment_policy_uuid,
                )
            )
            or not all(
                valid_digest(x)
                for x in (
                    self.execution_environment_digest,
                    self.execution_readiness_digest,
                    self.readiness_snapshot_digest,
                    self.readiness_repository_digest,
                    self.environment_policy_digest,
                )
            )
            or self.readiness_state not in EXECUTION_READINESS_STATES
            or (self.environment_state, self.environment_reason)
            not in allowed.get(self.readiness_state, set())
            or self.environment_classification not in EXECUTION_ENVIRONMENT_CLASSIFICATIONS
            or tuple(name for name, _ in profile) != environment_policy.dimensions
            or any(value not in {"AVAILABLE", "UNAVAILABLE"} for _, value in profile)
            or type(self.environment_quality) is not float
            or not 0.0 <= self.environment_quality <= 1.0
            or self.environment_quality != sum(value == "AVAILABLE" for _, value in profile) / len(profile)
            or (self.environment_state == "ENVIRONMENT_READY_FOR_FEASIBILITY") != (self.environment_quality >= environment_policy.minimum_quality)
            or expected_class.get(self.environment_reason)
            != self.environment_classification
            or self.environment_policy_version != "PR187-EXECUTION-ENVIRONMENT-POLICY.1.0"
            or self.environment_engine_version != "PR187.1.0"
            or self.environment_policy_uuid != environment_policy.environment_policy_uuid
            or self.environment_policy_digest != environment_policy.environment_policy_digest
            or not valid_timestamp(self.created_at)
            or self.authority_scope != AUTHORITY_SCOPE
            or self.advisory_only is not True
            or execution_environment_uuid(self.identity_payload()) != self.execution_environment_uuid
            or digest(self.digest_payload()) != self.execution_environment_digest
        ):
            raise ValueError("INVALID_EXECUTION_ENVIRONMENT")

    def identity_payload(self):
        return {
            n: ([list(x) for x in self.environment_profile] if n == "environment_profile" else getattr(self, n))
            for n in self.__dataclass_fields__
            if n not in {"execution_environment_uuid", "execution_environment_digest"}
        }

    def digest_payload(self):
        return {
            "execution_environment_uuid": self.execution_environment_uuid,
            **self.identity_payload(),
        }

    def to_dict(self):
        return self.digest_payload() | {
            "execution_environment_digest": self.execution_environment_digest
        }

    @classmethod
    def create(cls, **v):
        uid = execution_environment_uuid(v)
        return cls(
            execution_environment_uuid=uid,
            execution_environment_digest=digest({"execution_environment_uuid": uid, **v}),
            **v,
        )


@dataclass(frozen=True)
class ExecutionEnvironmentSnapshot:
    snapshot_uuid: str
    snapshot_digest: str
    environment_identities: tuple[tuple[str, str], ...]
    record_count: int
    repository_digest: str
    previous_snapshot_uuid: str | None
    previous_snapshot_digest: str | None
    generated_at: str
    environment_policy_uuid: str
    environment_policy_digest: str
    environment_policy_version: str
    environment_engine_version: str
    readiness_policy_uuid: str
    readiness_policy_digest: str
    readiness_policy_version: str
    readiness_engine_version: str
    authority_scope: str = AUTHORITY_SCOPE
    advisory_only: bool = True

    def __post_init__(self):
        environment_policy = ExecutionEnvironmentPolicy()
        ids = tuple(tuple(x) for x in self.environment_identities)
        object.__setattr__(self, "environment_identities", ids)
        prev = (
            self.previous_snapshot_uuid is None
            and self.previous_snapshot_digest is None
        ) or (
            valid_uuid(self.previous_snapshot_uuid)
            and valid_digest(self.previous_snapshot_digest)
        )
        if (
            not all(
                valid_uuid(x)
                for x in (
                    self.snapshot_uuid,
                    self.environment_policy_uuid,
                    self.readiness_policy_uuid,
                )
            )
            or not all(
                valid_digest(x)
                for x in (
                    self.snapshot_digest,
                    self.repository_digest,
                    self.environment_policy_digest,
                    self.readiness_policy_digest,
                )
            )
            or ids != tuple(sorted(ids))
            or self.record_count != len(ids)
            or len({x[0] for x in ids}) != len(ids)
            or not all(valid_uuid(x[0]) and valid_digest(x[1]) for x in ids)
            or not prev
            or not all(
                _version(x)
                for x in (
                    self.environment_policy_version,
                    self.environment_engine_version,
                    self.readiness_policy_version,
                    self.readiness_engine_version,
                )
            )
            or self.environment_policy_version != "PR187-EXECUTION-ENVIRONMENT-POLICY.1.0"
            or self.environment_engine_version != "PR187.1.0"
            or self.environment_policy_uuid != environment_policy.environment_policy_uuid
            or self.environment_policy_digest != environment_policy.environment_policy_digest
            or self.readiness_policy_version != "PR186-EXECUTION_READINESS-POLICY.1.0"
            or self.readiness_engine_version != "PR186.1.0"
            or not valid_timestamp(self.generated_at)
            or self.authority_scope != AUTHORITY_SCOPE
            or self.advisory_only is not True
            or snapshot_uuid(self.identity_payload()) != self.snapshot_uuid
            or digest(self.identity_payload()) != self.snapshot_digest
        ):
            raise ValueError("INVALID_EXECUTION_ENVIRONMENT_SNAPSHOT")

    def identity_payload(self):
        return {
            n: (
                [list(x) for x in self.environment_identities]
                if n == "environment_identities"
                else getattr(self, n)
            )
            for n in self.__dataclass_fields__
            if n not in {"snapshot_uuid", "snapshot_digest"}
        }

    def to_dict(self):
        return {
            "snapshot_uuid": self.snapshot_uuid,
            "snapshot_digest": self.snapshot_digest,
            **self.identity_payload(),
        }

    @classmethod
    def create(cls, **v):
        v = dict(v)
        v["environment_identities"] = tuple(v["environment_identities"])
        p = {
            **v,
            "environment_identities": [
                list(x) for x in v["environment_identities"]
            ],
        }
        uid = snapshot_uuid(p)
        return cls(snapshot_uuid=uid, snapshot_digest=digest(p), **v)


@dataclass(frozen=True)
class ExecutionEnvironmentReport:
    report_uuid: str
    report_digest: str
    execution_environment_records: tuple[ExecutionEnvironment, ...]
    processed_count: int
    ready_count: int
    insufficient_count: int
    rejected_count: int
    duplicate_count: int
    repository_digest: str
    snapshot_uuid: str
    snapshot_digest: str
    generated_at: str
    advisory_only: bool = True

    def __post_init__(self):
        items = tuple(
            ExecutionEnvironment(**x) if isinstance(x, Mapping) else x
            for x in self.execution_environment_records
        )
        object.__setattr__(self, "execution_environment_records", items)
        if (
            not all(type(x) is ExecutionEnvironment for x in items)
            or self.processed_count != len(items)
            or self.ready_count
            != sum(x.environment_state == "ENVIRONMENT_READY_FOR_FEASIBILITY" for x in items)
            or self.insufficient_count
            != sum(
                x.environment_state == "INSUFFICIENT_ENVIRONMENT_INFORMATION"
                for x in items
            )
            or self.rejected_count
            != sum(x.environment_state == "REJECTED" for x in items)
            or len({x.execution_environment_uuid for x in items}) != len(items)
            or type(self.duplicate_count) is not int
            or not 0 <= self.duplicate_count <= len(items)
            or not valid_uuid(self.report_uuid)
            or not valid_uuid(self.snapshot_uuid)
            or not all(
                valid_digest(x)
                for x in (
                    self.report_digest,
                    self.repository_digest,
                    self.snapshot_digest,
                )
            )
            or not valid_timestamp(self.generated_at)
            or self.advisory_only is not True
            or report_uuid(self.identity_payload()) != self.report_uuid
            or digest(self.digest_payload()) != self.report_digest
        ):
            raise ValueError("INVALID_EXECUTION_ENVIRONMENT_REPORT")

    def identity_payload(self):
        return {
            n: (
                [x.to_dict() for x in self.execution_environment_records]
                if n == "execution_environment_records"
                else getattr(self, n)
            )
            for n in self.__dataclass_fields__
            if n not in {"report_uuid", "report_digest"}
        }

    def digest_payload(self):
        return {"report_uuid": self.report_uuid, **self.identity_payload()}

    def to_dict(self):
        return {
            "report_uuid": self.report_uuid,
            "report_digest": self.report_digest,
            **self.identity_payload(),
        }

    @classmethod
    def create(cls, **v):
        v = dict(v)
        v["execution_environment_records"] = tuple(v["execution_environment_records"])
        p = {**v, "execution_environment_records": [x.to_dict() for x in v["execution_environment_records"]]}
        uid = report_uuid(p)
        return cls(
            report_uuid=uid, report_digest=digest({"report_uuid": uid, **p}), **v
        )
