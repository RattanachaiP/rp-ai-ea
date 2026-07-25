"""Immutable, independently validated PR184 advisory artifacts."""

from dataclasses import dataclass
from math import isfinite
from collections.abc import Mapping

from learning.pattern_memory.models import valid_digest, valid_timestamp, valid_uuid
from learning.decision_context.models import CONTEXT_STATES

from .identity import intelligence_uuid, digest, report_uuid, snapshot_uuid

AUTHORITY_SCOPE = "ADVISORY_DECISION_INTELLIGENCE_ONLY"
INTELLIGENCE_STATES = ("REJECTED", "INSUFFICIENT_DECISION_INTELLIGENCE", "DECISION_INTELLIGENCE_READY")
EXPECTED_INTELLIGENCE_MAPPING = {
    "CONTEXT_PREPARED": (
        "DECISION_INTELLIGENCE_READY",
        "VERIFIED_DECISION_INTELLIGENCE_CONSTRUCTED",
    ),
    "INSUFFICIENT_CONTEXT_EVIDENCE": (
        "INSUFFICIENT_DECISION_INTELLIGENCE",
        "DECISION_CONTEXT_EVIDENCE_INSUFFICIENT",
    ),
    "REJECTED": ("REJECTED", "DECISION_CONTEXT_REJECTED"),
}
VALID_RECOMMENDATIONS = (
    "RECOMMENDATION_REVIEW_ELIGIBLE",
    "MORE_EVIDENCE_REQUIRED",
    "RECOMMENDATION_REVIEW_REJECTED",
)

def _valid_version(value):
    return isinstance(value, str) and bool(value) and value == value.strip()


@dataclass(frozen=True)
class DecisionIntelligence:
    intelligence_uuid: str
    intelligence_digest: str
    decision_context_uuid: str
    decision_context_digest: str
    context_state: str
    decision_quality: float
    decision_reliability: float
    decision_consistency: float
    decision_recommendation: str
    decision_context_snapshot_uuid: str
    decision_context_snapshot_digest: str
    decision_context_repository_digest: str
    intelligence_state: str
    intelligence_reason: str
    intelligence_policy_uuid: str
    intelligence_policy_digest: str
    intelligence_policy_version: str
    intelligence_engine_version: str
    created_at: str
    authority_scope: str = AUTHORITY_SCOPE
    advisory_only: bool = True

    def __post_init__(self):
        expected_mapping = EXPECTED_INTELLIGENCE_MAPPING.get(self.context_state)
        if (
            not all(
                valid_uuid(item)
                for item in (
                    self.intelligence_uuid,
                    self.decision_context_uuid,
                    self.decision_context_snapshot_uuid,
                    self.intelligence_policy_uuid,
                )
            )
            or not all(
                valid_digest(item)
                for item in (
                    self.intelligence_digest,
                    self.decision_context_digest,
                    self.decision_context_snapshot_digest,
                    self.decision_context_repository_digest,
                    self.intelligence_policy_digest,
                )
            )
            or not all(
                _valid_version(item)
                for item in (self.intelligence_policy_version, self.intelligence_engine_version)
            )
            or self.intelligence_engine_version != "PR184.1.0"
            or self.context_state not in CONTEXT_STATES
            or expected_mapping != (self.intelligence_state, self.intelligence_reason)
            or any(type(value) is not float or not isfinite(value) or not 0.0 <= value <= 1.0 for value in (
                self.decision_quality, self.decision_reliability, self.decision_consistency
            ))
            or self.decision_recommendation not in VALID_RECOMMENDATIONS
            or self.decision_recommendation != {
                "DECISION_INTELLIGENCE_READY": "RECOMMENDATION_REVIEW_ELIGIBLE",
                "INSUFFICIENT_DECISION_INTELLIGENCE": "MORE_EVIDENCE_REQUIRED",
                "REJECTED": "RECOMMENDATION_REVIEW_REJECTED",
            }.get(self.intelligence_state)
            or not valid_timestamp(self.created_at)
            or self.authority_scope != AUTHORITY_SCOPE
            or self.advisory_only is not True
            or intelligence_uuid(self.identity_payload()) != self.intelligence_uuid
            or digest(self.digest_payload()) != self.intelligence_digest
        ):
            raise ValueError("INVALID_DECISION_INTELLIGENCE")

    def identity_payload(self):
        return {
            name: getattr(self, name)
            for name in self.__dataclass_fields__
            if name not in {"intelligence_uuid", "intelligence_digest"}
        }

    def digest_payload(self):
        return {"intelligence_uuid": self.intelligence_uuid, **self.identity_payload()}

    def to_dict(self):
        return {
            "intelligence_uuid": self.intelligence_uuid,
            "intelligence_digest": self.intelligence_digest,
            **self.identity_payload(),
        }

    @classmethod
    def create(cls, **values):
        identity = intelligence_uuid(values)
        return cls(
            intelligence_uuid=identity,
            intelligence_digest=digest({"intelligence_uuid": identity, **values}),
            **values,
        )


