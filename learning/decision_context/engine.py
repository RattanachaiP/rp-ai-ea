"""Governed construction of advisory Decision Context; never a trading decision."""
from learning.runtime_confidence import ConfidenceRecord, ConfidenceSnapshot, RuntimeConfidenceReport, RuntimeConfidenceRepository
from learning.runtime_confidence.identity import digest as confidence_digest, report_uuid as confidence_report_uuid
from learning.runtime_confidence.exceptions import RuntimeConfidenceError
from learning.pattern_memory.models import valid_digest, valid_uuid
from .exceptions import DecisionContextError
from .models import AUTHORITY_SCOPE, DecisionContext, DecisionContextReport, DecisionContextSnapshot
from .policy import DecisionContextPolicy
from .repository import DecisionContextRepository


class GovernedDecisionContextEngine:
    def __init__(self, confidence_repository=None, repository=None, policy=None):
        self.confidence_repository = confidence_repository or RuntimeConfidenceRepository()
        self.repository = repository or DecisionContextRepository()
        self.policy = policy or DecisionContextPolicy()
        if type(self.confidence_repository) is not RuntimeConfidenceRepository: raise DecisionContextError("INVALID_CONFIDENCE")
        if type(self.repository) is not DecisionContextRepository: raise DecisionContextError("REPOSITORY_MISMATCH")
        if type(self.policy) is not DecisionContextPolicy: raise DecisionContextError("POLICY_MISMATCH")
        if self.policy.context_engine_version != "PR183.1.0": raise DecisionContextError("ENGINE_VERSION_MISMATCH")

    def construct_context(self, source):
        if type(source) not in (ConfidenceRecord, RuntimeConfidenceReport, ConfidenceSnapshot): raise DecisionContextError("INVALID_CONFIDENCE")
        records, snapshot, generated_at = self._verify(source)
        self._verify_confidence_partition(records, snapshot)
        stored_contexts = self.repository.records()
        for stored in stored_contexts:
            if (stored.context_policy_uuid, stored.context_policy_digest,
                    stored.context_policy_version, stored.context_engine_version) != (
                    self.policy.context_policy_uuid, self.policy.context_policy_digest,
                    self.policy.context_policy_version, self.policy.context_engine_version):
                raise DecisionContextError("POLICY_MISMATCH")
        existing = {x.context_uuid: x for x in stored_contexts}; contexts = []; duplicates = 0
        for confidence in sorted(records, key=lambda x: x.confidence_uuid):
            state = "CONTEXT_PREPARED" if confidence.confidence_state == self.policy.prepared_confidence_state else ("INSUFFICIENT_CONTEXT_EVIDENCE" if confidence.confidence_state == self.policy.insufficient_confidence_state else "REJECTED")
            reason = {"CONTEXT_PREPARED": "VERIFIED_CONFIDENCE_CONTEXT_PREPARED", "INSUFFICIENT_CONTEXT_EVIDENCE": "CONFIDENCE_EVIDENCE_INSUFFICIENT", "REJECTED": "CONFIDENCE_REJECTED"}[state]
            item = DecisionContext.create(confidence_uuid=confidence.confidence_uuid, confidence_digest=confidence.confidence_digest, confidence_state=confidence.confidence_state, confidence_score=confidence.confidence_score, confidence_band=confidence.confidence_band, confidence_snapshot_uuid=snapshot.snapshot_uuid, confidence_snapshot_digest=snapshot.snapshot_digest, confidence_repository_digest=snapshot.repository_digest, context_state=state, context_reason=reason, context_policy_uuid=self.policy.context_policy_uuid, context_policy_digest=self.policy.context_policy_digest, context_policy_version=self.policy.context_policy_version, context_engine_version=self.policy.context_engine_version, created_at=confidence.created_at, authority_scope=AUTHORITY_SCOPE, advisory_only=True)
            prior = existing.get(item.context_uuid)
            if prior is not None:
                if prior != item: raise DecisionContextError("REPLAY_COLLISION")
                item = prior; duplicates += 1
            else: self.repository.save(item); existing[item.context_uuid] = item
            contexts.append(item)
        identities = self.repository.identities(); repository_digest = self.repository.digest(); previous = self.repository.latest_snapshot()
        values = dict(context_identities=identities, record_count=len(identities), repository_digest=repository_digest, context_policy_uuid=self.policy.context_policy_uuid, context_policy_digest=self.policy.context_policy_digest, context_policy_version=self.policy.context_policy_version, context_engine_version=self.policy.context_engine_version, confidence_policy_uuid=snapshot.confidence_policy_uuid, confidence_policy_digest=snapshot.confidence_policy_digest, confidence_policy_version=snapshot.confidence_policy_version, confidence_engine_version=snapshot.confidence_engine_version, authority_scope=AUTHORITY_SCOPE, advisory_only=True)
        if previous and all(getattr(previous, k) == v for k, v in values.items()): context_snapshot = previous
        else:
            context_snapshot = DecisionContextSnapshot.create(**values, previous_snapshot_uuid=previous.snapshot_uuid if previous else None, previous_snapshot_digest=previous.snapshot_digest if previous else None, generated_at=generated_at); self.repository.save_snapshot(context_snapshot)
        return DecisionContextReport.create(decision_contexts=tuple(contexts), processed_count=len(contexts), prepared_count=sum(x.context_state == "CONTEXT_PREPARED" for x in contexts), insufficient_count=sum(x.context_state == "INSUFFICIENT_CONTEXT_EVIDENCE" for x in contexts), rejected_count=sum(x.context_state == "REJECTED" for x in contexts), duplicate_count=duplicates, repository_digest=repository_digest, snapshot_uuid=context_snapshot.snapshot_uuid, snapshot_digest=context_snapshot.snapshot_digest, generated_at=generated_at, advisory_only=True)

    run = construct_context

    @staticmethod
    def _verify_confidence_partition(records, snapshot):
        """Bind every selected record to the selected PR182 policy partition."""
        if not records:
            raise DecisionContextError("INVALID_CONFIDENCE")
        expected = (
            snapshot.confidence_policy_uuid,
            snapshot.confidence_policy_digest,
            snapshot.confidence_policy_version,
            snapshot.confidence_engine_version,
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
            raise DecisionContextError("POLICY_MISMATCH")
        for record in records:
            actual = (
                record.confidence_policy_uuid,
                record.confidence_policy_digest,
                record.confidence_policy_version,
                record.confidence_engine_version,
            )
            if actual != expected:
                raise DecisionContextError("POLICY_MISMATCH")

    def _verify(self, source):
        try:
            records = self.confidence_repository.records()
            snapshots = self.confidence_repository.snapshots()
            latest_snapshot = self.confidence_repository.latest_snapshot()
        except (RuntimeConfidenceError, ValueError, OSError) as exc:
            raise DecisionContextError("BROKEN_PROVENANCE") from exc
        if latest_snapshot is None:
            raise DecisionContextError("BROKEN_PROVENANCE")
        by_record = {x.confidence_uuid: x for x in records}
        by_snapshot = {x.snapshot_uuid: x for x in snapshots}
        def verify_record(item):
            try: valid = confidence_digest(item.digest_payload()) == item.confidence_digest
            except Exception: valid = False
            if by_record.get(item.confidence_uuid) != item or not valid: raise DecisionContextError("BROKEN_PROVENANCE")
        if type(source) is ConfidenceRecord:
            verify_record(source)
            identity = (source.confidence_uuid, source.confidence_digest)
            if identity not in latest_snapshot.confidence_identities:
                raise DecisionContextError("SNAPSHOT_MISMATCH")
            return (source,), latest_snapshot, source.created_at
        if type(source) is ConfidenceSnapshot:
            snapshot = by_snapshot.get(source.snapshot_uuid)
            if snapshot != source: raise DecisionContextError("SNAPSHOT_MISMATCH")
            selected = []
            for uid, content_digest in snapshot.confidence_identities:
                item = by_record.get(uid)
                if item is None or item.confidence_digest != content_digest: raise DecisionContextError("SNAPSHOT_MISMATCH")
                selected.append(item)
            return tuple(selected), snapshot, source.generated_at
        snapshot = by_snapshot.get(source.snapshot_uuid)
        if snapshot is None or snapshot.snapshot_digest != source.snapshot_digest: raise DecisionContextError("SNAPSHOT_MISMATCH")
        if source.repository_digest != snapshot.repository_digest: raise DecisionContextError("REPOSITORY_MISMATCH")
        try: valid_report = confidence_report_uuid(source.identity_payload()) == source.report_uuid and confidence_digest(source.digest_payload()) == source.report_digest
        except Exception: valid_report = False
        if not valid_report: raise DecisionContextError("BROKEN_PROVENANCE")
        identities = set(snapshot.confidence_identities)
        for item in source.confidence_records:
            verify_record(item)
            if (item.confidence_uuid, item.confidence_digest) not in identities:
                raise DecisionContextError("SNAPSHOT_MISMATCH")
        return source.confidence_records, snapshot, source.generated_at
