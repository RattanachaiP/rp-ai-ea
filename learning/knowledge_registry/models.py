"""Immutable, advisory-only PR179 governance artifacts."""
from dataclasses import dataclass
from learning.pattern_memory.models import valid_digest, valid_timestamp, valid_uuid
from .identity import digest, registry_report_uuid, registry_snapshot_uuid, registry_uuid

REGISTRY_STATES = ("REJECTED", "NOT_ADMITTED", "REGISTERED")


def _strings(values): return all(isinstance(value, str) and value for value in values)


@dataclass(frozen=True)
class RegistryRecord:
    registry_uuid: str
    registry_digest: str
    promotion_uuid: str
    promotion_digest: str
    validation_uuid: str
    memory_uuid: str
    pattern_uuid: str
    knowledge_uuid: str
    registry_version: str
    registry_state: str
    registry_reasons: tuple[str, ...]
    registered_at: str
    advisory_only: bool = True

    def __post_init__(self):
        object.__setattr__(self, "registry_reasons", tuple(self.registry_reasons))
        if (not all(valid_uuid(value) for value in (self.registry_uuid, self.promotion_uuid,
                self.validation_uuid, self.memory_uuid, self.pattern_uuid, self.knowledge_uuid))
                or not all(valid_digest(value) for value in (self.registry_digest, self.promotion_digest))
                or not isinstance(self.registry_version, str) or not self.registry_version
                or self.registry_state not in REGISTRY_STATES or not self.registry_reasons
                or not _strings(self.registry_reasons) or not valid_timestamp(self.registered_at)
                or self.advisory_only is not True
                or registry_uuid(self.identity_payload()) != self.registry_uuid
                or digest(self.digest_payload()) != self.registry_digest):
            raise ValueError("INVALID_REGISTRY_RECORD")

    def identity_payload(self):
        return {name: getattr(self, name) for name in self.__dataclass_fields__
                if name not in {"registry_uuid", "registry_digest"}}

    def digest_payload(self): return {"registry_uuid": self.registry_uuid, **self.identity_payload()}
    def to_dict(self): return {"registry_uuid": self.registry_uuid,
                               "registry_digest": self.registry_digest, **self.identity_payload()}

    @classmethod
    def create(cls, **values):
        values["registry_reasons"] = tuple(values["registry_reasons"])
        identifier = registry_uuid(values)
        return cls(registry_uuid=identifier,
                   registry_digest=digest({"registry_uuid": identifier, **values}), **values)


@dataclass(frozen=True)
class KnowledgeRegistrySnapshot:
    snapshot_uuid: str
    snapshot_digest: str
    registry_version: str
    promotion_engine_version: str
    promotion_policy_uuid: str
    promotion_policy_digest: str
    record_identities: tuple[tuple[str, str], ...]
    repository_digest: str
    previous_snapshot_uuid: str | None
    previous_snapshot_digest: str | None
    generated_at: str
    advisory_only: bool = True

    def __post_init__(self):
        pairs = tuple(tuple(pair) for pair in self.record_identities)
        object.__setattr__(self, "record_identities", pairs)
        if (not valid_uuid(self.snapshot_uuid) or not valid_digest(self.snapshot_digest)
                or not _strings((self.registry_version, self.promotion_engine_version))
                or not valid_uuid(self.promotion_policy_uuid)
                or not all(valid_digest(x) for x in (self.promotion_policy_digest, self.repository_digest))
                or pairs != tuple(sorted(pairs)) or len({x[0] for x in pairs}) != len(pairs)
                or not all(len(x) == 2 and valid_uuid(x[0]) and valid_digest(x[1]) for x in pairs)
                or (self.previous_snapshot_uuid is None) != (self.previous_snapshot_digest is None)
                or (self.previous_snapshot_uuid is not None and not valid_uuid(self.previous_snapshot_uuid))
                or (self.previous_snapshot_digest is not None and not valid_digest(self.previous_snapshot_digest))
                or not valid_timestamp(self.generated_at) or self.advisory_only is not True
                or registry_snapshot_uuid(self.identity_payload()) != self.snapshot_uuid
                or digest(self.identity_payload()) != self.snapshot_digest):
            raise ValueError("INVALID_REGISTRY_SNAPSHOT")

    def identity_payload(self):
        return {name: ([list(x) for x in self.record_identities] if name == "record_identities"
                       else getattr(self, name)) for name in self.__dataclass_fields__
                if name not in {"snapshot_uuid", "snapshot_digest"}}

    def to_dict(self): return {"snapshot_uuid": self.snapshot_uuid,
                               "snapshot_digest": self.snapshot_digest, **self.identity_payload()}

    @classmethod
    def create(cls, **values):
        values["record_identities"] = tuple(sorted(values["record_identities"]))
        payload = {**values, "record_identities": [list(x) for x in values["record_identities"]]}
        return cls(snapshot_uuid=registry_snapshot_uuid(payload), snapshot_digest=digest(payload), **values)


@dataclass(frozen=True)
class KnowledgeRegistryReport:
    report_uuid: str
    source_artifact_type: str
    source_report_uuid: str | None
    source_report_digest: str | None
    promotion_engine_version: str
    promotion_policy_uuid: str
    promotion_policy_digest: str
    registry_records: tuple[RegistryRecord, ...]
    registered_count: int
    rejected_count: int
    duplicate_count: int
    repository_digest: str
    snapshot_uuid: str
    generated_at: str
    advisory_only: bool = True

    def __post_init__(self):
        records = tuple(self.registry_records); object.__setattr__(self, "registry_records", records)
        report_source = self.source_artifact_type == "PATTERN_PROMOTION_REPORT"
        if (not valid_uuid(self.report_uuid) or self.source_artifact_type not in
                ("PROMOTION_RECORD", "PATTERN_PROMOTION_REPORT")
                or (report_source and (not valid_uuid(self.source_report_uuid)
                    or not valid_digest(self.source_report_digest)))
                or (not report_source and (self.source_report_uuid is not None
                    or self.source_report_digest is not None))
                or not _strings((self.promotion_engine_version,))
                or not valid_uuid(self.promotion_policy_uuid)
                or not all(valid_digest(x) for x in (self.promotion_policy_digest, self.repository_digest))
                or not all(type(x) is RegistryRecord for x in records)
                or self.registered_count != sum(x.registry_state == "REGISTERED" for x in records)
                or self.rejected_count != sum(x.registry_state != "REGISTERED" for x in records)
                or not isinstance(self.duplicate_count, int) or self.duplicate_count < 0
                or not valid_uuid(self.snapshot_uuid) or not valid_timestamp(self.generated_at)
                or self.advisory_only is not True
                or registry_report_uuid(self.identity_payload()) != self.report_uuid):
            raise ValueError("INVALID_KNOWLEDGE_REGISTRY_REPORT")

    def identity_payload(self):
        return {name: ([x.to_dict() for x in self.registry_records] if name == "registry_records"
                       else getattr(self, name)) for name in self.__dataclass_fields__ if name != "report_uuid"}
    def to_dict(self): return {"report_uuid": self.report_uuid, **self.identity_payload()}

    @classmethod
    def create(cls, **values):
        payload = {**values, "registry_records": [x.to_dict() for x in values["registry_records"]]}
        return cls(report_uuid=registry_report_uuid(payload), **values)
