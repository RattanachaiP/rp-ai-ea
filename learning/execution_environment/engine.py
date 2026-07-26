"""Governed PR187 evaluation of explicit environment evidence; advisory only."""

from learning.execution_readiness import (
    ExecutionReadiness,
    ExecutionReadinessReport,
    ExecutionReadinessSnapshot,
    ExecutionReadinessRepository,
)
from learning.execution_readiness.identity import (
    digest as readiness_digest,
    report_uuid as readiness_report_uuid,
)
from learning.execution_readiness.exceptions import ExecutionReadinessError
from learning.pattern_memory.models import valid_digest, valid_uuid
from .exceptions import ExecutionEnvironmentError
from .models import (
    AUTHORITY_SCOPE,
    ExecutionEnvironment,
    ExecutionEnvironmentReport,
    ExecutionEnvironmentSnapshot,
)
from .policy import ENVIRONMENT_DIMENSIONS, ExecutionEnvironmentPolicy
from .repository import (
    ExecutionEnvironmentEvidenceRepository,
    ExecutionEnvironmentRepository,
)


class GovernedExecutionEnvironmentEngine:
    def __init__(
        self,
        readiness_repository=None,
        repository=None,
        policy=None,
        evidence_repository=None,
    ):
        self.readiness_repository = (
            readiness_repository or ExecutionReadinessRepository()
        )
        self.repository = repository or ExecutionEnvironmentRepository()
        self.policy = policy or ExecutionEnvironmentPolicy()
        self.evidence_repository = (
            evidence_repository or ExecutionEnvironmentEvidenceRepository()
        )
        if type(self.readiness_repository) is not ExecutionReadinessRepository:
            raise ExecutionEnvironmentError("INVALID_EXECUTION_READINESS")
        if (
            type(self.repository) is not ExecutionEnvironmentRepository
            or type(self.evidence_repository)
            is not ExecutionEnvironmentEvidenceRepository
        ):
            raise ExecutionEnvironmentError("REPOSITORY_MISMATCH")
        if type(self.policy) is not ExecutionEnvironmentPolicy:
            raise ExecutionEnvironmentError("POLICY_MISMATCH")

    def construct_environment(self, source):
        if type(source) not in (
            ExecutionReadiness,
            ExecutionReadinessReport,
            ExecutionReadinessSnapshot,
        ):
            raise ExecutionEnvironmentError("INVALID_EXECUTION_READINESS")
        records, snapshot, generated_at = self._verify(source)
        self._verify_partition(records, snapshot)
        existing = {x.execution_environment_uuid: x for x in self.repository.records()}
        output = []
        duplicates = 0
        for stored in existing.values():
            self._verify_stored_partition(stored)
        for readiness in sorted(records, key=lambda x: x.execution_readiness_uuid):
            evidence = self.evidence_repository.for_readiness(readiness)
            self._verify_evidence_partition(evidence, readiness, snapshot)
            state, reason, profile, quality = self._evaluate(readiness, evidence)
            item = ExecutionEnvironment.create(
                execution_readiness_uuid=readiness.execution_readiness_uuid,
                execution_readiness_digest=readiness.execution_readiness_digest,
                readiness_state=readiness.readiness_state,
                evidence_uuid=evidence.evidence_uuid if evidence else None,
                evidence_digest=evidence.evidence_digest if evidence else None,
                environment_evidence_complete=bool(
                    evidence
                    and len(evidence.observations) == len(ENVIRONMENT_DIMENSIONS)
                ),
                environment_state=state,
                environment_reason=reason,
                environment_profile=profile,
                environment_quality=quality,
                readiness_snapshot_uuid=snapshot.snapshot_uuid,
                readiness_snapshot_digest=snapshot.snapshot_digest,
                readiness_repository_digest=snapshot.repository_digest,
                environment_policy=self.policy.to_dict(),
                environment_policy_uuid=self.policy.environment_policy_uuid,
                environment_policy_digest=self.policy.environment_policy_digest,
                environment_policy_version=self.policy.environment_policy_version,
                environment_engine_version=self.policy.environment_engine_version,
                created_at=evidence.captured_at if evidence else readiness.created_at,
                authority_scope=AUTHORITY_SCOPE,
                advisory_only=True,
            )
            prior = existing.get(item.execution_environment_uuid)
            if prior is not None:
                if prior != item:
                    raise ExecutionEnvironmentError("REPLAY_COLLISION")
                item = prior
                duplicates += 1
            else:
                self.repository.save(item)
                existing[item.execution_environment_uuid] = item
            output.append(item)
        ids = self.repository.identities()
        repo_digest = self.repository.digest()
        previous = self.repository.latest_snapshot()
        values = dict(
            environment_identities=ids,
            record_count=len(ids),
            repository_digest=repo_digest,
            environment_policy_uuid=self.policy.environment_policy_uuid,
            environment_policy_digest=self.policy.environment_policy_digest,
            environment_policy_version=self.policy.environment_policy_version,
            environment_engine_version=self.policy.environment_engine_version,
            readiness_policy_uuid=snapshot.readiness_policy_uuid,
            readiness_policy_digest=snapshot.readiness_policy_digest,
            readiness_policy_version=snapshot.readiness_policy_version,
            readiness_engine_version=snapshot.readiness_engine_version,
            authority_scope=AUTHORITY_SCOPE,
            advisory_only=True,
        )
        if previous and all(getattr(previous, k) == v for k, v in values.items()):
            out_snapshot = previous
        else:
            out_snapshot = ExecutionEnvironmentSnapshot.create(
                **values,
                previous_snapshot_uuid=previous.snapshot_uuid if previous else None,
                previous_snapshot_digest=previous.snapshot_digest if previous else None,
                generated_at=generated_at
            )
            self.repository.save_snapshot(out_snapshot)
        return ExecutionEnvironmentReport.create(
            execution_environment_records=tuple(output),
            processed_count=len(output),
            ready_count=sum(
                x.environment_state == "ENVIRONMENT_READY_FOR_FEASIBILITY"
                for x in output
            ),
            insufficient_count=sum(
                x.environment_state == "INSUFFICIENT_ENVIRONMENT_INFORMATION"
                for x in output
            ),
            rejected_count=sum(x.environment_state == "REJECTED" for x in output),
            duplicate_count=duplicates,
            repository_digest=repo_digest,
            snapshot_uuid=out_snapshot.snapshot_uuid,
            snapshot_digest=out_snapshot.snapshot_digest,
            generated_at=generated_at,
            advisory_only=True,
        )

    evaluate_environment = construct_environment
    run = construct_environment

    def _evaluate(self, readiness, evidence):
        values = dict(evidence.observations) if evidence else {}
        profile = tuple(
            (
                d,
                (
                    "AVAILABLE"
                    if d in values and self.policy.available(d, values[d])
                    else "UNAVAILABLE"
                ),
            )
            for d in ENVIRONMENT_DIMENSIONS
        )
        quality = float(sum(v == "AVAILABLE" for _, v in profile) / len(profile))
        if readiness.readiness_state == "REJECTED":
            return "REJECTED", "READINESS_REJECTED", profile, quality
        if (
            evidence is not None
            and len(evidence.observations) == len(ENVIRONMENT_DIMENSIONS)
            and quality >= self.policy.minimum_quality
        ):
            return (
                "ENVIRONMENT_READY_FOR_FEASIBILITY",
                "ENVIRONMENT_QUALITY_SUFFICIENT",
                profile,
                quality,
            )
        return (
            "INSUFFICIENT_ENVIRONMENT_INFORMATION",
            "ENVIRONMENT_EVIDENCE_INSUFFICIENT",
            profile,
            quality,
        )

    def _verify_stored_partition(self, item):
        if item.environment_engine_version != self.policy.environment_engine_version:
            raise ExecutionEnvironmentError("ENGINE_VERSION_MISMATCH")
        if (
            item.environment_policy_uuid,
            item.environment_policy_digest,
            item.environment_policy_version,
        ) != (
            self.policy.environment_policy_uuid,
            self.policy.environment_policy_digest,
            self.policy.environment_policy_version,
        ):
            raise ExecutionEnvironmentError("POLICY_MISMATCH")

    def _verify_evidence_partition(self, evidence, readiness, snapshot):
        if evidence is None:
            return
        if (
            evidence.readiness_snapshot_uuid,
            evidence.readiness_snapshot_digest,
            evidence.readiness_repository_digest,
        ) != (
            snapshot.snapshot_uuid,
            snapshot.snapshot_digest,
            snapshot.repository_digest,
        ):
            raise ExecutionEnvironmentError("SNAPSHOT_MISMATCH")
        expected = (
            snapshot.readiness_policy_uuid,
            snapshot.readiness_policy_digest,
            snapshot.readiness_policy_version,
            snapshot.readiness_engine_version,
        )
        actual = (
            evidence.readiness_policy_uuid,
            evidence.readiness_policy_digest,
            evidence.readiness_policy_version,
            evidence.readiness_engine_version,
        )
        if actual[3] != expected[3]:
            raise ExecutionEnvironmentError("ENGINE_VERSION_MISMATCH")
        if actual != expected:
            raise ExecutionEnvironmentError("POLICY_MISMATCH")

    @staticmethod
    def _verify_partition(records, snapshot):
        if not records:
            raise ExecutionEnvironmentError("INVALID_EXECUTION_READINESS")
        expected = (
            snapshot.readiness_policy_uuid,
            snapshot.readiness_policy_digest,
            snapshot.readiness_policy_version,
            snapshot.readiness_engine_version,
        )
        if not valid_uuid(expected[0]) or not valid_digest(expected[1]):
            raise ExecutionEnvironmentError("POLICY_MISMATCH")
        for x in records:
            actual = (
                x.readiness_policy_uuid,
                x.readiness_policy_digest,
                x.readiness_policy_version,
                x.readiness_engine_version,
            )
            if actual[3] != expected[3]:
                raise ExecutionEnvironmentError("ENGINE_VERSION_MISMATCH")
            if actual != expected:
                raise ExecutionEnvironmentError("POLICY_MISMATCH")

    def _verify(self, source):
        try:
            records = self.readiness_repository.records()
            snapshots = self.readiness_repository.snapshots()
            latest = self.readiness_repository.latest_snapshot()
        except (ExecutionReadinessError, ValueError, OSError) as exc:
            raise ExecutionEnvironmentError("BROKEN_PROVENANCE") from exc
        if latest is None:
            raise ExecutionEnvironmentError("BROKEN_PROVENANCE")
        by_record = {x.execution_readiness_uuid: x for x in records}
        by_snapshot = {x.snapshot_uuid: x for x in snapshots}

        def verify(item):
            try:
                valid = (
                    readiness_digest(item.digest_payload())
                    == item.execution_readiness_digest
                )
            except Exception:
                valid = False
            if by_record.get(item.execution_readiness_uuid) != item or not valid:
                raise ExecutionEnvironmentError("BROKEN_PROVENANCE")

        if type(source) is ExecutionReadiness:
            verify(source)
            if (
                source.execution_readiness_uuid,
                source.execution_readiness_digest,
            ) not in latest.readiness_identities:
                raise ExecutionEnvironmentError("SNAPSHOT_MISMATCH")
            return (source,), latest, source.created_at
        if type(source) is ExecutionReadinessSnapshot:
            snapshot = by_snapshot.get(source.snapshot_uuid)
            if snapshot != source:
                raise ExecutionEnvironmentError("SNAPSHOT_MISMATCH")
            selected = []
            for uid, dgst in snapshot.readiness_identities:
                item = by_record.get(uid)
                if item is None or item.execution_readiness_digest != dgst:
                    raise ExecutionEnvironmentError("SNAPSHOT_MISMATCH")
                selected.append(item)
            return tuple(selected), snapshot, source.generated_at
        snapshot = by_snapshot.get(source.snapshot_uuid)
        if snapshot is None or snapshot.snapshot_digest != source.snapshot_digest:
            raise ExecutionEnvironmentError("SNAPSHOT_MISMATCH")
        if source.repository_digest != snapshot.repository_digest:
            raise ExecutionEnvironmentError("REPOSITORY_MISMATCH")
        try:
            valid = (
                readiness_report_uuid(source.identity_payload()) == source.report_uuid
                and readiness_digest(source.digest_payload()) == source.report_digest
            )
        except Exception:
            valid = False
        if not valid:
            raise ExecutionEnvironmentError("BROKEN_PROVENANCE")
        identities = set(snapshot.readiness_identities)
        for item in source.execution_readiness_records:
            verify(item)
            if (
                item.execution_readiness_uuid,
                item.execution_readiness_digest,
            ) not in identities:
                raise ExecutionEnvironmentError("SNAPSHOT_MISMATCH")
        return source.execution_readiness_records, snapshot, source.generated_at


GovernedAdvisoryExecutionEnvironmentEngine = GovernedExecutionEnvironmentEngine
