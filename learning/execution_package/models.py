"""Immutable advisory-only PR189 packages, reports, and snapshots."""

from dataclasses import dataclass
from learning.pattern_memory.models import valid_digest, valid_timestamp, valid_uuid
from .identity import digest, execution_package_uuid, report_uuid, snapshot_uuid

AUTHORITY_SCOPE = "ADVISORY_EXECUTION_PACKAGE_ASSEMBLY_ONLY"
PACKAGE_STATES = ("REJECTED", "PACKAGE_INCOMPLETE", "PACKAGE_READY")


def _valid_partition(uuid, dgst, version, engine):
    return (valid_uuid(uuid) and valid_digest(dgst) and
            all(isinstance(value, str) and value.strip() for value in (version, engine)))


@dataclass(frozen=True)
class ExecutionPackage:
    execution_package_uuid: str
    execution_package_digest: str
    execution_readiness_uuid: str
    execution_readiness_digest: str
    execution_environment_uuid: str
    execution_environment_digest: str
    execution_feasibility_uuid: str
    execution_feasibility_digest: str
    snapshot_chain_digest: str
    repository_digest: str
    policy_digest: str
    engine_versions: tuple[tuple[str, str], ...]
    package_state: str
    package_reason: str
    created_at: str
    package_policy_uuid: str
    package_policy_version: str
    package_engine_version: str
    authority_scope: str = AUTHORITY_SCOPE
    advisory_only: bool = True

    def __post_init__(self):
        versions = tuple(tuple(value) for value in self.engine_versions)
        object.__setattr__(self, "engine_versions", versions)
        reasons = {"REJECTED": "UPSTREAM_REJECTED", "PACKAGE_INCOMPLETE": "UPSTREAM_ARTIFACTS_INCOMPLETE",
                   "PACKAGE_READY": "IMMUTABLE_ADVISORY_PACKAGE_ASSEMBLED"}
        if (not all(valid_uuid(value) for value in (self.execution_package_uuid, self.execution_readiness_uuid,
                self.execution_environment_uuid, self.execution_feasibility_uuid, self.package_policy_uuid))
            or not all(valid_digest(value) for value in (self.execution_package_digest, self.execution_readiness_digest,
                self.execution_environment_digest, self.execution_feasibility_digest, self.snapshot_chain_digest,
                self.repository_digest, self.policy_digest))
            or tuple(name for name, _ in versions) != ("readiness", "environment", "feasibility", "package")
            or any(not isinstance(version, str) or not version.strip() for _, version in versions)
            or self.package_state not in PACKAGE_STATES or self.package_reason != reasons[self.package_state]
            or not _valid_partition(self.package_policy_uuid, self.policy_digest, self.package_policy_version,
                                    self.package_engine_version)
            or not valid_timestamp(self.created_at) or self.authority_scope != AUTHORITY_SCOPE
            or self.advisory_only is not True
            or execution_package_uuid(self.identity_payload()) != self.execution_package_uuid
            or digest(self.digest_payload()) != self.execution_package_digest):
            raise ValueError("INVALID_EXECUTION_PACKAGE")

    def identity_payload(self):
        return {name: ([list(value) for value in self.engine_versions] if name == "engine_versions" else getattr(self, name))
                for name in self.__dataclass_fields__ if name not in {"execution_package_uuid", "execution_package_digest"}}

    def digest_payload(self):
        return {"execution_package_uuid": self.execution_package_uuid, **self.identity_payload()}

    def to_dict(self):
        return {**self.digest_payload(), "execution_package_digest": self.execution_package_digest}

    @classmethod
    def create(cls, **values):
        values["engine_versions"] = tuple(values["engine_versions"])
        payload = {**values, "engine_versions": [list(value) for value in values["engine_versions"]]}
        uid = execution_package_uuid(payload)
        return cls(execution_package_uuid=uid,
                   execution_package_digest=digest({"execution_package_uuid": uid, **payload}), **values)


