"""Immutable, independently auditable PR181 advisory eligibility artifacts."""

from dataclasses import dataclass

from learning.pattern_memory.models import valid_digest, valid_timestamp, valid_uuid

from .identity import digest, report_uuid, selection_uuid, snapshot_uuid

ELIGIBLE = "ELIGIBLE_FOR_CONFIDENCE_EVALUATION"
SELECTION_SCOPE = "ADVISORY_ELIGIBILITY_ONLY"
SELECTION_STATES = ("REJECTED", "INSUFFICIENT_SELECTION_EVIDENCE", ELIGIBLE)
REASON_ORDER = (
    "RUNTIME_PACKAGE_STATE_NOT_ELIGIBLE",
    "REGISTRY_STATE_NOT_ELIGIBLE",
    "VALIDATION_STATE_INSUFFICIENT",
    "PROMOTION_STATE_INSUFFICIENT",
    "ELIGIBLE_FOR_PR182_CONFIDENCE_EVALUATION",
)
SOURCE_ARTIFACT_TYPES = (
    "RUNTIME_KNOWLEDGE_PACKAGE",
    "RUNTIME_KNOWLEDGE_SNAPSHOT",
    "RUNTIME_KNOWLEDGE_PACKAGING_REPORT",
)

POLICY_PARTITION_FIELDS = (
    "selector_version",
    "selection_policy_uuid",
    "selection_policy_digest",
    "selection_policy_version",
)
UPSTREAM_PARTITION_FIELDS = (
    "source_runtime_engine_version",
    "source_runtime_packaging_policy_uuid",
    "source_runtime_packaging_policy_digest",
    "source_runtime_packaging_policy_version",
    "source_registry_engine_version",
    "source_registry_admission_policy_uuid",
    "source_registry_admission_policy_digest",
    "source_registry_admission_policy_version",
    "source_promotion_engine_version",
    "source_promotion_policy_uuid",
    "source_promotion_policy_digest",
    "source_promotion_policy_version",
)
PARTITION_FIELDS = POLICY_PARTITION_FIELDS + UPSTREAM_PARTITION_FIELDS


def _text(value):
    return isinstance(value, str) and bool(value)


def _valid_reasons(value):
    return (
        isinstance(value, tuple)
        and bool(value)
        and all(_text(item) for item in value)
        and len(set(value)) == len(value)
    )


