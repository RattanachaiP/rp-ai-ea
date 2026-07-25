"""Immutable, independently validated PR183 advisory artifacts."""

from dataclasses import dataclass
from math import isfinite
from collections.abc import Mapping

from learning.pattern_memory.models import valid_digest, valid_timestamp, valid_uuid
from learning.runtime_confidence.models import CONFIDENCE_STATES
from learning.runtime_confidence.policy import DEFAULT_BANDS, RuntimeConfidencePolicy

from .identity import context_uuid, digest, report_uuid, snapshot_uuid
from .policy import DecisionContextPolicy

AUTHORITY_SCOPE = "ADVISORY_DECISION_CONTEXT_ONLY"
CONTEXT_STATES = ("REJECTED", "INSUFFICIENT_CONTEXT_EVIDENCE", "CONTEXT_PREPARED")
CANONICAL_MAPPING = {
    "CONFIDENCE_EVALUATED": (
        "CONTEXT_PREPARED",
        "VERIFIED_CONFIDENCE_CONTEXT_PREPARED",
    ),
    "INSUFFICIENT_CONFIDENCE_EVIDENCE": (
        "INSUFFICIENT_CONTEXT_EVIDENCE",
        "CONFIDENCE_EVIDENCE_INSUFFICIENT",
    ),
    "REJECTED": ("REJECTED", "CONFIDENCE_REJECTED"),
}
VALID_CONFIDENCE_BANDS = tuple(name for name, _ in DEFAULT_BANDS)

_CONTEXT_POLICY = DecisionContextPolicy()
_CONFIDENCE_POLICY = RuntimeConfidencePolicy()


def _valid_version(value):
    return isinstance(value, str) and bool(value) and value == value.strip()


def _context_policy_values(value):
    return (
        value.context_policy_uuid,
        value.context_policy_digest,
        value.context_policy_version,
        value.context_engine_version,
    )


def _expected_context_policy_values():
    return (
        _CONTEXT_POLICY.context_policy_uuid,
        _CONTEXT_POLICY.context_policy_digest,
        _CONTEXT_POLICY.context_policy_version,
        _CONTEXT_POLICY.context_engine_version,
    )


def _confidence_policy_values(value):
    return (
        value.confidence_policy_uuid,
        value.confidence_policy_digest,
        value.confidence_policy_version,
        value.confidence_engine_version,
    )


