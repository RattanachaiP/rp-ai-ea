"""Immutable advisory artifacts exported by the PR180 consumption gate."""

from dataclasses import dataclass

from learning.pattern_memory.models import valid_digest, valid_timestamp, valid_uuid

from .identity import digest, package_uuid, report_uuid, snapshot_uuid


def _valid_text(*values):
    return all(isinstance(value, str) and value for value in values)


@dataclass(frozen=True)
class RuntimeKnowledgePackage:
    runtime_package_uuid: str
    runtime_package_digest: str
    registry_uuid: str
    registry_digest: str
    knowledge_uuid: str
    knowledge_version: str
    pattern_uuid: str
    pattern_hash: str
    promotion_uuid: str
    validation_uuid: str
    memory_uuid: str
    policy_uuid: str
    source_digest: str
    replay_digest: str
    runtime_policy_version: str
    runtime_engine_version: str
    generated_at: str
    advisory_only: bool = True

    def __post_init__(self):
        uuids = (self.runtime_package_uuid, self.registry_uuid, self.knowledge_uuid,
                 self.pattern_uuid, self.promotion_uuid, self.validation_uuid,
                 self.memory_uuid, self.policy_uuid)
        digests = (self.runtime_package_digest, self.registry_digest, self.pattern_hash,
                   self.source_digest, self.replay_digest)
        if (not all(valid_uuid(value) for value in uuids)
                or not all(valid_digest(value) for value in digests)
                or not _valid_text(self.knowledge_version, self.runtime_policy_version,
                                   self.runtime_engine_version)
                or not valid_timestamp(self.generated_at) or self.advisory_only is not True
                or package_uuid(self.identity_payload()) != self.runtime_package_uuid
                or digest(self.digest_payload()) != self.runtime_package_digest):
            raise ValueError("INVALID_RUNTIME_KNOWLEDGE_PACKAGE")

    def identity_payload(self):
        return {name: getattr(self, name) for name in self.__dataclass_fields__
                if name not in {"runtime_package_uuid", "runtime_package_digest"}}

    def digest_payload(self):
        return {"runtime_package_uuid": self.runtime_package_uuid, **self.identity_payload()}

    def to_dict(self):
        return {"runtime_package_uuid": self.runtime_package_uuid,
                "runtime_package_digest": self.runtime_package_digest,
                **self.identity_payload()}

    @classmethod
    def create(cls, **values):
        identity = package_uuid(values)
        return cls(runtime_package_uuid=identity,
                   runtime_package_digest=digest({"runtime_package_uuid": identity, **values}),
                   **values)


@dataclass(frozen=True)
class RuntimeKnowledgeSnapshot:
    snapshot_uuid: str
    snapshot_digest: str
    source_registry_snapshot_uuid: str
    source_registry_snapshot_digest: str
    source_registry_repository_digest: str
    package_identities: tuple[tuple[str, str], ...]
    package_count: int
    repository_digest: str
    runtime_policy_version: str
    runtime_engine_version: str
    previous_snapshot_uuid: str | None
    previous_snapshot_digest: str | None
    generated_at: str
    advisory_only: bool = True

    def __post_init__(self):
        identities = tuple(tuple(item) for item in self.package_identities)
        object.__setattr__(self, "package_identities", identities)
        previous_valid = ((self.previous_snapshot_uuid is None and self.previous_snapshot_digest is None)
                          or (valid_uuid(self.previous_snapshot_uuid)
                              and valid_digest(self.previous_snapshot_digest)))
        if (not valid_uuid(self.snapshot_uuid)
                or not all(valid_uuid(value) for value in
                           (self.source_registry_snapshot_uuid,))
                or not all(valid_digest(value) for value in
                           (self.snapshot_digest, self.source_registry_snapshot_digest,
                            self.source_registry_repository_digest, self.repository_digest))
                or identities != tuple(sorted(identities))
                or self.package_count != len(identities)
                or len({item[0] for item in identities}) != len(identities)
                or not all(len(item) == 2 and valid_uuid(item[0]) and valid_digest(item[1])
                           for item in identities)
                or not previous_valid
                or not _valid_text(self.runtime_policy_version, self.runtime_engine_version)
                or not valid_timestamp(self.generated_at) or self.advisory_only is not True
                or snapshot_uuid(self.identity_payload()) != self.snapshot_uuid
                or digest(self.identity_payload()) != self.snapshot_digest):
            raise ValueError("INVALID_RUNTIME_KNOWLEDGE_SNAPSHOT")

    def identity_payload(self):
        return {name: ([list(item) for item in self.package_identities]
                       if name == "package_identities" else getattr(self, name))
                for name in self.__dataclass_fields__ if name not in {"snapshot_uuid", "snapshot_digest"}}

    def to_dict(self):
        return {"snapshot_uuid": self.snapshot_uuid, "snapshot_digest": self.snapshot_digest,
                **self.identity_payload()}

    @classmethod
    def create(cls, **values):
        values["package_identities"] = tuple(sorted(values["package_identities"]))
        payload = {**values, "package_identities": [list(item) for item in values["package_identities"]]}
        return cls(snapshot_uuid=snapshot_uuid(payload), snapshot_digest=digest(payload), **values)