@dataclass(frozen=True)
class RuntimeKnowledgeSelection:
    selection_uuid: str
    selection_digest: str
    source_runtime_package_uuid: str
    source_runtime_package_digest: str
    source_runtime_snapshot_uuid: str
    source_runtime_snapshot_digest: str
    source_runtime_repository_digest: str
    source_runtime_engine_version: str
    source_runtime_packaging_policy_uuid: str
    source_runtime_packaging_policy_digest: str
    source_runtime_packaging_policy_version: str
    source_registry_engine_version: str
    source_registry_admission_policy_uuid: str
    source_registry_admission_policy_digest: str
    source_registry_admission_policy_version: str
    source_promotion_engine_version: str
    source_promotion_policy_uuid: str
    source_promotion_policy_digest: str
    source_promotion_policy_version: str
    source_registry_uuid: str
    source_registry_digest: str
    source_promotion_uuid: str
    source_promotion_digest: str
    source_validation_uuid: str
    source_validation_digest: str
    source_memory_uuid: str
    source_memory_digest: str
    source_pattern_uuid: str
    source_pattern_hash: str
    knowledge_uuid: str
    knowledge_version: str
    source_runtime_package_state: str
    source_runtime_package_reasons: tuple[str, ...]
    source_registry_state: str
    source_registry_reasons: tuple[str, ...]
    source_validation_state: str
    source_validation_reasons: tuple[str, ...]
    source_promotion_state: str
    source_promotion_reasons: tuple[str, ...]
    selection_state: str
    selection_reasons: tuple[str, ...]
    selection_scope: str
    selection_policy_uuid: str
    selection_policy_digest: str
    selection_policy_version: str
    selector_version: str
    created_at: str
    advisory_only: bool = True

    def __post_init__(self):
        reason_fields = (
            "source_runtime_package_reasons",
            "source_registry_reasons",
            "source_validation_reasons",
            "source_promotion_reasons",
            "selection_reasons",
        )
        for name in reason_fields:
            object.__setattr__(self, name, tuple(getattr(self, name)))
        uuids = (
            self.selection_uuid,
            self.source_runtime_package_uuid,
            self.source_runtime_snapshot_uuid,
            self.source_runtime_packaging_policy_uuid,
            self.source_registry_admission_policy_uuid,
            self.source_promotion_policy_uuid,
            self.source_registry_uuid,
            self.source_promotion_uuid,
            self.source_validation_uuid,
            self.source_memory_uuid,
            self.source_pattern_uuid,
            self.knowledge_uuid,
            self.selection_policy_uuid,
        )
        digests = (
            self.selection_digest,
            self.source_runtime_package_digest,
            self.source_runtime_snapshot_digest,
            self.source_runtime_repository_digest,
            self.source_runtime_packaging_policy_digest,
            self.source_registry_admission_policy_digest,
            self.source_promotion_policy_digest,
            self.source_registry_digest,
            self.source_promotion_digest,
            self.source_validation_digest,
            self.source_memory_digest,
            self.source_pattern_hash,
            self.selection_policy_digest,
        )
        text_fields = (
            self.source_runtime_engine_version,
            self.source_runtime_packaging_policy_version,
            self.source_registry_engine_version,
            self.source_registry_admission_policy_version,
            self.source_promotion_engine_version,
            self.source_promotion_policy_version,
            self.knowledge_version,
            self.source_runtime_package_state,
            self.source_registry_state,
            self.source_validation_state,
            self.source_promotion_state,
            self.selection_policy_version,
            self.selector_version,
        )
        expected_reasons = self.expected_selection_reasons()
        if (
            not all(valid_uuid(value) for value in uuids)
            or not all(valid_digest(value) for value in digests)
            or not all(_text(value) for value in text_fields)
            or not all(_valid_reasons(getattr(self, name)) for name in reason_fields)
            or self.selection_state not in SELECTION_STATES
            or self.selection_reasons != expected_reasons
            or self.selection_scope != SELECTION_SCOPE
            or not valid_timestamp(self.created_at)
            or self.advisory_only is not True
            or selection_uuid(self.identity_payload()) != self.selection_uuid
            or digest(self.digest_payload()) != self.selection_digest
        ):
            raise ValueError("INVALID_RUNTIME_KNOWLEDGE_SELECTION")

    def expected_selection_reasons(self):
        hard = []
        insufficient = []
        if self.source_runtime_package_state != "ADVISORY_PACKAGE_PREPARED":
            hard.append("RUNTIME_PACKAGE_STATE_NOT_ELIGIBLE")
        if self.source_registry_state != "ADVISORY_ENTRY_RECORDED":
            hard.append("REGISTRY_STATE_NOT_ELIGIBLE")
        if self.source_validation_state != "STATISTICALLY_CONSISTENT":
            insufficient.append("VALIDATION_STATE_INSUFFICIENT")
        if self.source_promotion_state != "POLICY_CRITERIA_MET":
            insufficient.append("PROMOTION_STATE_INSUFFICIENT")
        if hard:
            expected_state, reasons = "REJECTED", tuple(hard)
        elif insufficient:
            expected_state, reasons = "INSUFFICIENT_SELECTION_EVIDENCE", tuple(
                insufficient
            )
        else:
            expected_state = ELIGIBLE
            reasons = ("ELIGIBLE_FOR_PR182_CONFIDENCE_EVALUATION",)
        return reasons if self.selection_state == expected_state else ()

    def identity_payload(self):
        return {
            name: getattr(self, name)
            for name in self.__dataclass_fields__
            if name not in {"selection_uuid", "selection_digest"}
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
        values = dict(values)
        for name in (
            "source_runtime_package_reasons",
            "source_registry_reasons",
            "source_validation_reasons",
            "source_promotion_reasons",
            "selection_reasons",
        ):
            values[name] = tuple(values[name])
        identity = selection_uuid(values)
        return cls(
            selection_uuid=identity,
            selection_digest=digest({"selection_uuid": identity, **values}),
            **values,
        )


@dataclass(frozen=True)
class RuntimeKnowledgeSelectionSnapshot:
    snapshot_uuid: str
    snapshot_digest: str
    selector_version: str
    selection_policy_uuid: str
    selection_policy_digest: str
    selection_policy_version: str
    source_runtime_engine_version: str
    source_runtime_packaging_policy_uuid: str
    source_runtime_packaging_policy_digest: str
    source_runtime_packaging_policy_version: str
    source_registry_engine_version: str
    source_registry_admission_policy_uuid: str
    source_registry_admission_policy_digest: str
    source_registry_admission_policy_version: str
    source_promotion_engine_version: str
    source_promotion_policy_uuid: str
    source_promotion_policy_digest: str
    source_promotion_policy_version: str
    source_runtime_snapshot_uuid: str
    source_runtime_snapshot_digest: str
    source_runtime_repository_digest: str
    selection_identities: tuple[tuple[str, str], ...]
    selection_count: int
    repository_digest: str
    previous_snapshot_uuid: str | None
    previous_snapshot_digest: str | None
    generated_at: str
    advisory_only: bool = True

    def __post_init__(self):
        identities = tuple(tuple(item) for item in self.selection_identities)
        object.__setattr__(self, "selection_identities", identities)
        previous = (
            self.previous_snapshot_uuid is None
            and self.previous_snapshot_digest is None
        ) or (
            valid_uuid(self.previous_snapshot_uuid)
            and valid_digest(self.previous_snapshot_digest)
        )
        uuid_fields = (
            "snapshot_uuid",
            "selection_policy_uuid",
            "source_runtime_packaging_policy_uuid",
            "source_registry_admission_policy_uuid",
            "source_promotion_policy_uuid",
            "source_runtime_snapshot_uuid",
        )
        digest_fields = (
            "snapshot_digest",
            "selection_policy_digest",
            "source_runtime_packaging_policy_digest",
            "source_registry_admission_policy_digest",
            "source_promotion_policy_digest",
            "source_runtime_snapshot_digest",
            "source_runtime_repository_digest",
            "repository_digest",
        )
        if (
            not all(valid_uuid(getattr(self, name)) for name in uuid_fields)
            or not all(valid_digest(getattr(self, name)) for name in digest_fields)
            or not all(
                _text(getattr(self, name))
                for name in PARTITION_FIELDS
                if name.endswith("version")
            )
            or identities != tuple(sorted(identities))
            or self.selection_count != len(identities)
            or len({item[0] for item in identities}) != len(identities)
            or not all(
                len(item) == 2 and valid_uuid(item[0]) and valid_digest(item[1])
                for item in identities
            )
            or not previous
            or not valid_timestamp(self.generated_at)
            or self.advisory_only is not True
            or snapshot_uuid(self.identity_payload()) != self.snapshot_uuid
            or digest(self.identity_payload()) != self.snapshot_digest
        ):
            raise ValueError("INVALID_RUNTIME_KNOWLEDGE_SELECTION_SNAPSHOT")

    def identity_payload(self):
        return {
            name: (
                [list(item) for item in self.selection_identities]
                if name == "selection_identities"
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
        values["selection_identities"] = tuple(
            sorted(tuple(item) for item in values["selection_identities"])
        )
        payload = {
            **values,
            "selection_identities": [
                list(item) for item in values["selection_identities"]
            ],
        }
        return cls(
            snapshot_uuid=snapshot_uuid(payload),
            snapshot_digest=digest(payload),
            **values,
        )


@dataclass(frozen=True)
class RuntimeKnowledgeSelectionReport:
    report_uuid: str
    report_digest: str
    source_artifact_type: str
    source_runtime_package_uuid: str | None
    source_runtime_package_digest: str | None
    source_runtime_packaging_report_uuid: str | None
    source_runtime_packaging_report_digest: str | None
    source_runtime_snapshot_uuid: str
    source_runtime_snapshot_digest: str
    source_runtime_repository_digest: str
    selector_version: str
    selection_policy_uuid: str
    selection_policy_digest: str
    selection_policy_version: str
    source_runtime_engine_version: str
    source_runtime_packaging_policy_uuid: str
    source_runtime_packaging_policy_digest: str
    source_runtime_packaging_policy_version: str
    source_registry_engine_version: str
    source_registry_admission_policy_uuid: str
    source_registry_admission_policy_digest: str
    source_registry_admission_policy_version: str
    source_promotion_engine_version: str
    source_promotion_policy_uuid: str
    source_promotion_policy_digest: str
    source_promotion_policy_version: str
    runtime_selections: tuple[RuntimeKnowledgeSelection, ...]
    processed_package_count: int
    new_selection_count: int
    duplicate_selection_count: int
    eligible_count: int
    insufficient_selection_evidence_count: int
    rejected_count: int
    repository_digest: str
    selection_snapshot_uuid: str
    selection_snapshot_digest: str
    generated_at: str
    advisory_only: bool = True

    def __post_init__(self):
        selections = tuple(self.runtime_selections)
        object.__setattr__(self, "runtime_selections", selections)
        package_form = (
            self.source_artifact_type == SOURCE_ARTIFACT_TYPES[0]
            and valid_uuid(self.source_runtime_package_uuid)
            and valid_digest(self.source_runtime_package_digest)
            and self.source_runtime_packaging_report_uuid is None
            and self.source_runtime_packaging_report_digest is None
        )
        snapshot_form = (
            self.source_artifact_type == SOURCE_ARTIFACT_TYPES[1]
            and self.source_runtime_package_uuid is None
            and self.source_runtime_package_digest is None
            and self.source_runtime_packaging_report_uuid is None
            and self.source_runtime_packaging_report_digest is None
        )
        report_form = (
            self.source_artifact_type == SOURCE_ARTIFACT_TYPES[2]
            and self.source_runtime_package_uuid is None
            and self.source_runtime_package_digest is None
            and valid_uuid(self.source_runtime_packaging_report_uuid)
            and valid_digest(self.source_runtime_packaging_report_digest)
        )
        counts = (
            self.processed_package_count,
            self.new_selection_count,
            self.duplicate_selection_count,
            self.eligible_count,
            self.insufficient_selection_evidence_count,
            self.rejected_count,
        )
        partition = tuple(getattr(self, name) for name in PARTITION_FIELDS)
        if (
            not valid_uuid(self.report_uuid)
            or not valid_digest(self.report_digest)
            or sum((bool(package_form), bool(snapshot_form), bool(report_form))) != 1
            or not all(
                valid_uuid(getattr(self, name))
                for name in (
                    "source_runtime_snapshot_uuid",
                    "selection_policy_uuid",
                    "source_runtime_packaging_policy_uuid",
                    "source_registry_admission_policy_uuid",
                    "source_promotion_policy_uuid",
                    "selection_snapshot_uuid",
                )
            )
            or not all(
                valid_digest(getattr(self, name))
                for name in (
                    "source_runtime_snapshot_digest",
                    "source_runtime_repository_digest",
                    "selection_policy_digest",
                    "source_runtime_packaging_policy_digest",
                    "source_registry_admission_policy_digest",
                    "source_promotion_policy_digest",
                    "repository_digest",
                    "selection_snapshot_digest",
                )
            )
            or not all(type(value) is int and value >= 0 for value in counts)
            or self.new_selection_count + self.duplicate_selection_count
            != self.processed_package_count
            or self.eligible_count
            + self.insufficient_selection_evidence_count
            + self.rejected_count
            != self.processed_package_count
            or self.processed_package_count != len(selections)
            or not all(type(item) is RuntimeKnowledgeSelection for item in selections)
            or any(
                tuple(getattr(item, name) for name in PARTITION_FIELDS) != partition
                for item in selections
            )
            or any(
                item.source_runtime_snapshot_uuid != self.source_runtime_snapshot_uuid
                or item.source_runtime_snapshot_digest
                != self.source_runtime_snapshot_digest
                or item.source_runtime_repository_digest
                != self.source_runtime_repository_digest
                for item in selections
            )
            or self.eligible_count
            != sum(item.selection_state == ELIGIBLE for item in selections)
            or self.insufficient_selection_evidence_count
            != sum(
                item.selection_state == "INSUFFICIENT_SELECTION_EVIDENCE"
                for item in selections
            )
            or self.rejected_count
            != sum(item.selection_state == "REJECTED" for item in selections)
            or not valid_timestamp(self.generated_at)
            or self.advisory_only is not True
            or report_uuid(self.identity_payload()) != self.report_uuid
            or digest(self.digest_payload()) != self.report_digest
        ):
            raise ValueError("INVALID_RUNTIME_KNOWLEDGE_SELECTION_REPORT")

    def identity_payload(self):
        return {
            name: (
                [item.to_dict() for item in self.runtime_selections]
                if name == "runtime_selections"
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
        values["runtime_selections"] = tuple(values["runtime_selections"])
        payload = {
            **values,
            "runtime_selections": [
                item.to_dict() for item in values["runtime_selections"]
            ],
        }
        identity = report_uuid(payload)
        return cls(
            report_uuid=identity,
            report_digest=digest({"report_uuid": identity, **payload}),
            **values,
        )
