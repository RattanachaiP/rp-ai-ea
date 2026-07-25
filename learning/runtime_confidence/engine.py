"""PR182 evidence-based advisory confidence evaluation.

This module verifies and scores governance evidence only.  It has no Runtime,
trading, decision-publication, risk, broker, or execution authority.
"""

from decimal import Decimal, ROUND_HALF_EVEN

from learning.runtime_selection import (
    KnowledgeEligibilityRecord,
    KnowledgeEligibilityReport,
    KnowledgeEligibilitySnapshot,
    RuntimeKnowledgeSelectionRepository,
)
from learning.runtime_selection.exceptions import RuntimeKnowledgeSelectionError
from learning.runtime_selection.identity import digest as eligibility_digest
from learning.runtime_selection.identity import report_uuid as eligibility_report_uuid
from learning.runtime_selection.models import PARTITION_FIELDS as PR181_PARTITION_FIELDS

from .exceptions import RuntimeConfidenceError
from .models import (
    AUTHORITY_SCOPE,
    PARTITION_FIELDS,
    ConfidenceDimensionResult,
    ConfidenceRecord,
    ConfidenceSnapshot,
    RuntimeConfidenceReport,
    confidence_band,
)
from .policy import RuntimeConfidencePolicy
from .repository import RuntimeConfidenceRepository


