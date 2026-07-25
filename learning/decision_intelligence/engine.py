"""Governed construction of advisory Decision Intelligence; never a trading decision."""
from learning.decision_context import DecisionContext, DecisionContextSnapshot, DecisionContextReport, DecisionContextRepository
from learning.decision_context.identity import digest as context_digest, report_uuid as context_report_uuid
from learning.decision_context.exceptions import DecisionContextError
from learning.pattern_memory.models import valid_digest, valid_uuid
from .exceptions import DecisionIntelligenceError
from .models import AUTHORITY_SCOPE, DecisionIntelligence, DecisionIntelligenceReport, DecisionIntelligenceSnapshot
from .policy import DecisionIntelligencePolicy
from .repository import DecisionIntelligenceRepository


class GovernedDecisionIntelligenceEngine:
    def __init__(self, context_repository=None, repository=None, policy=None):
        self.context_repository = context_repository or DecisionContextRepository()
        self.repository = repository or DecisionIntelligenceRepository()
        self.policy = policy or DecisionIntelligencePolicy()
        if type(self.context_repository) is not DecisionContextRepository: raise DecisionIntelligenceError("INVALID_CONTEXT")
        if type(self.repository) is not DecisionIntelligenceRepository: raise DecisionIntelligenceError("REPOSITORY_MISMATCH")
        if type(self.policy) is not DecisionIntelligencePolicy: raise DecisionIntelligenceError("POLICY_MISMATCH")
        if self.policy.intelligence_engine_version != "PR184.1.0": raise DecisionIntelligenceError("ENGINE_VERSION_MISMATCH")

    def construct_intelligence(self, source):
        if type(source) not in (DecisionContext, DecisionContextReport, DecisionContextSnapshot): raise DecisionIntelligenceError("INVALID_CONTEXT")
        records, snapshot, generated_at = self._verify(source)
        self._verify_context_partition(records, snapshot)
        stored_intelligences = self.repository.records()
        for stored in stored_intelligences:
            if (stored.intelligence_policy_uuid, stored.intelligence_policy_digest,
                    stored.intelligence_policy_version, stored.intelligence_engine_version) != (
                    self.policy.intelligence_policy_uuid, self.policy.intelligence_policy_digest,
                    self.policy.intelligence_policy_version, self.policy.intelligence_engine_version):
                raise DecisionIntelligenceError("POLICY_MISMATCH")
        existing = {x.intelligence_uuid: x for x in stored_intelligences}; intelligences = []; duplicates = 0
        for context in sorted(records, key=lambda x: x.context_uuid):
            state = "DECISION_INTELLIGENCE_READY" if context.context_state == self.policy.prepared_context_state else ("INSUFFICIENT_DECISION_INTELLIGENCE" if context.context_state == self.policy.insufficient_context_state else "REJECTED")
            reason = {"DECISION_INTELLIGENCE_READY": "VERIFIED_DECISION_INTELLIGENCE_CONSTRUCTED", "INSUFFICIENT_DECISION_INTELLIGENCE": "DECISION_CONTEXT_EVIDENCE_INSUFFICIENT", "REJECTED": "DECISION_CONTEXT_REJECTED"}[state]
            item = DecisionIntelligence.create(decision_context_uuid=context.context_uuid, decision_context_digest=context.context_digest, context_state=context.context_state, decision_quality=float(context.confidence_score), decision_reliability=float(context.confidence_score if state == "DECISION_INTELLIGENCE_READY" else 0.0), decision_consistency=float(1.0 if state == "DECISION_INTELLIGENCE_READY" else 0.0), decision_recommendation={"DECISION_INTELLIGENCE_READY": "RECOMMENDATION_REVIEW_ELIGIBLE", "INSUFFICIENT_DECISION_INTELLIGENCE": "MORE_EVIDENCE_REQUIRED", "REJECTED": "RECOMMENDATION_REVIEW_REJECTED"}[state], decision_context_snapshot_uuid=snapshot.snapshot_uuid, decision_context_snapshot_digest=snapshot.snapshot_digest, decision_context_repository_digest=snapshot.repository_digest, intelligence_state=state, intelligence_reason=reason, intelligence_policy_uuid=self.policy.intelligence_policy_uuid, intelligence_policy_digest=self.policy.intelligence_policy_digest, intelligence_policy_version=self.policy.intelligence_policy_version, intelligence_engine_version=self.policy.intelligence_engine_version, created_at=context.created_at, authority_scope=AUTHORITY_SCOPE, advisory_only=True)
            prior = existing.get(item.intelligence_uuid)
            if prior is not None:
                if prior != item: raise DecisionIntelligenceError("REPLAY_COLLISION")
                item = prior; duplicates += 1
            else: self.repository.save(item); existing[item.intelligence_uuid] = item
            intelligences.append(item)
        identities = self.repository.identities(); repository_digest = self.repository.digest(); previous = self.repository.latest_snapshot()
        values = dict(intelligence_identities=identities, record_count=len(identities), repository_digest=repository_digest, intelligence_policy_uuid=self.policy.intelligence_policy_uuid, intelligence_policy_digest=self.policy.intelligence_policy_digest, intelligence_policy_version=self.policy.intelligence_policy_version, intelligence_engine_version=self.policy.intelligence_engine_version, context_policy_uuid=snapshot.context_policy_uuid, context_policy_digest=snapshot.context_policy_digest, context_policy_version=snapshot.context_policy_version, context_engine_version=snapshot.context_engine_version, authority_scope=AUTHORITY_SCOPE, advisory_only=True)
        if previous and all(getattr(previous, k) == v for k, v in values.items()): intelligence_snapshot = previous
        else:
            intelligence_snapshot = DecisionIntelligenceSnapshot.create(**values, previous_snapshot_uuid=previous.snapshot_uuid if previous else None, previous_snapshot_digest=previous.snapshot_digest if previous else None, generated_at=generated_at); self.repository.save_snapshot(intelligence_snapshot)
        return DecisionIntelligenceReport.create(decision_intelligences=tuple(intelligences), processed_count=len(intelligences), prepared_count=sum(x.intelligence_state == "DECISION_INTELLIGENCE_READY" for x in intelligences), insufficient_count=sum(x.intelligence_state == "INSUFFICIENT_DECISION_INTELLIGENCE" for x in intelligences), rejected_count=sum(x.intelligence_state == "REJECTED" for x in intelligences), duplicate_count=duplicates, repository_digest=repository_digest, snapshot_uuid=intelligence_snapshot.snapshot_uuid, snapshot_digest=intelligence_snapshot.snapshot_digest, generated_at=generated_at, advisory_only=True)

    run = construct_intelligence

    @staticmethod
    def _verify_context_partition(records, snapshot):
        """Bind every selected record to the selected PR183 policy partition."""
        if not records:
            raise DecisionIntelligenceError("INVALID_CONTEXT")
        expected = (
            snapshot.context_policy_uuid,
            snapshot.context_policy_digest,
            snapshot.context_policy_version,
            snapshot.context_engine_version,
        )
        if (
            not valid_uuid(expected[0])
            or not valid_digest(expected[1])
            or not isinstance(expected[2], str)
            or not expected[2]
            or expected[2] != expected[2].strip()
            or not isinstance(expected[3], str)
            or not expected[3]
            or expected[3] != expected[3].strip()
        ):
            raise DecisionIntelligenceError("POLICY_MISMATCH")
        for record in records:
            actual = (
                record.context_policy_uuid,
                record.context_policy_digest,
                record.context_policy_version,
                record.context_engine_version,
            )
            if actual != expected:
                raise DecisionIntelligenceError("POLICY_MISMATCH")

    def _verify(self, source):
        try:
            records = self.context_repository.records()
            snapshots = self.context_repository.snapshots()
            latest_snapshot = self.context_repository.latest_snapshot()
        except (DecisionContextError, ValueError, OSError) as exc:
            raise DecisionIntelligenceError("BROKEN_PROVENANCE") from exc
        if latest_snapshot is None:
            raise DecisionIntelligenceError("BROKEN_PROVENANCE")
        by_record = {x.context_uuid: x for x in records}
        by_snapshot = {x.snapshot_uuid: x for x in snapshots}
        def verify_record(item):
            try: valid = context_digest(item.digest_payload()) == item.context_digest
            except Exception: valid = False
            if by_record.get(item.context_uuid) != item or not valid: raise DecisionIntelligenceError("BROKEN_PROVENANCE")
        if type(source) is DecisionContext:
            verify_record(source)
            identity = (source.context_uuid, source.context_digest)
            if identity not in latest_snapshot.context_identities:
                raise DecisionIntelligenceError("SNAPSHOT_MISMATCH")
            return (source,), latest_snapshot, source.created_at
        if type(source) is DecisionContextSnapshot:
            snapshot = by_snapshot.get(source.snapshot_uuid)
            if snapshot != source: raise DecisionIntelligenceError("SNAPSHOT_MISMATCH")
            selected = []
            for uid, content_digest in snapshot.context_identities:
                item = by_record.get(uid)
                if item is None or item.context_digest != content_digest: raise DecisionIntelligenceError("SNAPSHOT_MISMATCH")
                selected.append(item)
            return tuple(selected), snapshot, source.generated_at
        snapshot = by_snapshot.get(source.snapshot_uuid)
        if snapshot is None or snapshot.snapshot_digest != source.snapshot_digest: raise DecisionIntelligenceError("SNAPSHOT_MISMATCH")
        if source.repository_digest != snapshot.repository_digest: raise DecisionIntelligenceError("REPOSITORY_MISMATCH")
        try: valid_report = context_report_uuid(source.identity_payload()) == source.report_uuid and context_digest(source.digest_payload()) == source.report_digest
        except Exception: valid_report = False
        if not valid_report: raise DecisionIntelligenceError("BROKEN_PROVENANCE")
        identities = set(snapshot.context_identities)
        for item in source.decision_contexts:
            verify_record(item)
            if (item.context_uuid, item.context_digest) not in identities:
                raise DecisionIntelligenceError("SNAPSHOT_MISMATCH")
        return source.decision_contexts, snapshot, source.generated_at
