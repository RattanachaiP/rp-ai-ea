"""Immutable PR187 environment evidence, result, report, and snapshot artifacts."""

from collections.abc import Mapping
from dataclasses import dataclass
from math import isfinite
from types import MappingProxyType
from learning.pattern_memory.models import valid_digest, valid_timestamp, valid_uuid
from learning.execution_readiness.models import EXECUTION_READINESS_STATES
from .identity import (
    digest,
    environment_evidence_uuid,
    execution_environment_uuid,
    report_uuid,
    snapshot_uuid,
)
from .policy import ENVIRONMENT_DIMENSIONS, ExecutionEnvironmentPolicy

AUTHORITY_SCOPE = "ADVISORY_EXECUTION_ENVIRONMENT_ONLY"
EXECUTION_ENVIRONMENT_STATES = (
    "REJECTED",
    "INSUFFICIENT_ENVIRONMENT_INFORMATION",
    "ENVIRONMENT_READY_FOR_FEASIBILITY",
)


def _version(value):
    return isinstance(value, str) and bool(value) and value == value.strip()


def _partition_valid(uuid, dgst, version, engine):
    return (
        valid_uuid(uuid)
        and valid_digest(dgst)
        and _version(version)
        and _version(engine)
    )


def _canonical_observation_subset(observations):
    if any(len(item) != 2 for item in observations):
        return False
    names = tuple(item[0] for item in observations)
    if len(names) != len(set(names)) or any(name not in ENVIRONMENT_DIMENSIONS for name in names):
        return False
    expected_order = tuple(name for name in ENVIRONMENT_DIMENSIONS if name in set(names))
    return names == expected_order


@dataclass(frozen=True)
class ExecutionEnvironmentEvidence:
    evidence_uuid: str
    evidence_digest: str
    execution_readiness_uuid: str
    execution_readiness_digest: str
    observations: tuple[tuple[str, float], ...]
    captured_at: str
    readiness_snapshot_uuid: str
    readiness_snapshot_digest: str
    readiness_repository_digest: str
    readiness_policy_uuid: str
    readiness_policy_digest: str
    readiness_policy_version: str
    readiness_engine_version: str
    advisory_only: bool = True

    def __post_init__(self):
        observations = tuple(tuple(item) for item in self.observations)
        object.__setattr__(self, "observations", observations)
        if (
            not valid_uuid(self.evidence_uuid)
            or not valid_digest(self.evidence_digest)
            or not valid_uuid(self.execution_readiness_uuid)
            or not valid_digest(self.execution_readiness_digest)
            or not _canonical_observation_subset(observations)
            or any(
                type(value) is not float or not isfinite(value) or value < 0
                for _, value in observations
            )
            or not valid_timestamp(self.captured_at)
            or not valid_uuid(self.readiness_snapshot_uuid)
            or not valid_digest(self.readiness_snapshot_digest)
            or not valid_digest(self.readiness_repository_digest)
            or not _partition_valid(
                self.readiness_policy_uuid,
                self.readiness_policy_digest,
                self.readiness_policy_version,
                self.readiness_engine_version,
            )
            or self.advisory_only is not True
            or environment_evidence_uuid(self.identity_payload()) != self.evidence_uuid
            or digest(self.digest_payload()) != self.evidence_digest
        ):
            raise ValueError("INVALID_EXECUTION_ENVIRONMENT_EVIDENCE")

    def identity_payload(self):
        return {
            name: (
                [list(item) for item in self.observations]
                if name == "observations"
                else getattr(self, name)
            )
            for name in self.__dataclass_fields__
            if name not in {"evidence_uuid", "evidence_digest"}
        }

    def digest_payload(self):
        return {"evidence_uuid": self.evidence_uuid, **self.identity_payload()}

    def to_dict(self):
        return {**self.digest_payload(), "evidence_digest": self.evidence_digest}

    @classmethod
    def create(cls, **values):
        values = dict(values)
        values["observations"] = tuple(values["observations"])
        observations = values["observations"]
        if (
            not _canonical_observation_subset(observations)
            or any(
                type(value) is not float or not isfinite(value) or value < 0
                for _, value in observations
            )
        ):
            raise ValueError("INVALID_EXECUTION_ENVIRONMENT_EVIDENCE")
        payload = {**values, "observations": [list(item) for item in observations]}
        uid = environment_evidence_uuid(payload)
        return cls(
            evidence_uuid=uid,
            evidence_digest=digest({"evidence_uuid": uid, **payload}),
            **values,
        )


