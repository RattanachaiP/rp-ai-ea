"""Governed construction of PR186 readiness; never a trading decision."""

from learning.decision_recommendation import (
    DecisionRecommendation,
    DecisionRecommendationSnapshot,
    DecisionRecommendationReport,
    DecisionRecommendationRepository,
)
from learning.decision_recommendation.identity import (
    digest as recommendation_digest,
    report_uuid as recommendation_report_uuid,
)
from learning.decision_recommendation.exceptions import DecisionRecommendationError
from learning.pattern_memory.models import valid_digest, valid_uuid
from .exceptions import ExecutionReadinessError
from .models import (
    AUTHORITY_SCOPE,
    ExecutionReadiness,
    ExecutionReadinessReport,
    ExecutionReadinessSnapshot,
)
from .policy import ExecutionReadinessPolicy
from .repository import ExecutionReadinessRepository


class GovernedExecutionReadinessEngine:
    def __init__(self, recommendation_repository=None, repository=None, policy=None):
        self.recommendation_repository = (
            recommendation_repository or DecisionRecommendationRepository()
        )
        self.repository = repository or ExecutionReadinessRepository()
        self.policy = policy or ExecutionReadinessPolicy()
        if type(self.recommendation_repository) is not DecisionRecommendationRepository:
            raise ExecutionReadinessError("INVALID_RECOMMENDATION")
        if type(self.repository) is not ExecutionReadinessRepository:
            raise ExecutionReadinessError("REPOSITORY_MISMATCH")
        if type(self.policy) is not ExecutionReadinessPolicy:
            raise ExecutionReadinessError("POLICY_MISMATCH")

    def construct_readiness(self, source):
        if type(source) not in (
            DecisionRecommendation,
            DecisionRecommendationReport,
            DecisionRecommendationSnapshot,
        ):
            raise ExecutionReadinessError("INVALID_RECOMMENDATION")
        records, snapshot, generated_at = self._verify(source)
        self._verify_partition(records, snapshot)
        existing = {x.execution_readiness_uuid: x for x in self.repository.records()}
        output = []
        duplicates = 0
        for stored in existing.values():
            if stored.readiness_engine_version != self.policy.readiness_engine_version:
                raise ExecutionReadinessError("ENGINE_VERSION_MISMATCH")
            if (
                stored.readiness_policy_uuid,
                stored.readiness_policy_digest,
                stored.readiness_policy_version,
                stored.readiness_engine_version,
            ) != (
                self.policy.readiness_policy_uuid,
                self.policy.readiness_policy_digest,
                self.policy.readiness_policy_version,
                self.policy.readiness_engine_version,
            ):
                raise ExecutionReadinessError("POLICY_MISMATCH")
        for recommendation in sorted(records, key=lambda x: x.recommendation_uuid):
            state, classification, reason = self._classify(recommendation)
            item = ExecutionReadiness.create(
                recommendation_uuid=recommendation.recommendation_uuid,
                recommendation_digest=recommendation.recommendation_digest,
                recommendation_state=recommendation.recommendation_state,
                readiness_state=state,
                readiness_classification=classification,
                readiness_reason=reason,
                recommendation_snapshot_uuid=snapshot.snapshot_uuid,
                recommendation_snapshot_digest=snapshot.snapshot_digest,
                recommendation_repository_digest=snapshot.repository_digest,
                readiness_policy_uuid=self.policy.readiness_policy_uuid,
                readiness_policy_digest=self.policy.readiness_policy_digest,
                readiness_policy_version=self.policy.readiness_policy_version,
                readiness_engine_version=self.policy.readiness_engine_version,
                created_at=recommendation.created_at,
                authority_scope=AUTHORITY_SCOPE,
                advisory_only=True,
            )
            prior = existing.get(item.execution_readiness_uuid)
            if prior is not None:
                if prior != item:
                    raise ExecutionReadinessError("REPLAY_COLLISION")
                item = prior
                duplicates += 1
            else:
                self.repository.save(item)
                existing[item.execution_readiness_uuid] = item
            output.append(item)
        ids = self.repository.identities()
        repo_digest = self.repository.digest()
        previous = self.repository.latest_snapshot()
        values = dict(
            readiness_identities=ids,
            record_count=len(ids),
            repository_digest=repo_digest,
            readiness_policy_uuid=self.policy.readiness_policy_uuid,
            readiness_policy_digest=self.policy.readiness_policy_digest,
            readiness_policy_version=self.policy.readiness_policy_version,
            readiness_engine_version=self.policy.readiness_engine_version,
            recommendation_policy_uuid=snapshot.recommendation_policy_uuid,
            recommendation_policy_digest=snapshot.recommendation_policy_digest,
            recommendation_policy_version=snapshot.recommendation_policy_version,
            recommendation_engine_version=snapshot.recommendation_engine_version,
            authority_scope=AUTHORITY_SCOPE,
            advisory_only=True,
        )
        if previous and all(getattr(previous, k) == v for k, v in values.items()):
            out_snapshot = previous
        else:
            out_snapshot = ExecutionReadinessSnapshot.create(
                **values,
                previous_snapshot_uuid=previous.snapshot_uuid if previous else None,
                previous_snapshot_digest=previous.snapshot_digest if previous else None,
                generated_at=generated_at,
            )
            self.repository.save_snapshot(out_snapshot)
        return ExecutionReadinessReport.create(
            execution_readiness_records=tuple(output),
            processed_count=len(output),
            ready_count=sum(
                x.readiness_state == "EXECUTION_READY_FOR_ENVIRONMENT_CHECK"
                for x in output
            ),
            insufficient_count=sum(
                x.readiness_state == "INSUFFICIENT_EXECUTION_READINESS"
                for x in output
            ),
            rejected_count=sum(x.readiness_state == "REJECTED" for x in output),
            duplicate_count=duplicates,
            repository_digest=repo_digest,
            snapshot_uuid=out_snapshot.snapshot_uuid,
            snapshot_digest=out_snapshot.snapshot_digest,
            generated_at=generated_at,
            advisory_only=True,
        )

    evaluate_readiness = construct_readiness
    run = construct_readiness

    def _classify(self, recommendation):
        if recommendation.recommendation_state == "REJECTED":
            return "REJECTED", "REJECTED", "RECOMMENDATION_REJECTED"
        if recommendation.recommendation_state == "RECOMMENDATION_READY":
            return (
                "EXECUTION_READY_FOR_ENVIRONMENT_CHECK",
                "READY_FOR_ENVIRONMENT_CHECK",
                "ADVISORY_PIPELINE_COMPLETE",
            )
        reasons = {
            "INSUFFICIENT_RECOMMENDATION_EVIDENCE": "RECOMMENDATION_EVIDENCE_INSUFFICIENT",
            "RECOMMENDATION_MANUAL_REVIEW": "RECOMMENDATION_REQUIRES_MANUAL_REVIEW",
            "RECOMMENDATION_NOT_READY": "RECOMMENDATION_NOT_READY",
        }
        return (
            "INSUFFICIENT_EXECUTION_READINESS",
            "INSUFFICIENT_EXECUTION_READINESS",
            reasons[recommendation.recommendation_state],
        )

    @staticmethod
    def _verify_partition(records, snapshot):
        if not records:
            raise ExecutionReadinessError("INVALID_RECOMMENDATION")
        expected = (
            snapshot.recommendation_policy_uuid,
            snapshot.recommendation_policy_digest,
            snapshot.recommendation_policy_version,
            snapshot.recommendation_engine_version,
        )
        if not valid_uuid(expected[0]) or not valid_digest(expected[1]):
            raise ExecutionReadinessError("POLICY_MISMATCH")
        if any(x.recommendation_engine_version != expected[3] for x in records):
            raise ExecutionReadinessError("ENGINE_VERSION_MISMATCH")
        if any(
            (
                x.recommendation_policy_uuid,
                x.recommendation_policy_digest,
                x.recommendation_policy_version,
                x.recommendation_engine_version,
            )
            != expected
            for x in records
        ):
            raise ExecutionReadinessError("POLICY_MISMATCH")

    def _verify(self, source):
        try:
            records = self.recommendation_repository.records()
            snapshots = self.recommendation_repository.snapshots()
            latest = self.recommendation_repository.latest_snapshot()
        except (DecisionRecommendationError, ValueError, OSError) as exc:
            raise ExecutionReadinessError("BROKEN_PROVENANCE") from exc
        if latest is None:
            raise ExecutionReadinessError("BROKEN_PROVENANCE")
        by_record = {x.recommendation_uuid: x for x in records}
        by_snapshot = {x.snapshot_uuid: x for x in snapshots}

        def verify(item):
            try:
                valid = (
                    recommendation_digest(item.digest_payload())
                    == item.recommendation_digest
                )
            except Exception:
                valid = False
            if by_record.get(item.recommendation_uuid) != item or not valid:
                raise ExecutionReadinessError("BROKEN_PROVENANCE")

        if type(source) is DecisionRecommendation:
            verify(source)
            if (
                source.recommendation_uuid,
                source.recommendation_digest,
            ) not in latest.recommendation_identities:
                raise ExecutionReadinessError("SNAPSHOT_MISMATCH")
            return (source,), latest, source.created_at
        if type(source) is DecisionRecommendationSnapshot:
            snapshot = by_snapshot.get(source.snapshot_uuid)
            if snapshot != source:
                raise ExecutionReadinessError("SNAPSHOT_MISMATCH")
            selected = []
            for uid, d in snapshot.recommendation_identities:
                item = by_record.get(uid)
                if item is None or item.recommendation_digest != d:
                    raise ExecutionReadinessError("SNAPSHOT_MISMATCH")
                selected.append(item)
            return tuple(selected), snapshot, source.generated_at
        snapshot = by_snapshot.get(source.snapshot_uuid)
        if snapshot is None or snapshot.snapshot_digest != source.snapshot_digest:
            raise ExecutionReadinessError("SNAPSHOT_MISMATCH")
        if source.repository_digest != snapshot.repository_digest:
            raise ExecutionReadinessError("REPOSITORY_MISMATCH")
        try:
            valid = (
                recommendation_report_uuid(source.identity_payload())
                == source.report_uuid
                and recommendation_digest(source.digest_payload()) == source.report_digest
            )
        except Exception:
            valid = False
        if not valid:
            raise ExecutionReadinessError("BROKEN_PROVENANCE")
        identities = set(snapshot.recommendation_identities)
        for item in source.recommendations:
            verify(item)
            if (item.recommendation_uuid, item.recommendation_digest) not in identities:
                raise ExecutionReadinessError("SNAPSHOT_MISMATCH")
        return source.recommendations, snapshot, source.generated_at


GovernedAdvisoryExecutionReadinessEngine = GovernedExecutionReadinessEngine
