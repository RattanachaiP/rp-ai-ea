"""Immutable, independently validated PR186 advisory ExecutionReadiness artifacts."""

from dataclasses import dataclass
from collections.abc import Mapping
from learning.pattern_memory.models import valid_digest, valid_timestamp, valid_uuid
from learning.decision_recommendation.models import RECOMMENDATION_STATES
from .identity import digest, execution_readiness_uuid, report_uuid, snapshot_uuid
from .policy import ExecutionReadinessPolicy

AUTHORITY_SCOPE = "ADVISORY_EXECUTION_READINESS_ONLY"
EXECUTION_READINESS_STATES = (
    "REJECTED",
    "INSUFFICIENT_EXECUTION_READINESS",
    "EXECUTION_READY_FOR_ENVIRONMENT_CHECK",
)
EXECUTION_READINESS_CLASSIFICATIONS = (
    "READY_FOR_ENVIRONMENT_CHECK",
    "INSUFFICIENT_EXECUTION_READINESS",
    "REJECTED",
)


def _version(v):
    return isinstance(v, str) and bool(v) and v == v.strip()


@dataclass(frozen=True)
class ExecutionReadiness:
    execution_readiness_uuid: str
    execution_readiness_digest: str
    recommendation_uuid: str
    recommendation_digest: str
    recommendation_state: str
    readiness_state: str
    readiness_classification: str
    readiness_reason: str
    recommendation_snapshot_uuid: str
    recommendation_snapshot_digest: str
    recommendation_repository_digest: str
    readiness_policy_uuid: str
    readiness_policy_digest: str
    readiness_policy_version: str
    readiness_engine_version: str
    created_at: str
    authority_scope: str = AUTHORITY_SCOPE
    advisory_only: bool = True

    def __post_init__(self):
        readiness_policy = ExecutionReadinessPolicy()
        allowed = {
            "REJECTED": {("REJECTED", "RECOMMENDATION_REJECTED")},
            "INSUFFICIENT_RECOMMENDATION_EVIDENCE": {("INSUFFICIENT_EXECUTION_READINESS", "RECOMMENDATION_EVIDENCE_INSUFFICIENT")},
            "RECOMMENDATION_READY": {
                ("EXECUTION_READY_FOR_ENVIRONMENT_CHECK", "ADVISORY_PIPELINE_COMPLETE"),
            },
            "RECOMMENDATION_MANUAL_REVIEW": {("INSUFFICIENT_EXECUTION_READINESS", "RECOMMENDATION_REQUIRES_MANUAL_REVIEW")},
            "RECOMMENDATION_NOT_READY": {("INSUFFICIENT_EXECUTION_READINESS", "RECOMMENDATION_NOT_READY")},
        }
        expected_class = {
            "RECOMMENDATION_REJECTED": "REJECTED",
            "RECOMMENDATION_EVIDENCE_INSUFFICIENT": "INSUFFICIENT_EXECUTION_READINESS",
            "ADVISORY_PIPELINE_COMPLETE": "READY_FOR_ENVIRONMENT_CHECK",
            "RECOMMENDATION_REQUIRES_MANUAL_REVIEW": "INSUFFICIENT_EXECUTION_READINESS",
            "RECOMMENDATION_NOT_READY": "INSUFFICIENT_EXECUTION_READINESS",
        }
        if (
            not all(
                valid_uuid(x)
                for x in (
                    self.execution_readiness_uuid,
                    self.recommendation_uuid,
                    self.recommendation_snapshot_uuid,
                    self.readiness_policy_uuid,
                )
            )
            or not all(
                valid_digest(x)
                for x in (
                    self.execution_readiness_digest,
                    self.recommendation_digest,
                    self.recommendation_snapshot_digest,
                    self.recommendation_repository_digest,
                    self.readiness_policy_digest,
                )
            )
            or self.recommendation_state not in RECOMMENDATION_STATES
            or (self.readiness_state, self.readiness_reason)
            not in allowed.get(self.recommendation_state, set())
            or self.readiness_classification not in EXECUTION_READINESS_CLASSIFICATIONS
            or expected_class.get(self.readiness_reason)
            != self.readiness_classification
            or self.readiness_policy_version != "PR186-EXECUTION_READINESS-POLICY.1.0"
            or self.readiness_engine_version != "PR186.1.0"
            or self.readiness_policy_uuid != readiness_policy.readiness_policy_uuid
            or self.readiness_policy_digest != readiness_policy.readiness_policy_digest
            or not valid_timestamp(self.created_at)
            or self.authority_scope != AUTHORITY_SCOPE
            or self.advisory_only is not True
            or execution_readiness_uuid(self.identity_payload()) != self.execution_readiness_uuid
            or digest(self.digest_payload()) != self.execution_readiness_digest
        ):
            raise ValueError("INVALID_EXECUTION_READINESS")

    def identity_payload(self):
        return {
            n: getattr(self, n)
            for n in self.__dataclass_fields__
            if n not in {"execution_readiness_uuid", "execution_readiness_digest"}
        }

    def digest_payload(self):
        return {
            "execution_readiness_uuid": self.execution_readiness_uuid,
            **self.identity_payload(),
        }

    def to_dict(self):
        return self.digest_payload() | {
            "execution_readiness_digest": self.execution_readiness_digest
        }

    @classmethod
    def create(cls, **v):
        uid = execution_readiness_uuid(v)
        return cls(
            execution_readiness_uuid=uid,
            execution_readiness_digest=digest({"execution_readiness_uuid": uid, **v}),
            **v,
        )


