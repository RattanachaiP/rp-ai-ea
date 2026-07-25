"""Immutable, independently validated PR185 advisory Recommendation artifacts."""

from dataclasses import dataclass
from collections.abc import Mapping
from learning.pattern_memory.models import valid_digest, valid_timestamp, valid_uuid
from learning.decision_intelligence.models import INTELLIGENCE_STATES
from learning.decision_intelligence.policy import DecisionIntelligencePolicy
from .identity import digest, recommendation_uuid, report_uuid, snapshot_uuid

AUTHORITY_SCOPE = "ADVISORY_DECISION_RECOMMENDATION_ONLY"
RECOMMENDATION_STATES = (
    "REJECTED",
    "INSUFFICIENT_RECOMMENDATION_EVIDENCE",
    "RECOMMENDATION_READY",
    "RECOMMENDATION_MANUAL_REVIEW",
    "RECOMMENDATION_NOT_READY",
)
RECOMMENDATION_CLASSIFICATIONS = (
    "READY_FOR_DECISION",
    "NOT_READY",
    "INSUFFICIENT_EVIDENCE",
    "MANUAL_REVIEW",
    "REJECTED",
)


def _version(v):
    return isinstance(v, str) and bool(v) and v == v.strip()


@dataclass(frozen=True)
class DecisionRecommendation:
    recommendation_uuid: str
    recommendation_digest: str
    decision_intelligence_uuid: str
    decision_intelligence_digest: str
    intelligence_state: str
    recommendation_state: str
    recommendation_classification: str
    recommendation_reason: str
    decision_intelligence_snapshot_uuid: str
    decision_intelligence_snapshot_digest: str
    decision_intelligence_repository_digest: str
    recommendation_policy_uuid: str
    recommendation_policy_digest: str
    recommendation_policy_version: str
    recommendation_engine_version: str
    created_at: str
    authority_scope: str = AUTHORITY_SCOPE
    advisory_only: bool = True

    def __post_init__(self):
        allowed = {
            "REJECTED": {("REJECTED", "DECISION_INTELLIGENCE_REJECTED")},
            "INSUFFICIENT_DECISION_INTELLIGENCE": {
                (
                    "INSUFFICIENT_RECOMMENDATION_EVIDENCE",
                    "DECISION_INTELLIGENCE_EVIDENCE_INSUFFICIENT",
                )
            },
            "DECISION_INTELLIGENCE_READY": {
                ("RECOMMENDATION_READY", "READY_THRESHOLD_MET"),
                ("RECOMMENDATION_MANUAL_REVIEW", "MANUAL_REVIEW_THRESHOLD_MET"),
                ("RECOMMENDATION_NOT_READY", "READY_THRESHOLD_NOT_MET"),
            },
        }
        expected_class = {
            "DECISION_INTELLIGENCE_REJECTED": "REJECTED",
            "DECISION_INTELLIGENCE_EVIDENCE_INSUFFICIENT": "INSUFFICIENT_EVIDENCE",
            "READY_THRESHOLD_MET": "READY_FOR_DECISION",
            "MANUAL_REVIEW_THRESHOLD_MET": "MANUAL_REVIEW",
            "READY_THRESHOLD_NOT_MET": "NOT_READY",
        }
        if (
            not all(
                valid_uuid(x)
                for x in (
                    self.recommendation_uuid,
                    self.decision_intelligence_uuid,
                    self.decision_intelligence_snapshot_uuid,
                    self.recommendation_policy_uuid,
                )
            )
            or not all(
                valid_digest(x)
                for x in (
                    self.recommendation_digest,
                    self.decision_intelligence_digest,
                    self.decision_intelligence_snapshot_digest,
                    self.decision_intelligence_repository_digest,
                    self.recommendation_policy_digest,
                )
            )
            or self.intelligence_state not in INTELLIGENCE_STATES
            or (self.recommendation_state, self.recommendation_reason)
            not in allowed.get(self.intelligence_state, set())
            or self.recommendation_classification not in RECOMMENDATION_CLASSIFICATIONS
            or expected_class.get(self.recommendation_reason)
            != self.recommendation_classification
            or self.recommendation_policy_version != "PR185-RECOMMENDATION-POLICY.1.0"
            or self.recommendation_engine_version != "PR185.1.0"
            or not valid_timestamp(self.created_at)
            or self.authority_scope != AUTHORITY_SCOPE
            or self.advisory_only is not True
            or recommendation_uuid(self.identity_payload()) != self.recommendation_uuid
            or digest(self.digest_payload()) != self.recommendation_digest
        ):
            raise ValueError("INVALID_DECISION_RECOMMENDATION")

    def identity_payload(self):
        return {
            n: getattr(self, n)
            for n in self.__dataclass_fields__
            if n not in {"recommendation_uuid", "recommendation_digest"}
        }

    def digest_payload(self):
        return {
            "recommendation_uuid": self.recommendation_uuid,
            **self.identity_payload(),
        }

    def to_dict(self):
        return self.digest_payload() | {
            "recommendation_digest": self.recommendation_digest
        }

    @classmethod
    def create(cls, **v):
        uid = recommendation_uuid(v)
        return cls(
            recommendation_uuid=uid,
            recommendation_digest=digest({"recommendation_uuid": uid, **v}),
            **v,
        )


