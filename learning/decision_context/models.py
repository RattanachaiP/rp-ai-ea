"""Immutable, advisory-only PR183 artifacts."""

from dataclasses import dataclass
from learning.pattern_memory.models import valid_digest, valid_timestamp, valid_uuid
from learning.runtime_confidence.models import PARTITION_FIELDS as CONFIDENCE_PARTITION_FIELDS
from .identity import context_uuid, digest, report_uuid, snapshot_uuid

AUTHORITY_SCOPE = "ADVISORY_DECISION_CONTEXT_ONLY"
CONTEXT_STATES = ("REJECTED", "INSUFFICIENT_CONTEXT_EVIDENCE", "CONTEXT_PREPARED")
SOURCE_ARTIFACT_TYPES = ("CONFIDENCE_RECORD", "CONFIDENCE_REPORT", "CONFIDENCE_SNAPSHOT")
CONTEXT_PARTITION_FIELDS = ("context_policy_uuid", "context_policy_digest", "context_policy_version", "context_engine_version")
PARTITION_FIELDS = CONTEXT_PARTITION_FIELDS + CONFIDENCE_PARTITION_FIELDS


def _serialized(obj, excluded):
    return {name: ([list(x) for x in value] if name.endswith("identities") else value)
            for name in obj.__dataclass_fields__ if name not in excluded
            for value in (getattr(obj, name),)}


@dataclass(frozen=True)
class DecisionContext:
    context_uuid: str
    context_digest: str
    confidence_uuid: str
    confidence_digest: str
    confidence_state: str
    confidence_score: float
    confidence_band: str
    confidence_snapshot_uuid: str
    confidence_snapshot_digest: str
    confidence_repository_digest: str
    context_state: str
    context_reason: str
    context_policy_uuid: str
    context_policy_digest: str
    context_policy_version: str
    context_engine_version: str
    created_at: str
    authority_scope: str = AUTHORITY_SCOPE
    advisory_only: bool = True

    def __post_init__(self):
        if (not all(valid_uuid(x) for x in (self.context_uuid, self.confidence_uuid, self.confidence_snapshot_uuid, self.context_policy_uuid))
                or not all(valid_digest(x) for x in (self.context_digest, self.confidence_digest, self.confidence_snapshot_digest, self.confidence_repository_digest, self.context_policy_digest))
                or self.context_state not in CONTEXT_STATES or not self.context_reason
                or type(self.confidence_score) is not float or not 0 <= self.confidence_score <= 1
                or not valid_timestamp(self.created_at) or self.authority_scope != AUTHORITY_SCOPE
                or self.advisory_only is not True or context_uuid(self.identity_payload()) != self.context_uuid
                or digest(self.digest_payload()) != self.context_digest):
            raise ValueError("INVALID_DECISION_CONTEXT")

    def identity_payload(self): return _serialized(self, {"context_uuid", "context_digest"})
    def digest_payload(self): return {"context_uuid": self.context_uuid, **self.identity_payload()}
    def to_dict(self): return {"context_uuid": self.context_uuid, "context_digest": self.context_digest, **self.identity_payload()}

    @classmethod
    def create(cls, **values):
        identity = context_uuid(values)
        return cls(context_uuid=identity, context_digest=digest({"context_uuid": identity, **values}), **values)


@dataclass(frozen=True)
class DecisionContextSnapshot:
    snapshot_uuid: str
    snapshot_digest: str
    context_identities: tuple[tuple[str, str], ...]
    record_count: int
    repository_digest: str
    previous_snapshot_uuid: str | None
    previous_snapshot_digest: str | None
    generated_at: str
    context_policy_uuid: str
    context_policy_digest: str
    context_policy_version: str
    context_engine_version: str
    confidence_policy_uuid: str
    confidence_policy_digest: str
    confidence_policy_version: str
    confidence_engine_version: str
    authority_scope: str = AUTHORITY_SCOPE
    advisory_only: bool = True

    def __post_init__(self):
        object.__setattr__(self, "context_identities", tuple(tuple(x) for x in self.context_identities))
        previous = (self.previous_snapshot_uuid is None and self.previous_snapshot_digest is None) or (valid_uuid(self.previous_snapshot_uuid) and valid_digest(self.previous_snapshot_digest))
        if (not valid_uuid(self.snapshot_uuid) or not valid_digest(self.snapshot_digest) or self.context_identities != tuple(sorted(self.context_identities))
                or self.record_count != len(self.context_identities) or not valid_digest(self.repository_digest) or not previous
                or not valid_timestamp(self.generated_at) or self.authority_scope != AUTHORITY_SCOPE or self.advisory_only is not True
                or snapshot_uuid(self.identity_payload()) != self.snapshot_uuid or digest(self.identity_payload()) != self.snapshot_digest):
            raise ValueError("INVALID_CONTEXT_SNAPSHOT")

    def identity_payload(self): return _serialized(self, {"snapshot_uuid", "snapshot_digest"})
    def to_dict(self): return {"snapshot_uuid": self.snapshot_uuid, "snapshot_digest": self.snapshot_digest, **self.identity_payload()}
    @classmethod
    def create(cls, **values):
        values["context_identities"] = tuple(values["context_identities"]); payload = {**values, "context_identities": [list(x) for x in values["context_identities"]]}; identity = snapshot_uuid(payload)
        return cls(snapshot_uuid=identity, snapshot_digest=digest(payload), **values)


@dataclass(frozen=True)
class DecisionContextReport:
    report_uuid: str
    report_digest: str
    decision_contexts: tuple[DecisionContext, ...]
    processed_count: int
    prepared_count: int
    insufficient_count: int
    rejected_count: int
    duplicate_count: int
    repository_digest: str
    snapshot_uuid: str
    snapshot_digest: str
    generated_at: str
    advisory_only: bool = True

    def __post_init__(self):
        object.__setattr__(self, "decision_contexts", tuple(self.decision_contexts))
        contexts = self.decision_contexts
        if (self.processed_count != len(contexts) or self.prepared_count != sum(x.context_state == "CONTEXT_PREPARED" for x in contexts)
                or self.insufficient_count != sum(x.context_state == "INSUFFICIENT_CONTEXT_EVIDENCE" for x in contexts)
                or self.rejected_count != sum(x.context_state == "REJECTED" for x in contexts)
                or not all(valid_digest(x) for x in (self.report_digest, self.repository_digest, self.snapshot_digest))
                or not valid_uuid(self.report_uuid) or not valid_uuid(self.snapshot_uuid) or not valid_timestamp(self.generated_at)
                or self.advisory_only is not True or report_uuid(self.identity_payload()) != self.report_uuid or digest(self.digest_payload()) != self.report_digest):
            raise ValueError("INVALID_CONTEXT_REPORT")
    def identity_payload(self):
        return {name: ([x.to_dict() for x in self.decision_contexts] if name == "decision_contexts" else getattr(self, name)) for name in self.__dataclass_fields__ if name not in {"report_uuid", "report_digest"}}
    def digest_payload(self): return {"report_uuid": self.report_uuid, **self.identity_payload()}
    def to_dict(self): return {"report_uuid": self.report_uuid, "report_digest": self.report_digest, **self.identity_payload()}
    @classmethod
    def create(cls, **values):
        values["decision_contexts"] = tuple(values["decision_contexts"]); payload = {**values, "decision_contexts": [x.to_dict() for x in values["decision_contexts"]]}; identity = report_uuid(payload)
        return cls(report_uuid=identity, report_digest=digest({"report_uuid": identity, **payload}), **values)