@dataclass(frozen=True)
class RuntimeKnowledgeConsumptionReport:
    report_uuid: str
    source_artifact_type: str
    source_registry_report_uuid: str | None
    source_registry_uuid: str | None
    source_registry_snapshot_uuid: str
    source_registry_snapshot_digest: str
    source_registry_repository_digest: str
    runtime_packages: tuple[RuntimeKnowledgePackage, ...]
    processed_record_count: int
    new_package_count: int
    duplicate_package_count: int
    repository_digest: str
    snapshot_uuid: str
    snapshot_digest: str
    runtime_policy_version: str
    runtime_engine_version: str
    generated_at: str
    advisory_only: bool = True

    def __post_init__(self):
        packages = tuple(self.runtime_packages)
        object.__setattr__(self, "runtime_packages", packages)
        source_valid = ((self.source_artifact_type == "KNOWLEDGE_REGISTRY_REPORT"
                         and valid_uuid(self.source_registry_report_uuid)
                         and self.source_registry_uuid is None)
                        or (self.source_artifact_type == "KNOWLEDGE_REGISTRY_RECORD"
                            and valid_uuid(self.source_registry_uuid)
                            and self.source_registry_report_uuid is None))
        if (not valid_uuid(self.report_uuid) or not source_valid
                or not all(valid_uuid(value) for value in
                           (self.source_registry_snapshot_uuid, self.snapshot_uuid))
                or not all(valid_digest(value) for value in
                           (self.source_registry_snapshot_digest,
                            self.source_registry_repository_digest, self.repository_digest,
                            self.snapshot_digest))
                or not all(type(item) is RuntimeKnowledgePackage for item in packages)
                or self.processed_record_count != len(packages)
                or self.new_package_count + self.duplicate_package_count != len(packages)
                or not _valid_text(self.runtime_policy_version, self.runtime_engine_version)
                or not valid_timestamp(self.generated_at) or self.advisory_only is not True
                or report_uuid(self.identity_payload()) != self.report_uuid):
            raise ValueError("INVALID_RUNTIME_KNOWLEDGE_CONSUMPTION_REPORT")

    def identity_payload(self):
        return {name: ([item.to_dict() for item in self.runtime_packages]
                       if name == "runtime_packages" else getattr(self, name))
                for name in self.__dataclass_fields__ if name != "report_uuid"}

    def to_dict(self):
        return {"report_uuid": self.report_uuid, **self.identity_payload()}

    @classmethod
    def create(cls, **values):
        payload = {**values, "runtime_packages": [item.to_dict() for item in values["runtime_packages"]]}
        return cls(report_uuid=report_uuid(payload), **values)
