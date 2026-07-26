"""Deterministic PR188 advisory feasibility evaluation; never execution authority."""

from learning.execution_readiness import ExecutionReadiness, ExecutionReadinessRepository
from learning.execution_environment import ExecutionEnvironment, ExecutionEnvironmentRepository
from learning.execution_readiness.exceptions import ExecutionReadinessError
from learning.execution_environment.exceptions import ExecutionEnvironmentError
from .exceptions import ExecutionFeasibilityError
from .models import AUTHORITY_SCOPE, ExecutionFeasibilityRecord, ExecutionFeasibilityReport, ExecutionFeasibilitySnapshot
from .policy import FEASIBILITY_DIMENSIONS, ExecutionFeasibilityPolicy
from .repository import ExecutionFeasibilityRepository


class GovernedExecutionFeasibilityEngine:
    def __init__(self, readiness_repository=None, environment_repository=None, repository=None, policy=None):
        self.readiness_repository = readiness_repository or ExecutionReadinessRepository()
        self.environment_repository = environment_repository or ExecutionEnvironmentRepository()
        self.repository = repository or ExecutionFeasibilityRepository()
        self.policy = policy or ExecutionFeasibilityPolicy()
        if type(self.readiness_repository) is not ExecutionReadinessRepository:
            raise ExecutionFeasibilityError("INVALID_READINESS")
        if type(self.environment_repository) is not ExecutionEnvironmentRepository:
            raise ExecutionFeasibilityError("INVALID_ENVIRONMENT")
        if type(self.repository) is not ExecutionFeasibilityRepository:
            raise ExecutionFeasibilityError("REPOSITORY_MISMATCH")
        if type(self.policy) is not ExecutionFeasibilityPolicy:
            raise ExecutionFeasibilityError("POLICY_MISMATCH")

    def evaluate_feasibility(self, readiness, environment):
        if type(readiness) is not ExecutionReadiness:
            raise ExecutionFeasibilityError("INVALID_READINESS")
        if type(environment) is not ExecutionEnvironment:
            raise ExecutionFeasibilityError("INVALID_ENVIRONMENT")
        readiness_snapshot = self._verify_readiness(readiness)
        environment_snapshot = self._verify_environment(environment)
        self._verify_lineage(readiness, environment, readiness_snapshot, environment_snapshot)
        for stored in self.repository.records():
            self._verify_stored_partition(stored)

        rejected = readiness.readiness_state == "REJECTED" or environment.environment_state == "REJECTED"
        sufficient = (readiness.readiness_state == "EXECUTION_READY_FOR_ENVIRONMENT_CHECK" and
                      environment.environment_state == "ENVIRONMENT_READY_FOR_FEASIBILITY")
        status = "REJECTED" if rejected else ("SATISFIED" if sufficient else "INSUFFICIENT")
        dimensions = tuple((name, status) for name in FEASIBILITY_DIMENSIONS)
        record = ExecutionFeasibilityRecord.create(
            execution_readiness_uuid=readiness.execution_readiness_uuid,
            execution_readiness_digest=readiness.execution_readiness_digest,
            execution_environment_uuid=environment.execution_environment_uuid,
            execution_environment_digest=environment.execution_environment_digest,
            feasibility_state=("REJECTED" if rejected else "EXECUTION_FEASIBLE" if sufficient else "INSUFFICIENT_EXECUTION_FEASIBILITY"),
            feasibility_reason=("UPSTREAM_REJECTED" if rejected else "ALL_ADVISORY_PREREQUISITES_SATISFIED" if sufficient else "ADVISORY_PREREQUISITES_INSUFFICIENT"),
            feasibility_dimensions=dimensions,
            readiness_snapshot_uuid=readiness_snapshot.snapshot_uuid,
            readiness_snapshot_digest=readiness_snapshot.snapshot_digest,
            readiness_repository_digest=readiness_snapshot.repository_digest,
            environment_snapshot_uuid=environment_snapshot.snapshot_uuid,
            environment_snapshot_digest=environment_snapshot.snapshot_digest,
            environment_repository_digest=environment_snapshot.repository_digest,
            readiness_policy_uuid=readiness.readiness_policy_uuid,
            readiness_policy_digest=readiness.readiness_policy_digest,
            readiness_policy_version=readiness.readiness_policy_version,
            readiness_engine_version=readiness.readiness_engine_version,
            environment_policy_uuid=environment.environment_policy_uuid,
            environment_policy_digest=environment.environment_policy_digest,
            environment_policy_version=environment.environment_policy_version,
            environment_engine_version=environment.environment_engine_version,
            feasibility_policy_uuid=self.policy.feasibility_policy_uuid,
            feasibility_policy_digest=self.policy.feasibility_policy_digest,
            feasibility_policy_version=self.policy.feasibility_policy_version,
            feasibility_engine_version=self.policy.feasibility_engine_version,
            created_at=environment.created_at, authority_scope=AUTHORITY_SCOPE, advisory_only=True)
        existing = {x.execution_feasibility_uuid: x for x in self.repository.records()}
        duplicate = record.execution_feasibility_uuid in existing
        if duplicate:
            if existing[record.execution_feasibility_uuid] != record:
                raise ExecutionFeasibilityError("REPLAY_COLLISION")
            record = existing[record.execution_feasibility_uuid]
        else:
            self.repository.save(record)

        identities, repository_digest = self.repository.identities(), self.repository.digest()
        previous = self.repository.latest_snapshot()
        values = dict(feasibility_identities=identities, record_count=len(identities), repository_digest=repository_digest,
                      feasibility_policy_uuid=self.policy.feasibility_policy_uuid,
                      feasibility_policy_digest=self.policy.feasibility_policy_digest,
                      feasibility_policy_version=self.policy.feasibility_policy_version,
                      feasibility_engine_version=self.policy.feasibility_engine_version, advisory_only=True)
        if previous and all(getattr(previous, k) == v for k, v in values.items()):
            snapshot = previous
        else:
            snapshot = ExecutionFeasibilitySnapshot.create(**values,
                previous_snapshot_uuid=previous.snapshot_uuid if previous else None,
                previous_snapshot_digest=previous.snapshot_digest if previous else None,
                generated_at=environment.created_at)
            self.repository.save_snapshot(snapshot)
        return ExecutionFeasibilityReport.create(
            execution_feasibility_records=(record,), processed_count=1,
            feasible_count=int(record.feasibility_state == "EXECUTION_FEASIBLE"),
            insufficient_count=int(record.feasibility_state == "INSUFFICIENT_EXECUTION_FEASIBILITY"),
            rejected_count=int(record.feasibility_state == "REJECTED"), duplicate_count=int(duplicate),
            repository_digest=repository_digest, snapshot_uuid=snapshot.snapshot_uuid,
            snapshot_digest=snapshot.snapshot_digest, generated_at=environment.created_at, advisory_only=True)

    construct_feasibility = evaluate_feasibility
    run = evaluate_feasibility

    def _verify_stored_partition(self, record):
        if record.feasibility_engine_version != self.policy.feasibility_engine_version:
            raise ExecutionFeasibilityError("ENGINE_VERSION_MISMATCH")
        if (record.feasibility_policy_uuid, record.feasibility_policy_digest, record.feasibility_policy_version) != (
            self.policy.feasibility_policy_uuid, self.policy.feasibility_policy_digest, self.policy.feasibility_policy_version):
            raise ExecutionFeasibilityError("POLICY_MISMATCH")

    def _verify_readiness(self, record):
        try:
            records = self.readiness_repository.records()
            snapshot = self.readiness_repository.latest_snapshot()
        except (ExecutionReadinessError, ValueError, OSError) as exc:
            raise ExecutionFeasibilityError("BROKEN_PROVENANCE") from exc
        if snapshot is None or record not in records:
            raise ExecutionFeasibilityError("BROKEN_PROVENANCE")
        if (record.execution_readiness_uuid, record.execution_readiness_digest) not in snapshot.readiness_identities:
            raise ExecutionFeasibilityError("SNAPSHOT_MISMATCH")
        return snapshot

    def _verify_environment(self, record):
        try:
            records = self.environment_repository.records()
            snapshot = self.environment_repository.latest_snapshot()
        except (ExecutionEnvironmentError, ValueError, OSError) as exc:
            raise ExecutionFeasibilityError("BROKEN_PROVENANCE") from exc
        if snapshot is None or record not in records:
            raise ExecutionFeasibilityError("BROKEN_PROVENANCE")
        if (record.execution_environment_uuid, record.execution_environment_digest) not in snapshot.environment_identities:
            raise ExecutionFeasibilityError("SNAPSHOT_MISMATCH")
        return snapshot

    @staticmethod
    def _verify_lineage(readiness, environment, readiness_snapshot, environment_snapshot):
        if (environment.execution_readiness_uuid, environment.execution_readiness_digest) != (
            readiness.execution_readiness_uuid, readiness.execution_readiness_digest):
            raise ExecutionFeasibilityError("BROKEN_PROVENANCE")
        if (environment.readiness_snapshot_uuid, environment.readiness_snapshot_digest,
            environment.readiness_repository_digest) != (readiness_snapshot.snapshot_uuid,
            readiness_snapshot.snapshot_digest, readiness_snapshot.repository_digest):
            raise ExecutionFeasibilityError("SNAPSHOT_MISMATCH")
        expected = (readiness.readiness_policy_uuid, readiness.readiness_policy_digest,
                    readiness.readiness_policy_version, readiness.readiness_engine_version)
        actual = (environment_snapshot.readiness_policy_uuid, environment_snapshot.readiness_policy_digest,
                  environment_snapshot.readiness_policy_version, environment_snapshot.readiness_engine_version)
        if actual[3] != expected[3]:
            raise ExecutionFeasibilityError("ENGINE_VERSION_MISMATCH")
        if actual != expected:
            raise ExecutionFeasibilityError("POLICY_MISMATCH")


GovernedAdvisoryExecutionFeasibilityEngine = GovernedExecutionFeasibilityEngine