@dataclass(frozen=True)
class ExecutionEnvironment:
    execution_environment_uuid: str
    execution_environment_digest: str
    execution_readiness_uuid: str
    execution_readiness_digest: str
    readiness_state: str
    evidence_uuid: str | None
    evidence_digest: str | None
    environment_evidence_complete: bool
    environment_state: str
    environment_reason: str
    environment_profile: tuple[tuple[str, str], ...]
    environment_quality: float
    readiness_snapshot_uuid: str
    readiness_snapshot_digest: str
    readiness_repository_digest: str
    environment_policy: Mapping
    environment_policy_uuid: str
    environment_policy_digest: str
    environment_policy_version: str
    environment_engine_version: str
    created_at: str
    authority_scope: str = AUTHORITY_SCOPE
    advisory_only: bool = True

    def __post_init__(self):
        profile = tuple(tuple(item) for item in self.environment_profile)
        object.__setattr__(self, "environment_profile", profile)
        policy_data = dict(self.environment_policy)
        object.__setattr__(self, "environment_policy", MappingProxyType(policy_data))
        try:
            policy = ExecutionEnvironmentPolicy(**policy_data)
        except (TypeError, ValueError):
            policy = None
        names = tuple(item[0] for item in profile if len(item) == 2)
        evidence_pair = (
            self.evidence_uuid is None and self.evidence_digest is None
        ) or (valid_uuid(self.evidence_uuid) and valid_digest(self.evidence_digest))
        critical_ready = bool(policy and policy.critical_dimensions_available(profile))
        expected_state = (
            "REJECTED"
            if self.readiness_state == "REJECTED"
            else (
                "ENVIRONMENT_READY_FOR_FEASIBILITY"
                if self.evidence_uuid is not None
                and self.environment_evidence_complete is True
                and critical_ready
                and self.environment_quality >= (policy.minimum_quality if policy else 2)
                else "INSUFFICIENT_ENVIRONMENT_INFORMATION"
            )
        )
        expected_reason = {
            "REJECTED": "READINESS_REJECTED",
            "ENVIRONMENT_READY_FOR_FEASIBILITY": "ENVIRONMENT_QUALITY_SUFFICIENT",
            "INSUFFICIENT_ENVIRONMENT_INFORMATION": "ENVIRONMENT_EVIDENCE_INSUFFICIENT",
        }[expected_state]
        if (
            not valid_uuid(self.execution_environment_uuid)
            or not valid_digest(self.execution_environment_digest)
            or not valid_uuid(self.execution_readiness_uuid)
            or not valid_digest(self.execution_readiness_digest)
            or self.readiness_state not in EXECUTION_READINESS_STATES
            or not evidence_pair
            or type(self.environment_evidence_complete) is not bool
            or len(profile) != len(ENVIRONMENT_DIMENSIONS)
            or names != ENVIRONMENT_DIMENSIONS
            or any(value not in {"AVAILABLE", "UNAVAILABLE"} for _, value in profile)
            or type(self.environment_quality) is not float
            or not isfinite(self.environment_quality)
            or not 0 <= self.environment_quality <= 1
            or self.environment_quality
            != sum(value == "AVAILABLE" for _, value in profile) / len(profile)
            or self.environment_state != expected_state
            or self.environment_reason != expected_reason
            or policy is None
            or self.environment_policy_uuid != policy.environment_policy_uuid
            or self.environment_policy_digest != policy.environment_policy_digest
            or self.environment_policy_version != policy.environment_policy_version
            or self.environment_engine_version != policy.environment_engine_version
            or not valid_uuid(self.readiness_snapshot_uuid)
            or not valid_digest(self.readiness_snapshot_digest)
            or not valid_digest(self.readiness_repository_digest)
            or not valid_timestamp(self.created_at)
            or self.authority_scope != AUTHORITY_SCOPE
            or self.advisory_only is not True
            or execution_environment_uuid(self.identity_payload())
            != self.execution_environment_uuid
            or digest(self.digest_payload()) != self.execution_environment_digest
        ):
            raise ValueError("INVALID_EXECUTION_ENVIRONMENT")

    def identity_payload(self):
        return {
            name: (
                [list(item) for item in self.environment_profile]
                if name == "environment_profile"
                else (
                    dict(self.environment_policy)
                    if name == "environment_policy"
                    else getattr(self, name)
                )
            )
            for name in self.__dataclass_fields__
            if name not in {"execution_environment_uuid", "execution_environment_digest"}
        }

    def digest_payload(self):
        return {
            "execution_environment_uuid": self.execution_environment_uuid,
            **self.identity_payload(),
        }

    def to_dict(self):
        return {
            **self.digest_payload(),
            "execution_environment_digest": self.execution_environment_digest,
        }

    @classmethod
    def create(cls, **values):
        uid = execution_environment_uuid(values)
        return cls(
            execution_environment_uuid=uid,
            execution_environment_digest=digest(
                {"execution_environment_uuid": uid, **values}
            ),
            **values,
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
        identities = tuple(tuple(item) for item in self.environment_identities)
        object.__setattr__(self, "environment_identities", identities)
        previous_valid = (
            self.previous_snapshot_uuid is None
            and self.previous_snapshot_digest is None
        ) or (
            valid_uuid(self.previous_snapshot_uuid)
            and valid_digest(self.previous_snapshot_digest)
        )
        if (
            not valid_uuid(self.snapshot_uuid)
            or not valid_digest(self.snapshot_digest)
            or not valid_digest(self.repository_digest)
            or identities != tuple(sorted(identities))
            or self.record_count != len(identities)
            or len({item[0] for item in identities}) != len(identities)
            or any(
                not valid_uuid(item[0]) or not valid_digest(item[1])
                for item in identities
            )
            or not previous_valid
            or not _partition_valid(
                self.environment_policy_uuid,
                self.environment_policy_digest,
                self.environment_policy_version,
                self.environment_engine_version,
            )
            or not _partition_valid(
                self.readiness_policy_uuid,
                self.readiness_policy_digest,
                self.readiness_policy_version,
                self.readiness_engine_version,
            )
            or not valid_timestamp(self.generated_at)
            or self.authority_scope != AUTHORITY_SCOPE
            or self.advisory_only is not True
            or snapshot_uuid(self.identity_payload()) != self.snapshot_uuid
            or digest(self.identity_payload()) != self.snapshot_digest
        ):
            raise ValueError("INVALID_EXECUTION_ENVIRONMENT_SNAPSHOT")

    def identity_payload(self):
        return {
            name: (
                [list(item) for item in self.environment_identities]
                if name == "environment_identities"
                else getattr(self, name)
            )
            for name in self.__dataclass_fields__
            if name not in {"snapshot_uuid", "snapshot_digest"}
        }

    def to_dict(self):
        return {
            "snapshot_uuid": self.snapshot_uuid,
            "snapshot_digest": self.snapshot_digest,
            **self.identity_payload(),
        }

    @classmethod
    def create(cls, **values):
        values = dict(values)
        values["environment_identities"] = tuple(values["environment_identities"])
        payload = {
            **values,
            "environment_identities": [
                list(item) for item in values["environment_identities"]
            ],
        }
        uid = snapshot_uuid(payload)
        return cls(snapshot_uuid=uid, snapshot_digest=digest(payload), **values)


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
            ExecutionEnvironment(**item) if isinstance(item, Mapping) else item
            for item in self.execution_environment_records
        )
        object.__setattr__(self, "execution_environment_records", items)
        if (
            any(type(item) is not ExecutionEnvironment for item in items)
            or self.processed_count != len(items)
            or self.ready_count
            != sum(
                item.environment_state == "ENVIRONMENT_READY_FOR_FEASIBILITY"
                for item in items
            )
            or self.insufficient_count
            != sum(
                item.environment_state == "INSUFFICIENT_ENVIRONMENT_INFORMATION"
                for item in items
            )
            or self.rejected_count
            != sum(item.environment_state == "REJECTED" for item in items)
            or len({item.execution_environment_uuid for item in items}) != len(items)
            or type(self.duplicate_count) is not int
            or not 0 <= self.duplicate_count <= len(items)
            or not valid_uuid(self.report_uuid)
            or not valid_digest(self.report_digest)
            or not valid_digest(self.repository_digest)
            or not valid_uuid(self.snapshot_uuid)
            or not valid_digest(self.snapshot_digest)
            or not valid_timestamp(self.generated_at)
            or self.advisory_only is not True
            or report_uuid(self.identity_payload()) != self.report_uuid
            or digest(self.digest_payload()) != self.report_digest
        ):
            raise ValueError("INVALID_EXECUTION_ENVIRONMENT_REPORT")

    def identity_payload(self):
        return {
            name: (
                [item.to_dict() for item in self.execution_environment_records]
                if name == "execution_environment_records"
                else getattr(self, name)
            )
            for name in self.__dataclass_fields__
            if name not in {"report_uuid", "report_digest"}
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
    def create(cls, **values):
        values = dict(values)
        values["execution_environment_records"] = tuple(
            values["execution_environment_records"]
        )
        payload = {
            **values,
            "execution_environment_records": [
                item.to_dict() for item in values["execution_environment_records"]
            ],
        }
        uid = report_uuid(payload)
        return cls(
            report_uuid=uid,
            report_digest=digest({"report_uuid": uid, **payload}),
            **values,
        )