class RuntimeConfidenceEvaluator:
    """Evaluate immutable PR181 governance evidence for advisory confidence."""

    def __init__(self, eligibility_repository=None, repository=None, policy=None):
        self.eligibility_repository = (
            eligibility_repository or RuntimeKnowledgeSelectionRepository()
        )
        self.repository = repository or RuntimeConfidenceRepository()
        self.policy = policy or RuntimeConfidencePolicy()
        if type(self.eligibility_repository) is not RuntimeKnowledgeSelectionRepository:
            raise RuntimeConfidenceError("INVALID_ELIGIBILITY")
        if type(self.repository) is not RuntimeConfidenceRepository:
            raise RuntimeConfidenceError("REPOSITORY_MISMATCH")
        if type(self.policy) is not RuntimeConfidencePolicy:
            raise RuntimeConfidenceError("POLICY_MISMATCH")
        if self.policy.confidence_engine_version != "PR182.2.0":
            raise RuntimeConfidenceError("ENGINE_VERSION_MISMATCH")

    def evaluate_confidence(self, source):
        """Evaluate confidence evidence without interpreting or applying the score."""
        if type(source) not in (
            KnowledgeEligibilityRecord,
            KnowledgeEligibilityReport,
            KnowledgeEligibilitySnapshot,
        ):
            raise RuntimeConfidenceError("INVALID_ELIGIBILITY")

        records, source_snapshot, source_binding, generated_at = self._verify_source(
            source
        )
        partition = self._partition(records, source_snapshot)
        existing, previous_snapshot = self.repository.validate_partition(partition)
        by_uuid = {item.confidence_uuid: item for item in existing}
        confidence_records = []
        new_count = 0
        duplicate_count = 0

        for eligibility in sorted(records, key=lambda item: item.selection_uuid):
            dimensions = self._evaluate_dimensions(eligibility)
            state, reasons = self._confidence_state_and_reasons(eligibility, dimensions)
            score = self._score(dimensions)
            record = ConfidenceRecord.create(
                **partition,
                confidence_state=state,
                confidence_score=score,
                confidence_band=confidence_band(
                    score, self.policy.confidence_band_thresholds
                ),
                confidence_reasons=reasons,
                confidence_dimension_results=dimensions,
                source_eligibility_uuid=eligibility.selection_uuid,
                source_eligibility_digest=eligibility.selection_digest,
                source_eligibility_state=eligibility.selection_state,
                source_eligibility_reasons=eligibility.selection_reasons,
                source_eligibility_scope=eligibility.selection_scope,
                source_eligibility_snapshot_uuid=source_snapshot.snapshot_uuid,
                source_eligibility_snapshot_digest=source_snapshot.snapshot_digest,
                source_eligibility_repository_digest=source_snapshot.repository_digest,
                source_selection_policy_uuid=eligibility.selection_policy_uuid,
                source_selection_policy_digest=eligibility.selection_policy_digest,
                source_selection_policy_version=eligibility.selection_policy_version,
                source_selector_version=eligibility.selector_version,
                source_runtime_package_uuid=eligibility.source_runtime_package_uuid,
                source_runtime_package_digest=eligibility.source_runtime_package_digest,
                source_runtime_snapshot_uuid=eligibility.source_runtime_snapshot_uuid,
                source_runtime_snapshot_digest=eligibility.source_runtime_snapshot_digest,
                source_runtime_repository_digest=eligibility.source_runtime_repository_digest,
                source_registry_uuid=eligibility.source_registry_uuid,
                source_registry_digest=eligibility.source_registry_digest,
                source_promotion_uuid=eligibility.source_promotion_uuid,
                source_promotion_digest=eligibility.source_promotion_digest,
                source_validation_uuid=eligibility.source_validation_uuid,
                source_validation_digest=eligibility.source_validation_digest,
                source_memory_uuid=eligibility.source_memory_uuid,
                source_memory_digest=eligibility.source_memory_digest,
                source_pattern_uuid=eligibility.source_pattern_uuid,
                source_pattern_hash=eligibility.source_pattern_hash,
                knowledge_uuid=eligibility.knowledge_uuid,
                knowledge_version=eligibility.knowledge_version,
                source_runtime_package_state=eligibility.source_runtime_package_state,
                source_runtime_package_reasons=eligibility.source_runtime_package_reasons,
                source_registry_state=eligibility.source_registry_state,
                source_registry_reasons=eligibility.source_registry_reasons,
                source_validation_state=eligibility.source_validation_state,
                source_validation_reasons=eligibility.source_validation_reasons,
                source_promotion_state=eligibility.source_promotion_state,
                source_promotion_reasons=eligibility.source_promotion_reasons,
                score_precision=self.policy.score_precision,
                confidence_band_thresholds=self.policy.confidence_band_thresholds,
                reason_ordering_rules=self.policy.reason_ordering_rules,
                created_at=eligibility.created_at,
                authority_scope=AUTHORITY_SCOPE,
                advisory_only=True,
            )
            prior = by_uuid.get(record.confidence_uuid)
            if prior is not None:
                if prior != record:
                    raise RuntimeConfidenceError("REPLAY_COLLISION")
                record = prior
                duplicate_count += 1
            else:
                self.repository.save(record)
                by_uuid[record.confidence_uuid] = record
                new_count += 1
            confidence_records.append(record)

        identities = self.repository.identities()
        repository_digest = self.repository.digest()
        snapshot_values = {
            **partition,
            **source_binding,
            "source_eligibility_snapshot_uuid": source_snapshot.snapshot_uuid,
            "source_eligibility_snapshot_digest": source_snapshot.snapshot_digest,
            "source_eligibility_repository_digest": source_snapshot.repository_digest,
            "confidence_identities": identities,
            "record_count": len(identities),
            "repository_digest": repository_digest,
        }
        reusable = previous_snapshot is not None and all(
            getattr(previous_snapshot, name) == value
            for name, value in snapshot_values.items()
        )
        if reusable:
            confidence_snapshot = previous_snapshot
        else:
            confidence_snapshot = ConfidenceSnapshot.create(
                **snapshot_values,
                previous_snapshot_uuid=(
                    previous_snapshot.snapshot_uuid if previous_snapshot else None
                ),
                previous_snapshot_digest=(
                    previous_snapshot.snapshot_digest if previous_snapshot else None
                ),
                generated_at=generated_at,
                authority_scope=AUTHORITY_SCOPE,
                advisory_only=True,
            )
            self.repository.save_snapshot(confidence_snapshot)

        return RuntimeConfidenceReport.create(
            **partition,
            **source_binding,
            source_eligibility_snapshot_uuid=source_snapshot.snapshot_uuid,
            source_eligibility_snapshot_digest=source_snapshot.snapshot_digest,
            source_eligibility_repository_digest=source_snapshot.repository_digest,
            confidence_records=tuple(confidence_records),
            processed_record_count=len(confidence_records),
            new_confidence_record_count=new_count,
            duplicate_confidence_record_count=duplicate_count,
            confidence_evaluated_count=sum(
                item.confidence_state == "CONFIDENCE_EVALUATED"
                for item in confidence_records
            ),
            insufficient_confidence_evidence_count=sum(
                item.confidence_state == "INSUFFICIENT_CONFIDENCE_EVIDENCE"
                for item in confidence_records
            ),
            rejected_count=sum(
                item.confidence_state == "REJECTED" for item in confidence_records
            ),
            repository_digest=repository_digest,
            snapshot_uuid=confidence_snapshot.snapshot_uuid,
            snapshot_digest=confidence_snapshot.snapshot_digest,
            generated_at=generated_at,
            authority_scope=AUTHORITY_SCOPE,
            advisory_only=True,
        )

    run = evaluate_confidence

    def _verify_source(self, source):
        try:
            stored_records = self.eligibility_repository.selections()
            snapshots = self.eligibility_repository.snapshots()
            self.eligibility_repository.latest_snapshot()
        except RuntimeKnowledgeSelectionError as exc:
            raise RuntimeConfidenceError("BROKEN_PROVENANCE") from exc

        ordered_snapshots = self._ordered_eligibility_snapshots(snapshots)
        by_record = {item.selection_uuid: item for item in stored_records}
        by_snapshot = {item.snapshot_uuid: item for item in ordered_snapshots}

        if type(source) is KnowledgeEligibilityRecord:
            self._verify_record(source, by_record)
            source_snapshot = self._earliest_membership(source, ordered_snapshots)
            binding = self._source_binding(
                "ELIGIBILITY_RECORD", source.selection_uuid, source.selection_digest
            )
            return (source,), source_snapshot, binding, source.created_at

        if type(source) is KnowledgeEligibilitySnapshot:
            source_snapshot = by_snapshot.get(source.snapshot_uuid)
            if source_snapshot != source:
                raise RuntimeConfidenceError("SNAPSHOT_MISMATCH")
            selected = self._records_for_snapshot(source_snapshot, by_record)
            binding = self._source_binding(
                "ELIGIBILITY_SNAPSHOT",
                source.snapshot_uuid,
                source.snapshot_digest,
            )
            return selected, source_snapshot, binding, source.generated_at

        source_snapshot = by_snapshot.get(source.selection_snapshot_uuid)
        if (
            source_snapshot is None
            or source_snapshot.snapshot_digest != source.selection_snapshot_digest
        ):
            raise RuntimeConfidenceError("SNAPSHOT_MISMATCH")
        if source.repository_digest != source_snapshot.repository_digest:
            raise RuntimeConfidenceError("REPOSITORY_MISMATCH")
        if tuple(getattr(source, name) for name in PR181_PARTITION_FIELDS) != tuple(
            getattr(source_snapshot, name) for name in PR181_PARTITION_FIELDS
        ):
            raise RuntimeConfidenceError("UPSTREAM_PARTITION_MISMATCH")
        self._verify_report(source)
        identities = set(source_snapshot.selection_identities)
        for item in source.runtime_selections:
            self._verify_record(item, by_record)
            if (item.selection_uuid, item.selection_digest) not in identities:
                raise RuntimeConfidenceError("REPORT_BINDING_MISMATCH")
        binding = self._source_binding(
            "ELIGIBILITY_REPORT", source.report_uuid, source.report_digest
        )
        return source.runtime_selections, source_snapshot, binding, source.generated_at

    @staticmethod
    def _verify_record(record, by_record):
        try:
            valid_identity = record.selection_digest == eligibility_digest(
                record.digest_payload()
            )
        except (AttributeError, TypeError, ValueError):
            valid_identity = False
        if by_record.get(record.selection_uuid) != record or not valid_identity:
            raise RuntimeConfidenceError("BROKEN_PROVENANCE")

    @staticmethod
    def _verify_report(report):
        selections = tuple(report.runtime_selections)
        valid_counts = (
            report.processed_package_count == len(selections)
            and report.new_selection_count + report.duplicate_selection_count
            == len(selections)
            and report.eligible_count
            == sum(
                item.selection_state == "ELIGIBLE_FOR_CONFIDENCE_EVALUATION"
                for item in selections
            )
            and report.insufficient_selection_evidence_count
            == sum(
                item.selection_state == "INSUFFICIENT_SELECTION_EVIDENCE"
                for item in selections
            )
            and report.rejected_count
            == sum(item.selection_state == "REJECTED" for item in selections)
        )
        try:
            valid_identity = (
                eligibility_report_uuid(report.identity_payload()) == report.report_uuid
                and eligibility_digest(report.digest_payload()) == report.report_digest
            )
        except (AttributeError, TypeError, ValueError):
            valid_identity = False
        if not valid_counts or not valid_identity:
            raise RuntimeConfidenceError("REPORT_BINDING_MISMATCH")

    @staticmethod
    def _ordered_eligibility_snapshots(snapshots):
        if not snapshots:
            raise RuntimeConfidenceError("BROKEN_PROVENANCE")
        by_uuid = {item.snapshot_uuid: item for item in snapshots}
        children = {}
        roots = []
        for item in snapshots:
            if item.previous_snapshot_uuid is None:
                roots.append(item)
            elif item.previous_snapshot_uuid in children:
                raise RuntimeConfidenceError("BROKEN_PROVENANCE")
            else:
                children[item.previous_snapshot_uuid] = item
        if len(by_uuid) != len(snapshots) or len(roots) != 1:
            raise RuntimeConfidenceError("BROKEN_PROVENANCE")
        ordered = []
        current = roots[0]
        while current is not None:
            ordered.append(current)
            current = children.get(current.snapshot_uuid)
        if len(ordered) != len(snapshots):
            raise RuntimeConfidenceError("BROKEN_PROVENANCE")
        return tuple(ordered)

    @staticmethod
    def _earliest_membership(record, snapshots):
        identity = (record.selection_uuid, record.selection_digest)
        for snapshot in snapshots:
            if identity in snapshot.selection_identities:
                return snapshot
        raise RuntimeConfidenceError("SNAPSHOT_MISMATCH")

    @staticmethod
    def _records_for_snapshot(snapshot, by_record):
        selected = []
        for identity, content_digest in snapshot.selection_identities:
            record = by_record.get(identity)
            if record is None or record.selection_digest != content_digest:
                raise RuntimeConfidenceError("SNAPSHOT_MISMATCH")
            selected.append(record)
        return tuple(selected)

    @staticmethod
    def _source_binding(artifact_type, artifact_uuid, artifact_digest):
        return {
            "source_artifact_type": artifact_type,
            "source_artifact_uuid": artifact_uuid,
            "source_artifact_digest": artifact_digest,
        }

    def _partition(self, records, snapshot):
        if not records:
            raise RuntimeConfidenceError("INVALID_ELIGIBILITY")
        first = records[0]
        partition = {
            "confidence_policy_uuid": self.policy.confidence_policy_uuid,
            "confidence_policy_digest": self.policy.confidence_policy_digest,
            "confidence_policy_version": self.policy.confidence_policy_version,
            "confidence_engine_version": self.policy.confidence_engine_version,
            **{name: getattr(first, name) for name in PR181_PARTITION_FIELDS},
        }
        for record in records:
            actual = tuple(getattr(record, name) for name in PR181_PARTITION_FIELDS)
            expected = tuple(partition[name] for name in PR181_PARTITION_FIELDS)
            if actual != expected:
                raise RuntimeConfidenceError("UPSTREAM_PARTITION_MISMATCH")
        snapshot_partition = tuple(
            getattr(snapshot, name) for name in PR181_PARTITION_FIELDS
        )
        if snapshot_partition != tuple(
            partition[name] for name in PR181_PARTITION_FIELDS
        ):
            raise RuntimeConfidenceError("UPSTREAM_PARTITION_MISMATCH")
        if tuple(partition) != PARTITION_FIELDS:
            raise RuntimeConfidenceError("UPSTREAM_PARTITION_MISMATCH")
        return partition

    def _evaluate_dimensions(self, item):
        weight_by_dimension = dict(self.policy.dimension_weights)
        unmet_states = sum(
            (
                item.source_runtime_package_state != "ADVISORY_PACKAGE_PREPARED",
                item.source_registry_state != "ADVISORY_ENTRY_RECORDED",
                item.source_promotion_state != "POLICY_CRITERIA_MET",
                item.source_validation_state != "STATISTICALLY_CONSISTENT",
            )
        )
        if item.selection_state == self.policy.required_eligibility_state:
            eligibility_score = 1.0
            eligibility_reason = "ELIGIBILITY_EVIDENCE_COMPLETE"
        elif item.selection_state == "INSUFFICIENT_SELECTION_EVIDENCE":
            eligibility_score = 0.6
            eligibility_reason = "ELIGIBILITY_EVIDENCE_INSUFFICIENT"
        else:
            eligibility_score = 0.2
            eligibility_reason = "ELIGIBILITY_REJECTED"

        evidence = (
            (
                "ELIGIBILITY_EVIDENCE_COMPLETENESS",
                item.selection_state,
                eligibility_score,
                eligibility_reason,
            ),
            (
                "RUNTIME_PACKAGE_VALIDATION",
                item.source_runtime_package_state,
                (
                    1.0
                    if item.source_runtime_package_state == "ADVISORY_PACKAGE_PREPARED"
                    else 0.0
                ),
                (
                    "RUNTIME_PACKAGE_STATE_SATISFIED"
                    if item.source_runtime_package_state == "ADVISORY_PACKAGE_PREPARED"
                    else "RUNTIME_PACKAGE_STATE_UNSATISFIED"
                ),
            ),
            (
                "REGISTRY_ADMISSION",
                item.source_registry_state,
                1.0 if item.source_registry_state == "ADVISORY_ENTRY_RECORDED" else 0.0,
                (
                    "REGISTRY_ADMISSION_SATISFIED"
                    if item.source_registry_state == "ADVISORY_ENTRY_RECORDED"
                    else "REGISTRY_ADMISSION_UNSATISFIED"
                ),
            ),
            (
                "PROMOTION_STATE",
                item.source_promotion_state,
                1.0 if item.source_promotion_state == "POLICY_CRITERIA_MET" else 0.25,
                (
                    "PROMOTION_STATE_SATISFIED"
                    if item.source_promotion_state == "POLICY_CRITERIA_MET"
                    else "PROMOTION_STATE_UNSATISFIED"
                ),
            ),
            (
                "VALIDATION_STATE",
                item.source_validation_state,
                (
                    1.0
                    if item.source_validation_state == "STATISTICALLY_CONSISTENT"
                    else 0.25
                ),
                (
                    "VALIDATION_STATE_SATISFIED"
                    if item.source_validation_state == "STATISTICALLY_CONSISTENT"
                    else "VALIDATION_STATE_UNSATISFIED"
                ),
            ),
            (
                "UPSTREAM_REASON_SEVERITY",
                f"UNSATISFIED_STATE_COUNT={unmet_states}",
                max(0.0, 1.0 - 0.25 * unmet_states),
                (
                    "UPSTREAM_REASONS_CLEAR"
                    if unmet_states == 0
                    else "UPSTREAM_REASONS_SEVERE"
                ),
            ),
            (
                "SNAPSHOT_MEMBERSHIP_INTEGRITY",
                "VERIFIED",
                1.0,
                "SNAPSHOT_MEMBERSHIP_VERIFIED",
            ),
            (
                "LINEAGE_COMPLETENESS",
                "COMPLETE_PR181_RETAINED_LINEAGE",
                1.0,
                "LINEAGE_COMPLETE",
            ),
            (
                "POLICY_PARTITION_CONSISTENCY",
                "CONSISTENT",
                1.0,
                "POLICY_PARTITION_CONSISTENT",
            ),
        )
        results = []
        for dimension, raw_value, score, reason in evidence:
            state = (
                "SATISFIED"
                if score == 1.0
                else "UNSATISFIED" if score == 0.0 else "PARTIAL"
            )
            weight = weight_by_dimension[dimension]
            contribution = float(
                (Decimal(str(score)) * Decimal(str(weight))).quantize(
                    Decimal("0.000000000001"), rounding=ROUND_HALF_EVEN
                )
            )
            try:
                result = ConfidenceDimensionResult(
                    dimension=dimension,
                    state=state,
                    raw_value=str(raw_value),
                    normalized_score=float(score),
                    weight=float(weight),
                    weighted_contribution=contribution,
                    reasons=(reason,),
                )
            except ValueError as exc:
                raise RuntimeConfidenceError("INVALID_CONFIDENCE_EVIDENCE") from exc
            results.append(result)
        return tuple(results)

    def _score(self, dimensions):
        quantum = Decimal(1).scaleb(-self.policy.score_precision)
        value = sum(
            (Decimal(str(item.weighted_contribution)) for item in dimensions),
            Decimal("0"),
        ).quantize(quantum, rounding=ROUND_HALF_EVEN)
        score = float(value)
        if not 0.0 <= score <= 1.0:
            raise RuntimeConfidenceError("INVALID_CONFIDENCE_SCORE")
        return score

    def _confidence_state_and_reasons(self, eligibility, dimensions):
        if eligibility.selection_state == "REJECTED":
            state = "REJECTED"
        elif eligibility.selection_state == "INSUFFICIENT_SELECTION_EVIDENCE":
            state = "INSUFFICIENT_CONFIDENCE_EVIDENCE"
        else:
            state = "CONFIDENCE_EVALUATED"
        available = {reason for result in dimensions for reason in result.reasons}
        if state == "CONFIDENCE_EVALUATED":
            available.add("ADVISORY_CONFIDENCE_CALCULATED")
        reasons = tuple(
            reason
            for reason in self.policy.reason_ordering_rules
            if reason in available
        )
        if not reasons:
            raise RuntimeConfidenceError("INSUFFICIENT_CONFIDENCE_EVIDENCE")
        return state, reasons