@dataclass(frozen=True)
class ExecutionReadinessSnapshot:
    snapshot_uuid: str
    snapshot_digest: str
    readiness_identities: tuple[tuple[str, str], ...]
    record_count: int
    repository_digest: str
    previous_snapshot_uuid: str | None
    previous_snapshot_digest: str | None
    generated_at: str
    readiness_policy_uuid: str
    readiness_policy_digest: str
    readiness_policy_version: str
    readiness_engine_version: str
    recommendation_policy_uuid: str
    recommendation_policy_digest: str
    recommendation_policy_version: str
    recommendation_engine_version: str
    authority_scope: str = AUTHORITY_SCOPE
    advisory_only: bool = True

    def __post_init__(self):
        readiness_policy = ExecutionReadinessPolicy()
        ids = tuple(tuple(x) for x in self.readiness_identities)
        object.__setattr__(self, "readiness_identities", ids)
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
                    self.readiness_policy_uuid,
                    self.recommendation_policy_uuid,
                )
            )
            or not all(
                valid_digest(x)
                for x in (
                    self.snapshot_digest,
                    self.repository_digest,
                    self.readiness_policy_digest,
                    self.recommendation_policy_digest,
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
                    self.readiness_policy_version,
                    self.readiness_engine_version,
                    self.recommendation_policy_version,
                    self.recommendation_engine_version,
                )
            )
            or self.readiness_policy_version != "PR186-EXECUTION_READINESS-POLICY.1.0"
            or self.readiness_engine_version != "PR186.1.0"
            or self.readiness_policy_uuid != readiness_policy.readiness_policy_uuid
            or self.readiness_policy_digest != readiness_policy.readiness_policy_digest
            or self.recommendation_policy_version != "PR185-RECOMMENDATION-POLICY.1.0"
            or self.recommendation_engine_version != "PR185.1.0"
            or not valid_timestamp(self.generated_at)
            or self.authority_scope != AUTHORITY_SCOPE
            or self.advisory_only is not True
            or snapshot_uuid(self.identity_payload()) != self.snapshot_uuid
            or digest(self.identity_payload()) != self.snapshot_digest
        ):
            raise ValueError("INVALID_EXECUTION_READINESS_SNAPSHOT")

    def identity_payload(self):
        return {
            n: (
                [list(x) for x in self.readiness_identities]
                if n == "readiness_identities"
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
        v["readiness_identities"] = tuple(v["readiness_identities"])
        p = {
            **v,
            "readiness_identities": [
                list(x) for x in v["readiness_identities"]
            ],
        }
        uid = snapshot_uuid(p)
        return cls(snapshot_uuid=uid, snapshot_digest=digest(p), **v)


@dataclass(frozen=True)
class ExecutionReadinessReport:
    report_uuid: str
    report_digest: str
    execution_readiness_records: tuple[ExecutionReadiness, ...]
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
            ExecutionReadiness(**x) if isinstance(x, Mapping) else x
            for x in self.execution_readiness_records
        )
        object.__setattr__(self, "execution_readiness_records", items)
        if (
            not all(type(x) is ExecutionReadiness for x in items)
            or self.processed_count != len(items)
            or self.ready_count
            != sum(x.readiness_state == "EXECUTION_READY_FOR_ENVIRONMENT_CHECK" for x in items)
            or self.insufficient_count
            != sum(
                x.readiness_state == "INSUFFICIENT_EXECUTION_READINESS"
                for x in items
            )
            or self.rejected_count
            != sum(x.readiness_state == "REJECTED" for x in items)
            or len({x.execution_readiness_uuid for x in items}) != len(items)
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
            raise ValueError("INVALID_EXECUTION_READINESS_REPORT")

    def identity_payload(self):
        return {
            n: (
                [x.to_dict() for x in self.execution_readiness_records]
                if n == "execution_readiness_records"
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
        v["execution_readiness_records"] = tuple(v["execution_readiness_records"])
        p = {**v, "execution_readiness_records": [x.to_dict() for x in v["execution_readiness_records"]]}
        uid = report_uuid(p)
        return cls(
            report_uuid=uid, report_digest=digest({"report_uuid": uid, **p}), **v
        )