def _expected_confidence_policy_values():
    return (
        _CONFIDENCE_POLICY.confidence_policy_uuid,
        _CONFIDENCE_POLICY.confidence_policy_digest,
        _CONFIDENCE_POLICY.confidence_policy_version,
        _CONFIDENCE_POLICY.confidence_engine_version,
    )


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
        expected_mapping = CANONICAL_MAPPING.get(self.confidence_state)
        if (
            not all(
                valid_uuid(item)
                for item in (
                    self.context_uuid,
                    self.confidence_uuid,
                    self.confidence_snapshot_uuid,
                    self.context_policy_uuid,
                )
            )
            or not all(
                valid_digest(item)
                for item in (
                    self.context_digest,
                    self.confidence_digest,
                    self.confidence_snapshot_digest,
                    self.confidence_repository_digest,
                    self.context_policy_digest,
                )
            )
            or not all(
                _valid_version(item)
                for item in (self.context_policy_version, self.context_engine_version)
            )
            or _context_policy_values(self) != _expected_context_policy_values()
            or self.confidence_state not in CONFIDENCE_STATES
            or expected_mapping != (self.context_state, self.context_reason)
            or self.confidence_band not in VALID_CONFIDENCE_BANDS
            or type(self.confidence_score) is not float
            or not isfinite(self.confidence_score)
            or not 0.0 <= self.confidence_score <= 1.0
            or not valid_timestamp(self.created_at)
            or self.authority_scope != AUTHORITY_SCOPE
            or self.advisory_only is not True
            or context_uuid(self.identity_payload()) != self.context_uuid
            or digest(self.digest_payload()) != self.context_digest
        ):
            raise ValueError("INVALID_DECISION_CONTEXT")

    def identity_payload(self):
        return {
            name: getattr(self, name)
            for name in self.__dataclass_fields__
            if name not in {"context_uuid", "context_digest"}
        }

    def digest_payload(self):
        return {"context_uuid": self.context_uuid, **self.identity_payload()}

    def to_dict(self):
        return {
            "context_uuid": self.context_uuid,
            "context_digest": self.context_digest,
            **self.identity_payload(),
        }

    @classmethod
    def create(cls, **values):
        identity = context_uuid(values)
        return cls(
            context_uuid=identity,
            context_digest=digest({"context_uuid": identity, **values}),
            **values,
        )


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
        identities = tuple(tuple(item) for item in self.context_identities)
        object.__setattr__(self, "context_identities", identities)
        previous_valid = (
            self.previous_snapshot_uuid is None
            and self.previous_snapshot_digest is None
        ) or (
            valid_uuid(self.previous_snapshot_uuid)
            and valid_digest(self.previous_snapshot_digest)
        )
        if (
            not all(
                valid_uuid(item)
                for item in (
                    self.snapshot_uuid,
                    self.context_policy_uuid,
                    self.confidence_policy_uuid,
                )
            )
            or not all(
                valid_digest(item)
                for item in (
                    self.snapshot_digest,
                    self.repository_digest,
                    self.context_policy_digest,
                    self.confidence_policy_digest,
                )
            )
            or not all(
                _valid_version(item)
                for item in (
                    self.context_policy_version,
                    self.context_engine_version,
                    self.confidence_policy_version,
                    self.confidence_engine_version,
                )
            )
            or _context_policy_values(self) != _expected_context_policy_values()
            or _confidence_policy_values(self) != _expected_confidence_policy_values()
            or identities != tuple(sorted(identities))
            or self.record_count != len(identities)
            or len({item[0] for item in identities}) != len(identities)
            or not all(
                valid_uuid(item[0]) and valid_digest(item[1]) for item in identities
            )
            or not previous_valid
            or not valid_timestamp(self.generated_at)
            or self.authority_scope != AUTHORITY_SCOPE
            or self.advisory_only is not True
            or snapshot_uuid(self.identity_payload()) != self.snapshot_uuid
            or digest(self.identity_payload()) != self.snapshot_digest
        ):
            raise ValueError("INVALID_CONTEXT_SNAPSHOT")

    def identity_payload(self):
        return {
            name: (
                [list(item) for item in self.context_identities]
                if name == "context_identities"
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
        values["context_identities"] = tuple(values["context_identities"])
        payload = {
            **values,
            "context_identities": [list(item) for item in values["context_identities"]],
        }
        identity = snapshot_uuid(payload)
        return cls(
            snapshot_uuid=identity,
            snapshot_digest=digest(payload),
            **values,
        )


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
        contexts = tuple(
            DecisionContext(**item) if isinstance(item, Mapping) else item
            for item in self.decision_contexts
        )
        object.__setattr__(self, "decision_contexts", contexts)
        if (
            not all(type(item) is DecisionContext for item in contexts)
            or self.processed_count != len(contexts)
            or self.prepared_count
            != sum(item.context_state == "CONTEXT_PREPARED" for item in contexts)
            or self.insufficient_count
            != sum(
                item.context_state == "INSUFFICIENT_CONTEXT_EVIDENCE"
                for item in contexts
            )
            or self.rejected_count
            != sum(item.context_state == "REJECTED" for item in contexts)
            or type(self.duplicate_count) is not int
            or not 0 <= self.duplicate_count <= self.processed_count
            or not all(
                valid_digest(item)
                for item in (
                    self.report_digest,
                    self.repository_digest,
                    self.snapshot_digest,
                )
            )
            or not valid_uuid(self.report_uuid)
            or not valid_uuid(self.snapshot_uuid)
            or not valid_timestamp(self.generated_at)
            or self.advisory_only is not True
            or report_uuid(self.identity_payload()) != self.report_uuid
            or digest(self.digest_payload()) != self.report_digest
        ):
            raise ValueError("INVALID_CONTEXT_REPORT")

    def identity_payload(self):
        return {
            name: (
                [item.to_dict() for item in self.decision_contexts]
                if name == "decision_contexts"
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
        values["decision_contexts"] = tuple(values["decision_contexts"])
        payload = {
            **values,
            "decision_contexts": [item.to_dict() for item in values["decision_contexts"]],
        }
        identity = report_uuid(payload)
        return cls(
            report_uuid=identity,
            report_digest=digest({"report_uuid": identity, **payload}),
            **values,
        )