@dataclass(frozen=True)
class DecisionRecommendationSnapshot:
    snapshot_uuid: str
    snapshot_digest: str
    recommendation_identities: tuple[tuple[str, str], ...]
    record_count: int
    repository_digest: str
    previous_snapshot_uuid: str | None
    previous_snapshot_digest: str | None
    generated_at: str
    recommendation_policy_uuid: str
    recommendation_policy_digest: str
    recommendation_policy_version: str
    recommendation_engine_version: str
    intelligence_policy_uuid: str
    intelligence_policy_digest: str
    intelligence_policy_version: str
    intelligence_engine_version: str
    authority_scope: str = AUTHORITY_SCOPE
    advisory_only: bool = True

    def __post_init__(self):
        intelligence_policy = DecisionIntelligencePolicy()
        ids = tuple(tuple(x) for x in self.recommendation_identities)
        object.__setattr__(self, "recommendation_identities", ids)
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
                    self.recommendation_policy_uuid,
                    self.intelligence_policy_uuid,
                )
            )
            or not all(
                valid_digest(x)
                for x in (
                    self.snapshot_digest,
                    self.repository_digest,
                    self.recommendation_policy_digest,
                    self.intelligence_policy_digest,
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
                    self.recommendation_policy_version,
                    self.recommendation_engine_version,
                    self.intelligence_policy_version,
                    self.intelligence_engine_version,
                )
            )
            or self.recommendation_policy_version != "PR185-RECOMMENDATION-POLICY.1.0"
            or self.recommendation_engine_version != "PR185.1.0"
            or self.intelligence_policy_version != "PR184-INTELLIGENCE-POLICY.1.0"
            or self.intelligence_engine_version != "PR184.1.0"
            or self.intelligence_policy_uuid
            != intelligence_policy.intelligence_policy_uuid
            or self.intelligence_policy_digest
            != intelligence_policy.intelligence_policy_digest
            or not valid_timestamp(self.generated_at)
            or self.authority_scope != AUTHORITY_SCOPE
            or self.advisory_only is not True
            or snapshot_uuid(self.identity_payload()) != self.snapshot_uuid
            or digest(self.identity_payload()) != self.snapshot_digest
        ):
            raise ValueError("INVALID_RECOMMENDATION_SNAPSHOT")

    def identity_payload(self):
        return {
            n: (
                [list(x) for x in self.recommendation_identities]
                if n == "recommendation_identities"
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
        v["recommendation_identities"] = tuple(v["recommendation_identities"])
        p = {
            **v,
            "recommendation_identities": [
                list(x) for x in v["recommendation_identities"]
            ],
        }
        uid = snapshot_uuid(p)
        return cls(snapshot_uuid=uid, snapshot_digest=digest(p), **v)


@dataclass(frozen=True)
class DecisionRecommendationReport:
    report_uuid: str
    report_digest: str
    recommendations: tuple[DecisionRecommendation, ...]
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
            DecisionRecommendation(**x) if isinstance(x, Mapping) else x
            for x in self.recommendations
        )
        object.__setattr__(self, "recommendations", items)
        evaluated_states = {
            "RECOMMENDATION_READY",
            "RECOMMENDATION_MANUAL_REVIEW",
            "RECOMMENDATION_NOT_READY",
        }
        if (
            not all(type(x) is DecisionRecommendation for x in items)
            or self.processed_count != len(items)
            or self.ready_count
            != sum(x.recommendation_state in evaluated_states for x in items)
            or self.insufficient_count
            != sum(
                x.recommendation_state == "INSUFFICIENT_RECOMMENDATION_EVIDENCE"
                for x in items
            )
            or self.rejected_count
            != sum(x.recommendation_state == "REJECTED" for x in items)
            or len({x.recommendation_uuid for x in items}) != len(items)
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
            raise ValueError("INVALID_RECOMMENDATION_REPORT")

    def identity_payload(self):
        return {
            n: (
                [x.to_dict() for x in self.recommendations]
                if n == "recommendations"
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
        v["recommendations"] = tuple(v["recommendations"])
        p = {**v, "recommendations": [x.to_dict() for x in v["recommendations"]]}
        uid = report_uuid(p)
        return cls(
            report_uuid=uid, report_digest=digest({"report_uuid": uid, **p}), **v
        )