@dataclass(frozen=True)
class DecisionIntelligenceSnapshot:
    snapshot_uuid: str
    snapshot_digest: str
    intelligence_identities: tuple[tuple[str, str], ...]
    record_count: int
    repository_digest: str
    previous_snapshot_uuid: str | None
    previous_snapshot_digest: str | None
    generated_at: str
    intelligence_policy_uuid: str
    intelligence_policy_digest: str
    intelligence_policy_version: str
    intelligence_engine_version: str
    context_policy_uuid: str
    context_policy_digest: str
    context_policy_version: str
    context_engine_version: str
    authority_scope: str = AUTHORITY_SCOPE
    advisory_only: bool = True

    def __post_init__(self):
        identities = tuple(tuple(item) for item in self.intelligence_identities)
        object.__setattr__(self, "intelligence_identities", identities)
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
                    self.intelligence_policy_uuid,
                    self.context_policy_uuid,
                )
            )
            or not all(
                valid_digest(item)
                for item in (
                    self.snapshot_digest,
                    self.repository_digest,
                    self.intelligence_policy_digest,
                    self.context_policy_digest,
                )
            )
            or not all(
                _valid_version(item)
                for item in (
                    self.intelligence_policy_version,
                    self.intelligence_engine_version,
                    self.context_policy_version,
                    self.context_engine_version,
                )
            )
            or self.intelligence_engine_version != "PR184.1.0"
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
            raise ValueError("INVALID_INTELLIGENCE_SNAPSHOT")

    def identity_payload(self):
        return {
            name: (
                [list(item) for item in self.intelligence_identities]
                if name == "intelligence_identities"
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
        values["intelligence_identities"] = tuple(values["intelligence_identities"])
        payload = {
            **values,
            "intelligence_identities": [list(item) for item in values["intelligence_identities"]],
        }
        identity = snapshot_uuid(payload)
        return cls(
            snapshot_uuid=identity,
            snapshot_digest=digest(payload),
            **values,
        )


@dataclass(frozen=True)
class DecisionIntelligenceReport:
    report_uuid: str
    report_digest: str
    decision_intelligences: tuple[DecisionIntelligence, ...]
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
        intelligences = tuple(
            DecisionIntelligence(**item) if isinstance(item, Mapping) else item
            for item in self.decision_intelligences
        )
        object.__setattr__(self, "decision_intelligences", intelligences)
        if (
            not all(type(item) is DecisionIntelligence for item in intelligences)
            or self.processed_count != len(intelligences)
            or self.prepared_count
            != sum(item.intelligence_state == "DECISION_INTELLIGENCE_READY" for item in intelligences)
            or self.insufficient_count
            != sum(
                item.intelligence_state == "INSUFFICIENT_DECISION_INTELLIGENCE"
                for item in intelligences
            )
            or self.rejected_count
            != sum(item.intelligence_state == "REJECTED" for item in intelligences)
            or len(
                {(item.intelligence_uuid, item.intelligence_digest) for item in intelligences}
            )
            != len(intelligences)
            or len({item.intelligence_uuid for item in intelligences}) != len(intelligences)
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
            raise ValueError("INVALID_INTELLIGENCE_REPORT")

    def identity_payload(self):
        return {
            name: (
                [item.to_dict() for item in self.decision_intelligences]
                if name == "decision_intelligences"
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
        values["decision_intelligences"] = tuple(values["decision_intelligences"])
        payload = {
            **values,
            "decision_intelligences": [item.to_dict() for item in values["decision_intelligences"]],
        }
        identity = report_uuid(payload)
        return cls(
            report_uuid=identity,
            report_digest=digest({"report_uuid": identity, **payload}),
            **values,
        )
