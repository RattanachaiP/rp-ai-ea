"""Governed construction of advisory PR185 Recommendations; never a trading decision."""

from learning.decision_intelligence import (
    DecisionIntelligence,
    DecisionIntelligenceSnapshot,
    DecisionIntelligenceReport,
    DecisionIntelligenceRepository,
)
from learning.decision_intelligence.identity import (
    digest as intelligence_digest,
    report_uuid as intelligence_report_uuid,
)
from learning.decision_intelligence.exceptions import DecisionIntelligenceError
from learning.pattern_memory.models import valid_digest, valid_uuid
from .exceptions import DecisionRecommendationError
from .models import (
    AUTHORITY_SCOPE,
    DecisionRecommendation,
    DecisionRecommendationReport,
    DecisionRecommendationSnapshot,
)
from .policy import DecisionRecommendationPolicy
from .repository import DecisionRecommendationRepository


class GovernedDecisionRecommendationEngine:
    def __init__(self, intelligence_repository=None, repository=None, policy=None):
        self.intelligence_repository = (
            intelligence_repository or DecisionIntelligenceRepository()
        )
        self.repository = repository or DecisionRecommendationRepository()
        self.policy = policy or DecisionRecommendationPolicy()
        if type(self.intelligence_repository) is not DecisionIntelligenceRepository:
            raise DecisionRecommendationError("INVALID_DECISION_INTELLIGENCE")
        if type(self.repository) is not DecisionRecommendationRepository:
            raise DecisionRecommendationError("REPOSITORY_MISMATCH")
        if type(self.policy) is not DecisionRecommendationPolicy:
            raise DecisionRecommendationError("POLICY_MISMATCH")

    def construct_recommendation(self, source):
        if type(source) not in (
            DecisionIntelligence,
            DecisionIntelligenceReport,
            DecisionIntelligenceSnapshot,
        ):
            raise DecisionRecommendationError("INVALID_DECISION_INTELLIGENCE")
        records, snapshot, generated_at = self._verify(source)
        self._verify_partition(records, snapshot)
        existing = {x.recommendation_uuid: x for x in self.repository.records()}
        output = []
        duplicates = 0
        for stored in existing.values():
            if (
                stored.recommendation_policy_uuid,
                stored.recommendation_policy_digest,
                stored.recommendation_policy_version,
                stored.recommendation_engine_version,
            ) != (
                self.policy.recommendation_policy_uuid,
                self.policy.recommendation_policy_digest,
                self.policy.recommendation_policy_version,
                self.policy.recommendation_engine_version,
            ):
                raise DecisionRecommendationError("POLICY_MISMATCH")
        for intel in sorted(records, key=lambda x: x.intelligence_uuid):
            state, classification, reason = self._classify(intel)
            item = DecisionRecommendation.create(
                decision_intelligence_uuid=intel.intelligence_uuid,
                decision_intelligence_digest=intel.intelligence_digest,
                intelligence_state=intel.intelligence_state,
                recommendation_state=state,
                recommendation_classification=classification,
                recommendation_reason=reason,
                decision_intelligence_snapshot_uuid=snapshot.snapshot_uuid,
                decision_intelligence_snapshot_digest=snapshot.snapshot_digest,
                decision_intelligence_repository_digest=snapshot.repository_digest,
                recommendation_policy_uuid=self.policy.recommendation_policy_uuid,
                recommendation_policy_digest=self.policy.recommendation_policy_digest,
                recommendation_policy_version=self.policy.recommendation_policy_version,
                recommendation_engine_version=self.policy.recommendation_engine_version,
                created_at=intel.created_at,
                authority_scope=AUTHORITY_SCOPE,
                advisory_only=True,
            )
            prior = existing.get(item.recommendation_uuid)
            if prior is not None:
                if prior != item:
                    raise DecisionRecommendationError("REPLAY_COLLISION")
                item = prior
                duplicates += 1
            else:
                self.repository.save(item)
                existing[item.recommendation_uuid] = item
            output.append(item)
        ids = self.repository.identities()
        repo_digest = self.repository.digest()
        previous = self.repository.latest_snapshot()
        values = dict(
            recommendation_identities=ids,
            record_count=len(ids),
            repository_digest=repo_digest,
            recommendation_policy_uuid=self.policy.recommendation_policy_uuid,
            recommendation_policy_digest=self.policy.recommendation_policy_digest,
            recommendation_policy_version=self.policy.recommendation_policy_version,
            recommendation_engine_version=self.policy.recommendation_engine_version,
            intelligence_policy_uuid=snapshot.intelligence_policy_uuid,
            intelligence_policy_digest=snapshot.intelligence_policy_digest,
            intelligence_policy_version=snapshot.intelligence_policy_version,
            intelligence_engine_version=snapshot.intelligence_engine_version,
            authority_scope=AUTHORITY_SCOPE,
            advisory_only=True,
        )
        if previous and all(getattr(previous, k) == v for k, v in values.items()):
            out_snapshot = previous
        else:
            out_snapshot = DecisionRecommendationSnapshot.create(
                **values,
                previous_snapshot_uuid=previous.snapshot_uuid if previous else None,
                previous_snapshot_digest=previous.snapshot_digest if previous else None,
                generated_at=generated_at,
            )
            self.repository.save_snapshot(out_snapshot)
        return DecisionRecommendationReport.create(
            recommendations=tuple(output),
            processed_count=len(output),
            ready_count=sum(
                x.recommendation_state
                in {
                    "RECOMMENDATION_READY",
                    "RECOMMENDATION_MANUAL_REVIEW",
                    "RECOMMENDATION_NOT_READY",
                }
                for x in output
            ),
            insufficient_count=sum(
                x.recommendation_state == "INSUFFICIENT_RECOMMENDATION_EVIDENCE"
                for x in output
            ),
            rejected_count=sum(x.recommendation_state == "REJECTED" for x in output),
            duplicate_count=duplicates,
            repository_digest=repo_digest,
            snapshot_uuid=out_snapshot.snapshot_uuid,
            snapshot_digest=out_snapshot.snapshot_digest,
            generated_at=generated_at,
            advisory_only=True,
        )

    recommend = construct_recommendation
    run = construct_recommendation

    def _classify(self, intelligence):
        if intelligence.intelligence_state == "REJECTED":
            return "REJECTED", "REJECTED", "DECISION_INTELLIGENCE_REJECTED"
        if (
            intelligence.intelligence_state
            == self.policy.insufficient_intelligence_state
        ):
            return (
                "INSUFFICIENT_RECOMMENDATION_EVIDENCE",
                "INSUFFICIENT_EVIDENCE",
                "DECISION_INTELLIGENCE_EVIDENCE_INSUFFICIENT",
            )
        if (
            intelligence.decision_quality >= self.policy.ready_quality_threshold
            and intelligence.decision_reliability >= self.policy.ready_quality_threshold
        ):
            return "RECOMMENDATION_READY", "READY_FOR_DECISION", "READY_THRESHOLD_MET"
        if intelligence.decision_quality >= self.policy.manual_review_quality_threshold:
            return (
                "RECOMMENDATION_MANUAL_REVIEW",
                "MANUAL_REVIEW",
                "MANUAL_REVIEW_THRESHOLD_MET",
            )
        return "RECOMMENDATION_NOT_READY", "NOT_READY", "READY_THRESHOLD_NOT_MET"

    @staticmethod
    def _verify_partition(records, snapshot):
        if not records:
            raise DecisionRecommendationError("INVALID_DECISION_INTELLIGENCE")
        expected = (
            snapshot.intelligence_policy_uuid,
            snapshot.intelligence_policy_digest,
            snapshot.intelligence_policy_version,
            snapshot.intelligence_engine_version,
        )
        if not valid_uuid(expected[0]) or not valid_digest(expected[1]):
            raise DecisionRecommendationError("POLICY_MISMATCH")
        if any(
            (
                x.intelligence_policy_uuid,
                x.intelligence_policy_digest,
                x.intelligence_policy_version,
                x.intelligence_engine_version,
            )
            != expected
            for x in records
        ):
            raise DecisionRecommendationError("POLICY_MISMATCH")

    def _verify(self, source):
        try:
            records = self.intelligence_repository.records()
            snapshots = self.intelligence_repository.snapshots()
            latest = self.intelligence_repository.latest_snapshot()
        except (DecisionIntelligenceError, ValueError, OSError) as exc:
            raise DecisionRecommendationError("BROKEN_PROVENANCE") from exc
        if latest is None:
            raise DecisionRecommendationError("BROKEN_PROVENANCE")
        by_record = {x.intelligence_uuid: x for x in records}
        by_snapshot = {x.snapshot_uuid: x for x in snapshots}

        def verify(item):
            try:
                valid = (
                    intelligence_digest(item.digest_payload())
                    == item.intelligence_digest
                )
            except Exception:
                valid = False
            if by_record.get(item.intelligence_uuid) != item or not valid:
                raise DecisionRecommendationError("BROKEN_PROVENANCE")

        if type(source) is DecisionIntelligence:
            verify(source)
            if (
                source.intelligence_uuid,
                source.intelligence_digest,
            ) not in latest.intelligence_identities:
                raise DecisionRecommendationError("SNAPSHOT_MISMATCH")
            return (source,), latest, source.created_at
        if type(source) is DecisionIntelligenceSnapshot:
            snapshot = by_snapshot.get(source.snapshot_uuid)
            if snapshot != source:
                raise DecisionRecommendationError("SNAPSHOT_MISMATCH")
            selected = []
            for uid, d in snapshot.intelligence_identities:
                item = by_record.get(uid)
                if item is None or item.intelligence_digest != d:
                    raise DecisionRecommendationError("SNAPSHOT_MISMATCH")
                selected.append(item)
            return tuple(selected), snapshot, source.generated_at
        snapshot = by_snapshot.get(source.snapshot_uuid)
        if snapshot is None or snapshot.snapshot_digest != source.snapshot_digest:
            raise DecisionRecommendationError("SNAPSHOT_MISMATCH")
        if source.repository_digest != snapshot.repository_digest:
            raise DecisionRecommendationError("REPOSITORY_MISMATCH")
        try:
            valid = (
                intelligence_report_uuid(source.identity_payload())
                == source.report_uuid
                and intelligence_digest(source.digest_payload()) == source.report_digest
            )
        except Exception:
            valid = False
        if not valid:
            raise DecisionRecommendationError("BROKEN_PROVENANCE")
        identities = set(snapshot.intelligence_identities)
        for item in source.decision_intelligences:
            verify(item)
            if (item.intelligence_uuid, item.intelligence_digest) not in identities:
                raise DecisionRecommendationError("SNAPSHOT_MISMATCH")
        return source.decision_intelligences, snapshot, source.generated_at


GovernedAdvisoryDecisionRecommendationEngine = GovernedDecisionRecommendationEngine
