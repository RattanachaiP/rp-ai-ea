"""Immutable PR181 selection, snapshot, and report artifacts."""

from dataclasses import dataclass
from learning.pattern_memory.models import valid_digest, valid_timestamp, valid_uuid
from .identity import digest, report_uuid, selection_uuid, snapshot_uuid

SELECTION_STATES = ("REJECTED", "INSUFFICIENT_SELECTION_EVIDENCE", "SELECTED")
SELECTION_REASONS = {
    "REJECTED": "PACKAGE_INELIGIBLE",
    "INSUFFICIENT_SELECTION_EVIDENCE": "GOVERNANCE_EVIDENCE_INSUFFICIENT",
    "SELECTED": "ELIGIBLE_FOR_RUNTIME_CONFIDENCE_EVALUATION",
}


@dataclass(frozen=True)
class RuntimeKnowledgeSelection:
    selection_uuid: str
    selection_digest: str
    runtime_package_uuid: str
    runtime_package_digest: str
    registry_uuid: str
    promotion_uuid: str
    validation_uuid: str
    memory_uuid: str
    pattern_uuid: str
    knowledge_uuid: str
    selection_state: str
    selection_reason: str
    selection_policy_uuid: str
    selection_policy_version: str
    selector_version: str
    created_at: str
    advisory_only: bool = True

    def __post_init__(self):
        uuids = (
            self.selection_uuid,
            self.runtime_package_uuid,
            self.registry_uuid,
            self.promotion_uuid,
            self.validation_uuid,
            self.memory_uuid,
            self.pattern_uuid,
            self.knowledge_uuid,
            self.selection_policy_uuid,
        )
        if (
            not all(valid_uuid(x) for x in uuids)
            or not valid_digest(self.selection_digest)
            or not valid_digest(self.runtime_package_digest)
            or self.selection_state not in SELECTION_STATES
            or self.selection_reason != SELECTION_REASONS[self.selection_state]
            or not self.selection_policy_version
            or not self.selector_version
            or not valid_timestamp(self.created_at)
            or self.advisory_only is not True
            or selection_uuid(self.identity_payload()) != self.selection_uuid
            or digest(self.digest_payload()) != self.selection_digest
        ):
            raise ValueError("INVALID_RUNTIME_KNOWLEDGE_SELECTION")

    def identity_payload(self):
        return {
            n: getattr(self, n)
            for n in self.__dataclass_fields__
            if n not in {"selection_uuid", "selection_digest"}
        }

    def digest_payload(self):
        return {"selection_uuid": self.selection_uuid, **self.identity_payload()}

    def to_dict(self):
        return {
            "selection_uuid": self.selection_uuid,
            "selection_digest": self.selection_digest,
            **self.identity_payload(),
        }

    @classmethod
    def create(cls, **values):
        identity = selection_uuid(values)
        return cls(
            selection_uuid=identity,
            selection_digest=digest({"selection_uuid": identity, **values}),
            **values
        )


@dataclass(frozen=True)
class RuntimeKnowledgeSelectionSnapshot:
    snapshot_uuid: str
    snapshot_digest: str
    selection_policy_uuid: str
    selection_policy_digest: str
    selection_policy_version: str
    selector_version: str
    selection_identities: tuple[tuple[str, str], ...]
    selection_count: int
    repository_digest: str
    previous_snapshot_uuid: str | None
    previous_snapshot_digest: str | None
    generated_at: str
    advisory_only: bool = True

    def __post_init__(self):
        ids = tuple(tuple(x) for x in self.selection_identities)
        object.__setattr__(self, "selection_identities", ids)
        previous = (
            self.previous_snapshot_uuid is None
            and self.previous_snapshot_digest is None
        ) or (
            valid_uuid(self.previous_snapshot_uuid)
            and valid_digest(self.previous_snapshot_digest)
        )
        if (
            not valid_uuid(self.snapshot_uuid)
            or not valid_digest(self.snapshot_digest)
            or not valid_uuid(self.selection_policy_uuid)
            or not valid_digest(self.selection_policy_digest)
            or ids != tuple(sorted(ids))
            or self.selection_count != len(ids)
            or len({x[0] for x in ids}) != len(ids)
            or not all(
                len(x) == 2 and valid_uuid(x[0]) and valid_digest(x[1]) for x in ids
            )
            or not valid_digest(self.repository_digest)
            or not previous
            or not valid_timestamp(self.generated_at)
            or self.advisory_only is not True
            or snapshot_uuid(self.identity_payload()) != self.snapshot_uuid
            or digest(self.identity_payload()) != self.snapshot_digest
        ):
            raise ValueError("INVALID_RUNTIME_KNOWLEDGE_SELECTION_SNAPSHOT")

    def identity_payload(self):
        return {
            n: (
                [list(x) for x in self.selection_identities]
                if n == "selection_identities"
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
    def create(cls, **values):
        values["selection_identities"] = tuple(sorted(values["selection_identities"]))
        payload = {
            **values,
            "selection_identities": [list(x) for x in values["selection_identities"]],
        }
        return cls(
            snapshot_uuid=snapshot_uuid(payload),
            snapshot_digest=digest(payload),
            **values
        )


@dataclass(frozen=True)
class RuntimeKnowledgeSelectionReport:
    report_uuid: str
    processed_package_count: int
    selected_count: int
    duplicate_count: int
    rejected_count: int
    repository_digest: str
    snapshot_uuid: str
    generated_at: str
    advisory_only: bool = True

    def __post_init__(self):
        counts = (
            self.processed_package_count,
            self.selected_count,
            self.duplicate_count,
            self.rejected_count,
        )
        if (
            not valid_uuid(self.report_uuid)
            or any(type(x) is not int or x < 0 for x in counts)
            or self.selected_count + self.rejected_count != self.processed_package_count
            or self.duplicate_count > self.processed_package_count
            or not valid_digest(self.repository_digest)
            or not valid_uuid(self.snapshot_uuid)
            or not valid_timestamp(self.generated_at)
            or self.advisory_only is not True
            or report_uuid(self.identity_payload()) != self.report_uuid
        ):
            raise ValueError("INVALID_RUNTIME_KNOWLEDGE_SELECTION_REPORT")

    def identity_payload(self):
        return {
            n: getattr(self, n) for n in self.__dataclass_fields__ if n != "report_uuid"
        }

    def to_dict(self):
        return {"report_uuid": self.report_uuid, **self.identity_payload()}

    @classmethod
    def create(cls, **values):
        return cls(report_uuid=report_uuid(values), **values)