@dataclass(frozen=True)
class ExecutionPackageSnapshot:
    snapshot_uuid: str
    snapshot_digest: str
    package_identities: tuple[tuple[str, str], ...]
    record_count: int
    repository_digest: str
    previous_snapshot_uuid: str | None
    previous_snapshot_digest: str | None
    generated_at: str
    package_policy_uuid: str
    package_policy_digest: str
    package_policy_version: str
    package_engine_version: str
    advisory_only: bool = True

    def __post_init__(self):
        identities = tuple(tuple(value) for value in self.package_identities)
        object.__setattr__(self, "package_identities", identities)
        previous = ((self.previous_snapshot_uuid is None and self.previous_snapshot_digest is None) or
                    (valid_uuid(self.previous_snapshot_uuid) and valid_digest(self.previous_snapshot_digest)))
        if (not valid_uuid(self.snapshot_uuid) or not valid_digest(self.snapshot_digest)
            or identities != tuple(sorted(identities)) or self.record_count != len(identities)
            or len({value[0] for value in identities}) != len(identities)
            or any(not valid_uuid(uid) or not valid_digest(dgst) for uid, dgst in identities)
            or not valid_digest(self.repository_digest) or not previous or not valid_timestamp(self.generated_at)
            or not _valid_partition(self.package_policy_uuid, self.package_policy_digest,
                                    self.package_policy_version, self.package_engine_version)
            or self.advisory_only is not True or snapshot_uuid(self.identity_payload()) != self.snapshot_uuid
            or digest(self.identity_payload()) != self.snapshot_digest):
            raise ValueError("INVALID_EXECUTION_PACKAGE_SNAPSHOT")

    def identity_payload(self):
        return {name: ([list(value) for value in self.package_identities] if name == "package_identities" else getattr(self, name))
                for name in self.__dataclass_fields__ if name not in {"snapshot_uuid", "snapshot_digest"}}

    def to_dict(self):
        return {"snapshot_uuid": self.snapshot_uuid, "snapshot_digest": self.snapshot_digest, **self.identity_payload()}

    @classmethod
    def create(cls, **values):
        values["package_identities"] = tuple(values["package_identities"])
        payload = {**values, "package_identities": [list(value) for value in values["package_identities"]]}
        return cls(snapshot_uuid=snapshot_uuid(payload), snapshot_digest=digest(payload), **values)


@dataclass(frozen=True)
class ExecutionPackageReport:
    report_uuid: str
    report_digest: str
    package_uuid: str
    package_digest: str
    assembled_records: tuple[tuple[str, str], ...]
    validation_status: str
    repository_digest: str
    snapshot_uuid: str
    snapshot_digest: str
    generated_at: str
    duplicate: bool
    advisory_only: bool = True

    def __post_init__(self):
        records = tuple(tuple(value) for value in self.assembled_records)
        object.__setattr__(self, "assembled_records", records)
        if (not valid_uuid(self.report_uuid) or not valid_digest(self.report_digest)
            or not valid_uuid(self.package_uuid) or not valid_digest(self.package_digest)
            or tuple(name for name, _ in records) != ("readiness", "environment", "feasibility")
            or any(not valid_uuid(uid) for _, uid in records) or self.validation_status not in PACKAGE_STATES
            or not valid_digest(self.repository_digest) or not valid_uuid(self.snapshot_uuid)
            or not valid_digest(self.snapshot_digest) or not valid_timestamp(self.generated_at)
            or type(self.duplicate) is not bool or self.advisory_only is not True
            or report_uuid(self.identity_payload()) != self.report_uuid or digest(self.digest_payload()) != self.report_digest):
            raise ValueError("INVALID_EXECUTION_PACKAGE_REPORT")

    def identity_payload(self):
        return {name: ([list(value) for value in self.assembled_records] if name == "assembled_records" else getattr(self, name))
                for name in self.__dataclass_fields__ if name not in {"report_uuid", "report_digest"}}

    def digest_payload(self):
        return {"report_uuid": self.report_uuid, **self.identity_payload()}

    def to_dict(self):
        return {"report_uuid": self.report_uuid, "report_digest": self.report_digest, **self.identity_payload()}

    @classmethod
    def create(cls, **values):
        values["assembled_records"] = tuple(values["assembled_records"])
        payload = {**values, "assembled_records": [list(value) for value in values["assembled_records"]]}
        uid = report_uuid(payload)
        return cls(report_uuid=uid, report_digest=digest({"report_uuid": uid, **payload}), **values)
