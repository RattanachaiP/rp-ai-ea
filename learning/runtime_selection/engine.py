"""PR181 advisory eligibility evaluation; no Runtime or execution authority."""

from dataclasses import replace

from learning.runtime_knowledge import (
    RuntimeKnowledgePackage,
    RuntimeKnowledgePackagingReport,
    RuntimeKnowledgeRepository,
    RuntimeKnowledgeSnapshot,
)
from learning.runtime_knowledge.exceptions import RuntimeKnowledgeError
from learning.runtime_knowledge.identity import digest as runtime_digest
from learning.runtime_knowledge.identity import report_uuid as packaging_report_uuid
from learning.runtime_knowledge.models import (
    PACKAGE_REASONS,
    PACKAGE_STATE,
    PARTITION_FIELDS as PR180_PARTITION_FIELDS,
)

from .exceptions import RuntimeKnowledgeSelectionError
from .models import (
    ELIGIBLE,
    PARTITION_FIELDS,
    SELECTION_SCOPE,
    RuntimeKnowledgeSelection,
    RuntimeKnowledgeSelectionReport,
    RuntimeKnowledgeSelectionSnapshot,
)
from .policy import RuntimeKnowledgeSelectionPolicy
from .repository import RuntimeKnowledgeSelectionRepository


class RuntimeKnowledgeSelector:
    """Record advisory eligibility for future confidence evaluation only."""

    def __init__(self, runtime_repository=None, repository=None, policy=None):
        self.runtime_repository = runtime_repository or RuntimeKnowledgeRepository()
        self.repository = repository or RuntimeKnowledgeSelectionRepository()
        self.policy = policy or RuntimeKnowledgeSelectionPolicy()
        if type(self.runtime_repository) is not RuntimeKnowledgeRepository:
            raise RuntimeKnowledgeSelectionError("INVALID_RUNTIME_KNOWLEDGE_REPOSITORY")
        if type(self.repository) is not RuntimeKnowledgeSelectionRepository:
            raise RuntimeKnowledgeSelectionError("INVALID_SELECTION_REPOSITORY")
        if type(self.policy) is not RuntimeKnowledgeSelectionPolicy:
            raise RuntimeKnowledgeSelectionError("SELECTION_POLICY_MISMATCH")

    def evaluate_eligibility(self, source):
        """Record advisory eligibility; never activate, apply, rank, weight, or score."""
        if type(source) not in (
            RuntimeKnowledgePackage,
            RuntimeKnowledgeSnapshot,
            RuntimeKnowledgePackagingReport,
        ):
            raise RuntimeKnowledgeSelectionError("INVALID_RUNTIME_KNOWLEDGE_INPUT")
        packages, source_snapshot, source_fields, generated_at = self._verify_source(
            source
        )
        partition = self._partition(packages, source_snapshot)
        existing, previous = self.repository.validate_partition(partition)
        by_package = {item.source_runtime_package_uuid: item for item in existing}
        runtime_selections = []
        new_count = duplicate_count = 0
        for package in sorted(packages, key=lambda item: item.runtime_package_uuid):
            state, reasons = self._classify(package)
            selection = RuntimeKnowledgeSelection.create(
                **partition,
                source_runtime_package_uuid=package.runtime_package_uuid,
                source_runtime_package_digest=package.runtime_package_digest,
                source_runtime_snapshot_uuid=source_snapshot.snapshot_uuid,
                source_runtime_snapshot_digest=source_snapshot.snapshot_digest,
                source_runtime_repository_digest=source_snapshot.repository_digest,
                source_registry_uuid=package.source_registry_uuid,
                source_registry_digest=package.source_registry_digest,
                source_promotion_uuid=package.source_promotion_uuid,
                source_promotion_digest=package.source_promotion_digest,
                source_validation_uuid=package.source_validation_uuid,
                source_validation_digest=package.source_validation_digest,
                source_memory_uuid=package.source_memory_uuid,
                source_memory_digest=package.source_memory_digest,
                source_pattern_uuid=package.source_pattern_uuid,
                source_pattern_hash=package.source_pattern_hash,
                knowledge_uuid=package.knowledge_uuid,
                knowledge_version=package.knowledge_version,
                memory_version=package.memory_version,
                memory_state=package.memory_state,
                source_report_uuid=package.source_report_uuid,
                source_policy_uuid=package.source_policy_uuid,
                source_policy_version=package.source_policy_version,
                source_attribution_uuid=package.source_attribution_uuid,
                source_digest=package.source_digest,
                replay_digest=package.replay_digest,
                evidence_envelope_uuid=package.evidence_envelope_uuid,
                evidence_envelope_digest=package.evidence_envelope_digest,
                source_engine_version=package.source_engine_version,
                mining_config_digest=package.mining_config_digest,
                outcome_contract=package.outcome_contract,
                source_validation_statistics=package.source_validation_statistics,
                source_validated_at=package.source_validated_at,
                source_validation_thresholds=package.source_validation_thresholds,
                promotion_policy_thresholds=package.promotion_policy_thresholds,
                threshold_monotonicity_result=package.threshold_monotonicity_result,
                source_promotion_created_at=package.source_promotion_created_at,
                source_registry_recorded_at=package.source_registry_recorded_at,
                source_runtime_package_state=package.runtime_package_state,
                source_runtime_package_reasons=package.runtime_package_reasons,
                source_registry_state=package.source_registry_state,
                source_registry_reasons=package.source_registry_reasons,
                source_validation_state=package.source_validation_state,
                source_validation_reasons=package.source_validation_reasons,
                source_promotion_state=package.source_promotion_state,
                source_promotion_reasons=package.source_promotion_reasons,
                selection_state=state,
                selection_reasons=reasons,
                selection_scope=SELECTION_SCOPE,
                created_at=package.generated_at,
                advisory_only=True,
            )
            prior = by_package.get(package.runtime_package_uuid)
            if prior is not None:
                if prior != selection:
                    raise RuntimeKnowledgeSelectionError("SELECTION_REPLAY_COLLISION")
                selection = prior
                duplicate_count += 1
            else:
                self.repository.save(selection)
                by_package[package.runtime_package_uuid] = selection
                new_count += 1
            runtime_selections.append(selection)

        identities = self.repository.identities()
        repository_digest = self.repository.digest()
        snapshot_values = {
            **partition,
            "source_runtime_snapshot_uuid": source_snapshot.snapshot_uuid,
            "source_runtime_snapshot_digest": source_snapshot.snapshot_digest,
            "source_runtime_repository_digest": source_snapshot.repository_digest,
            "selection_identities": identities,
            "selection_count": len(identities),
            "repository_digest": repository_digest,
        }
        reusable = previous is not None and all(
            getattr(previous, name) == value for name, value in snapshot_values.items()
        )
        if reusable:
            selection_snapshot = previous
        else:
            selection_snapshot = RuntimeKnowledgeSelectionSnapshot.create(
                **snapshot_values,
                previous_snapshot_uuid=previous.snapshot_uuid if previous else None,
                previous_snapshot_digest=previous.snapshot_digest if previous else None,
                generated_at=generated_at,
                advisory_only=True,
            )
            self.repository.save_snapshot(selection_snapshot)

        eligible_count = sum(
            item.selection_state == ELIGIBLE for item in runtime_selections
        )
        insufficient_count = sum(
            item.selection_state == "INSUFFICIENT_SELECTION_EVIDENCE"
            for item in runtime_selections
        )
        rejected_count = sum(
            item.selection_state == "REJECTED" for item in runtime_selections
        )
        return RuntimeKnowledgeSelectionReport.create(
            **source_fields,
            **partition,
            source_runtime_snapshot_uuid=source_snapshot.snapshot_uuid,
            source_runtime_snapshot_digest=source_snapshot.snapshot_digest,
            source_runtime_repository_digest=source_snapshot.repository_digest,
            runtime_selections=tuple(runtime_selections),
            processed_package_count=len(runtime_selections),
            new_selection_count=new_count,
            duplicate_selection_count=duplicate_count,
            eligible_count=eligible_count,
            insufficient_selection_evidence_count=insufficient_count,
            rejected_count=rejected_count,
            repository_digest=repository_digest,
            selection_snapshot_uuid=selection_snapshot.snapshot_uuid,
            selection_snapshot_digest=selection_snapshot.snapshot_digest,
            generated_at=generated_at,
            advisory_only=True,
        )

    select = evaluate_eligibility
    run = evaluate_eligibility

    def _verify_source(self, source):
        try:
            packages = self.runtime_repository.packages()
            snapshots = self.runtime_repository.snapshots()
        except RuntimeKnowledgeError as exc:
            raise RuntimeKnowledgeSelectionError(
                "BROKEN_RUNTIME_PACKAGE_PROVENANCE"
            ) from exc
        ordered_snapshots = self._ordered_snapshots(snapshots)
        by_package = {item.runtime_package_uuid: item for item in packages}
        by_snapshot = {item.snapshot_uuid: item for item in ordered_snapshots}

        if type(source) is RuntimeKnowledgePackagingReport:
            self._verify_report_counters(source)
        try:
            clean = replace(source)
        except (TypeError, ValueError) as exc:
            labels = {
                RuntimeKnowledgePackage: "BROKEN_RUNTIME_PACKAGE",
                RuntimeKnowledgeSnapshot: "RUNTIME_PACKAGING_REPORT_SNAPSHOT_MISMATCH",
                RuntimeKnowledgePackagingReport: "BROKEN_RUNTIME_PACKAGING_REPORT",
            }
            raise RuntimeKnowledgeSelectionError(labels[type(source)]) from exc

        if type(source) is RuntimeKnowledgePackage:
            stored = by_package.get(clean.runtime_package_uuid)
            if stored != clean:
                raise RuntimeKnowledgeSelectionError("BROKEN_PACKAGE_PROVENANCE")
            snapshot = self._earliest_membership(clean, ordered_snapshots)
            self._validate_runtime_repository()
            fields = self._source_fields(
                "RUNTIME_KNOWLEDGE_PACKAGE",
                package=(clean.runtime_package_uuid, clean.runtime_package_digest),
            )
            return (clean,), snapshot, fields, clean.generated_at

        if type(source) is RuntimeKnowledgeSnapshot:
            self._validate_runtime_repository()
            snapshot = by_snapshot.get(clean.snapshot_uuid)
            if snapshot != clean:
                raise RuntimeKnowledgeSelectionError(
                    "RUNTIME_PACKAGING_REPORT_SNAPSHOT_MISMATCH"
                )
            selected = self._packages_for_snapshot(clean, by_package)
            fields = self._source_fields("RUNTIME_KNOWLEDGE_SNAPSHOT")
            return selected, clean, fields, clean.generated_at

        self._validate_runtime_repository()
        if packaging_report_uuid(clean.identity_payload()) != clean.report_uuid:
            raise RuntimeKnowledgeSelectionError("BROKEN_RUNTIME_PACKAGING_REPORT")
        snapshot = by_snapshot.get(clean.snapshot_uuid)
        if snapshot is None or snapshot.snapshot_digest != clean.snapshot_digest:
            raise RuntimeKnowledgeSelectionError(
                "RUNTIME_PACKAGING_REPORT_SNAPSHOT_MISMATCH"
            )
        if snapshot.repository_digest != clean.repository_digest:
            raise RuntimeKnowledgeSelectionError(
                "RUNTIME_PACKAGING_REPORT_REPOSITORY_MISMATCH"
            )
        if tuple(getattr(clean, name) for name in PR180_PARTITION_FIELDS) != tuple(
            getattr(snapshot, name) for name in PR180_PARTITION_FIELDS
        ):
            raise RuntimeKnowledgeSelectionError(
                "RUNTIME_PACKAGING_REPORT_PARTITION_MISMATCH"
            )
        identities = set(snapshot.package_identities)
        if len({item.runtime_package_uuid for item in clean.runtime_packages}) != len(
            clean.runtime_packages
        ):
            raise RuntimeKnowledgeSelectionError(
                "RUNTIME_PACKAGING_REPORT_PACKAGE_SET_MISMATCH"
            )
        for package in clean.runtime_packages:
            if (
                by_package.get(package.runtime_package_uuid) != package
                or (package.runtime_package_uuid, package.runtime_package_digest)
                not in identities
            ):
                raise RuntimeKnowledgeSelectionError(
                    "RUNTIME_PACKAGING_REPORT_PACKAGE_SET_MISMATCH"
                )
            if (
                package.runtime_package_state != PACKAGE_STATE
                or package.runtime_package_reasons != PACKAGE_REASONS
            ):
                raise RuntimeKnowledgeSelectionError("BROKEN_RUNTIME_PACKAGING_REPORT")
        fields = self._source_fields(
            "RUNTIME_KNOWLEDGE_PACKAGING_REPORT",
            report=(clean.report_uuid, runtime_digest(clean.to_dict())),
        )
        return clean.runtime_packages, snapshot, fields, clean.generated_at

    def _validate_runtime_repository(self):
        try:
            self.runtime_repository.latest_snapshot()
        except RuntimeKnowledgeError as exc:
            raise RuntimeKnowledgeSelectionError(
                "BROKEN_RUNTIME_PACKAGE_PROVENANCE"
            ) from exc

    @staticmethod
    def _verify_report_counters(report):
        packages = tuple(report.runtime_packages)
        if (
            report.processed_record_count != len(packages)
            or report.new_package_count + report.duplicate_package_count
            != len(packages)
            or report.advisory_package_prepared_count
            != sum(item.runtime_package_state == PACKAGE_STATE for item in packages)
        ):
            raise RuntimeKnowledgeSelectionError(
                "RUNTIME_PACKAGING_REPORT_COUNTER_MISMATCH"
            )

    @staticmethod
    def _ordered_snapshots(snapshots):
        if not snapshots:
            raise RuntimeKnowledgeSelectionError("BROKEN_RUNTIME_PACKAGE_PROVENANCE")
        by_uuid = {item.snapshot_uuid: item for item in snapshots}
        children = {}
        roots = []
        for item in snapshots:
            if item.previous_snapshot_uuid is None:
                roots.append(item)
            elif item.previous_snapshot_uuid in children:
                raise RuntimeKnowledgeSelectionError(
                    "BROKEN_RUNTIME_PACKAGE_PROVENANCE"
                )
            else:
                children[item.previous_snapshot_uuid] = item
        if len(by_uuid) != len(snapshots) or len(roots) != 1:
            raise RuntimeKnowledgeSelectionError("BROKEN_RUNTIME_PACKAGE_PROVENANCE")
        ordered = []
        current = roots[0]
        while current is not None:
            ordered.append(current)
            current = children.get(current.snapshot_uuid)
        if len(ordered) != len(snapshots):
            raise RuntimeKnowledgeSelectionError("BROKEN_RUNTIME_PACKAGE_PROVENANCE")
        return tuple(ordered)

    @staticmethod
    def _earliest_membership(package, snapshots):
        identity = (package.runtime_package_uuid, package.runtime_package_digest)
        matches = [
            snapshot
            for snapshot in snapshots
            if identity in snapshot.package_identities
        ]
        if not matches:
            raise RuntimeKnowledgeSelectionError(
                "RUNTIME_PACKAGE_SNAPSHOT_MEMBERSHIP_MISSING"
            )
        return matches[0]

    @staticmethod
    def _packages_for_snapshot(snapshot, by_package):
        selected = []
        for identity, content_digest in snapshot.package_identities:
            package = by_package.get(identity)
            if package is None or package.runtime_package_digest != content_digest:
                raise RuntimeKnowledgeSelectionError(
                    "RUNTIME_PACKAGING_REPORT_PACKAGE_SET_MISMATCH"
                )
            selected.append(package)
        return tuple(selected)

    @staticmethod
    def _source_fields(artifact_type, package=None, report=None):
        return {
            "source_artifact_type": artifact_type,
            "source_runtime_package_uuid": package[0] if package else None,
            "source_runtime_package_digest": package[1] if package else None,
            "source_runtime_packaging_report_uuid": report[0] if report else None,
            "source_runtime_packaging_report_digest": report[1] if report else None,
        }

    def _partition(self, packages, snapshot):
        if not packages:
            raise RuntimeKnowledgeSelectionError(
                "RUNTIME_PACKAGING_REPORT_PACKAGE_SET_MISMATCH"
            )
        first = packages[0]
        partition = {
            "selector_version": self.policy.runtime_selector_version,
            "selection_policy_uuid": self.policy.selection_policy_uuid,
            "selection_policy_digest": self.policy.selection_policy_digest,
            "selection_policy_version": self.policy.selection_policy_version,
            "source_runtime_engine_version": first.runtime_engine_version,
            "source_runtime_packaging_policy_uuid": first.runtime_packaging_policy_uuid,
            "source_runtime_packaging_policy_digest": first.runtime_packaging_policy_digest,
            "source_runtime_packaging_policy_version": first.runtime_packaging_policy_version,
            "source_registry_engine_version": first.source_registry_engine_version,
            "source_registry_admission_policy_uuid": first.source_registry_admission_policy_uuid,
            "source_registry_admission_policy_digest": first.source_registry_admission_policy_digest,
            "source_registry_admission_policy_version": first.source_registry_admission_policy_version,
            "source_promotion_engine_version": first.source_promotion_engine_version,
            "source_promotion_policy_uuid": first.source_promotion_policy_uuid,
            "source_promotion_policy_digest": first.source_promotion_policy_digest,
            "source_promotion_policy_version": first.source_promotion_policy_version,
            "source_validator_version": first.source_validator_version,
            "source_validation_policy_version": first.source_validation_policy_version,
            "source_validation_config_digest": first.source_validation_config_digest,
            "source_mining_engine_version": first.source_engine_version,
            "source_mining_policy_uuid": first.source_policy_uuid,
            "source_mining_policy_version": first.source_policy_version,
            "source_mining_config_digest": first.mining_config_digest,
        }
        if any(
            tuple(self._package_partition(item)[name] for name in PARTITION_FIELDS[4:])
            != tuple(partition[name] for name in PARTITION_FIELDS[4:])
            for item in packages
        ):
            raise RuntimeKnowledgeSelectionError("MIXED_RUNTIME_KNOWLEDGE_PARTITION")
        if tuple(getattr(snapshot, name) for name in PR180_PARTITION_FIELDS) != tuple(
            partition[self._source_name(name)] for name in PR180_PARTITION_FIELDS
        ):
            raise RuntimeKnowledgeSelectionError(
                "RUNTIME_PACKAGING_REPORT_PARTITION_MISMATCH"
            )
        return partition

    @staticmethod
    def _source_name(name):
        if name == "runtime_engine_version":
            return "source_runtime_engine_version"
        if name == "runtime_packaging_policy_uuid":
            return "source_runtime_packaging_policy_uuid"
        if name == "runtime_packaging_policy_digest":
            return "source_runtime_packaging_policy_digest"
        if name == "runtime_packaging_policy_version":
            return "source_runtime_packaging_policy_version"
        return name

    @classmethod
    def _package_partition(cls, package):
        partition = {
            cls._source_name(name): getattr(package, name)
            for name in PR180_PARTITION_FIELDS
        }
        partition.update(
            source_validator_version=package.source_validator_version,
            source_validation_policy_version=package.source_validation_policy_version,
            source_validation_config_digest=package.source_validation_config_digest,
            source_mining_engine_version=package.source_engine_version,
            source_mining_policy_uuid=package.source_policy_uuid,
            source_mining_policy_version=package.source_policy_version,
            source_mining_config_digest=package.mining_config_digest,
        )
        return partition

    def _classify(self, package):
        hard = []
        insufficient = []
        if package.runtime_package_state != self.policy.required_runtime_package_state:
            hard.append("RUNTIME_PACKAGE_STATE_NOT_ELIGIBLE")
        if package.source_registry_state != self.policy.required_registry_state:
            hard.append("REGISTRY_STATE_NOT_ELIGIBLE")
        if package.source_validation_state != self.policy.required_validation_state:
            insufficient.append("VALIDATION_STATE_INSUFFICIENT")
        if package.source_promotion_state != self.policy.required_promotion_state:
            insufficient.append("PROMOTION_STATE_INSUFFICIENT")
        if hard:
            return "REJECTED", tuple(hard)
        if insufficient:
            return "INSUFFICIENT_SELECTION_EVIDENCE", tuple(insufficient)
        return ELIGIBLE, ("ELIGIBLE_FOR_PR182_CONFIDENCE_EVALUATION",)
