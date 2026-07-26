"""PR189 deterministic assembly of already-validated advisory artifacts."""

from learning.execution_readiness import ExecutionReadiness, ExecutionReadinessRepository
from learning.execution_environment import ExecutionEnvironment, ExecutionEnvironmentRepository
from learning.execution_feasibility import ExecutionFeasibility, ExecutionFeasibilityRepository
from .exceptions import ExecutionPackageError
from .identity import digest
from .models import AUTHORITY_SCOPE, ExecutionPackage, ExecutionPackageReport, ExecutionPackageSnapshot
from .policy import ExecutionPackagePolicy
from .repository import ExecutionPackageRepository


class GovernedExecutionPackageAssemblyEngine:
    def __init__(self, readiness_repository=None, environment_repository=None,
                 feasibility_repository=None, repository=None, policy=None):
        self.readiness_repository = readiness_repository or ExecutionReadinessRepository()
        self.environment_repository = environment_repository or ExecutionEnvironmentRepository()
        self.feasibility_repository = feasibility_repository or ExecutionFeasibilityRepository()
        self.repository = repository or ExecutionPackageRepository()
        self.policy = policy or ExecutionPackagePolicy()
        expected = ((self.readiness_repository, ExecutionReadinessRepository, "INVALID_READINESS"),
                    (self.environment_repository, ExecutionEnvironmentRepository, "INVALID_ENVIRONMENT"),
                    (self.feasibility_repository, ExecutionFeasibilityRepository, "INVALID_FEASIBILITY"),
                    (self.repository, ExecutionPackageRepository, "REPOSITORY_MISMATCH"),
                    (self.policy, ExecutionPackagePolicy, "POLICY_MISMATCH"))
        for value, kind, reason in expected:
            if type(value) is not kind:
                raise ExecutionPackageError(reason)

    def assemble(self, readiness, environment, feasibility):
        if type(readiness) is not ExecutionReadiness:
            raise ExecutionPackageError("INVALID_READINESS")
        if type(environment) is not ExecutionEnvironment:
            raise ExecutionPackageError("INVALID_ENVIRONMENT")
        if type(feasibility) is not ExecutionFeasibility:
            raise ExecutionPackageError("INVALID_FEASIBILITY")
        readiness_snapshot = self._verify_source(self.readiness_repository, readiness,
            "readiness_identities", readiness.execution_readiness_uuid, readiness.execution_readiness_digest)
        environment_snapshot = self._verify_source(self.environment_repository, environment,
            "environment_identities", environment.execution_environment_uuid, environment.execution_environment_digest)
        feasibility_snapshot = self._verify_source(self.feasibility_repository, feasibility,
            "feasibility_identities", feasibility.execution_feasibility_uuid, feasibility.execution_feasibility_digest)
        self._verify_lineage(readiness, environment, feasibility, readiness_snapshot,
                             environment_snapshot, feasibility_snapshot)
        for stored in self.repository.records():
            self._verify_package_partition(stored)
        self.repository.latest_snapshot()

        rejected = any(state == "REJECTED" for state in (
            readiness.readiness_state, environment.environment_state, feasibility.feasibility_state))
        complete = (readiness.readiness_state == "EXECUTION_READY_FOR_ENVIRONMENT_CHECK" and
                    environment.environment_state == "ENVIRONMENT_READY_FOR_FEASIBILITY" and
                    feasibility.feasibility_state == "EXECUTION_FEASIBLE")
        state = "REJECTED" if rejected else "PACKAGE_READY" if complete else "PACKAGE_INCOMPLETE"
        reason = {"REJECTED": "UPSTREAM_REJECTED", "PACKAGE_READY": "IMMUTABLE_ADVISORY_PACKAGE_ASSEMBLED",
                  "PACKAGE_INCOMPLETE": "UPSTREAM_ARTIFACTS_INCOMPLETE"}[state]
        chain_digest = digest([
            [readiness_snapshot.snapshot_uuid, readiness_snapshot.snapshot_digest],
            [environment_snapshot.snapshot_uuid, environment_snapshot.snapshot_digest],
            [feasibility_snapshot.snapshot_uuid, feasibility_snapshot.snapshot_digest],
        ])
        source_repository_digest = digest([
            readiness_snapshot.repository_digest, environment_snapshot.repository_digest,
            feasibility_snapshot.repository_digest,
        ])
        package = ExecutionPackage.create(
            execution_readiness_uuid=readiness.execution_readiness_uuid,
            execution_readiness_digest=readiness.execution_readiness_digest,
            execution_environment_uuid=environment.execution_environment_uuid,
            execution_environment_digest=environment.execution_environment_digest,
            execution_feasibility_uuid=feasibility.execution_feasibility_uuid,
            execution_feasibility_digest=feasibility.execution_feasibility_digest,
            snapshot_chain_digest=chain_digest, repository_digest=source_repository_digest,
            policy_digest=self.policy.package_policy_digest,
            engine_versions=(("readiness", readiness.readiness_engine_version),
                             ("environment", environment.environment_engine_version),
                             ("feasibility", feasibility.feasibility_engine_version),
                             ("package", self.policy.package_engine_version)),
            package_state=state, package_reason=reason, created_at=feasibility.created_at,
            package_policy_uuid=self.policy.package_policy_uuid,
            package_policy_version=self.policy.package_policy_version,
            package_engine_version=self.policy.package_engine_version,
            authority_scope=AUTHORITY_SCOPE, advisory_only=True)
        existing = {value.execution_package_uuid: value for value in self.repository.records()}
        duplicate = package.execution_package_uuid in existing
        if duplicate:
            if existing[package.execution_package_uuid] != package:
                raise ExecutionPackageError("REPLAY_COLLISION")
            package = existing[package.execution_package_uuid]
        else:
            self.repository.save(package)
        identities, repository_digest = self.repository.identities(), self.repository.digest()
        previous = self.repository.latest_snapshot()
        values = dict(package_identities=identities, record_count=len(identities), repository_digest=repository_digest,
                      package_policy_uuid=self.policy.package_policy_uuid,
                      package_policy_digest=self.policy.package_policy_digest,
                      package_policy_version=self.policy.package_policy_version,
                      package_engine_version=self.policy.package_engine_version, advisory_only=True)
        if previous and all(getattr(previous, name) == value for name, value in values.items()):
            snapshot = previous
        else:
            snapshot = ExecutionPackageSnapshot.create(**values,
                previous_snapshot_uuid=previous.snapshot_uuid if previous else None,
                previous_snapshot_digest=previous.snapshot_digest if previous else None,
                generated_at=feasibility.created_at)
            self.repository.save_snapshot(snapshot)
        report = ExecutionPackageReport.create(
            package_uuid=package.execution_package_uuid, package_digest=package.execution_package_digest,
            assembled_records=(("readiness", readiness.execution_readiness_uuid),
                               ("environment", environment.execution_environment_uuid),
                               ("feasibility", feasibility.execution_feasibility_uuid)),
            validation_status=state, repository_digest=repository_digest,
            snapshot_uuid=snapshot.snapshot_uuid, snapshot_digest=snapshot.snapshot_digest,
            generated_at=feasibility.created_at, duplicate=duplicate, advisory_only=True)
        return package, report

    run = assemble
    assemble_package = assemble

    @staticmethod
    def _verify_source(repository, record, identity_field, uid, dgst):
        try:
            records, snapshot = repository.records(), repository.latest_snapshot()
        except (ValueError, OSError) as exc:
            raise ExecutionPackageError("BROKEN_PROVENANCE") from exc
        if record not in records:
            raise ExecutionPackageError("BROKEN_PROVENANCE")
        if snapshot is None or (uid, dgst) not in getattr(snapshot, identity_field):
            raise ExecutionPackageError("SNAPSHOT_MISMATCH")
        return snapshot

    @staticmethod
    def _verify_lineage(readiness, environment, feasibility, readiness_snapshot,
                        environment_snapshot, feasibility_snapshot):
        if (environment.execution_readiness_uuid, environment.execution_readiness_digest) != (
                readiness.execution_readiness_uuid, readiness.execution_readiness_digest):
            raise ExecutionPackageError("BROKEN_PROVENANCE")
        if (feasibility.execution_readiness_uuid, feasibility.execution_readiness_digest,
            feasibility.execution_environment_uuid, feasibility.execution_environment_digest) != (
                readiness.execution_readiness_uuid, readiness.execution_readiness_digest,
                environment.execution_environment_uuid, environment.execution_environment_digest):
            raise ExecutionPackageError("BROKEN_PROVENANCE")
        if (environment.readiness_snapshot_uuid, environment.readiness_snapshot_digest,
            environment.readiness_repository_digest) != (readiness_snapshot.snapshot_uuid,
                readiness_snapshot.snapshot_digest, readiness_snapshot.repository_digest):
            raise ExecutionPackageError("SNAPSHOT_MISMATCH")
        if (feasibility.readiness_snapshot_uuid, feasibility.readiness_snapshot_digest,
            feasibility.readiness_repository_digest, feasibility.environment_snapshot_uuid,
            feasibility.environment_snapshot_digest, feasibility.environment_repository_digest) != (
                readiness_snapshot.snapshot_uuid, readiness_snapshot.snapshot_digest,
                readiness_snapshot.repository_digest, environment_snapshot.snapshot_uuid,
                environment_snapshot.snapshot_digest, environment_snapshot.repository_digest):
            raise ExecutionPackageError("SNAPSHOT_MISMATCH")
        partitions = (
            ((readiness.readiness_policy_uuid, readiness.readiness_policy_digest,
              readiness.readiness_policy_version, readiness.readiness_engine_version),
             (feasibility.readiness_policy_uuid, feasibility.readiness_policy_digest,
              feasibility.readiness_policy_version, feasibility.readiness_engine_version)),
            ((environment.environment_policy_uuid, environment.environment_policy_digest,
              environment.environment_policy_version, environment.environment_engine_version),
             (feasibility.environment_policy_uuid, feasibility.environment_policy_digest,
              feasibility.environment_policy_version, feasibility.environment_engine_version)),
            ((feasibility.feasibility_policy_uuid, feasibility.feasibility_policy_digest,
              feasibility.feasibility_policy_version, feasibility.feasibility_engine_version),
             (feasibility_snapshot.feasibility_policy_uuid, feasibility_snapshot.feasibility_policy_digest,
              feasibility_snapshot.feasibility_policy_version, feasibility_snapshot.feasibility_engine_version)),
        )
        for expected, actual in partitions:
            if expected[3] != actual[3]:
                raise ExecutionPackageError("ENGINE_VERSION_MISMATCH")
            if expected != actual:
                raise ExecutionPackageError("POLICY_MISMATCH")

    def _verify_package_partition(self, package):
        if package.package_engine_version != self.policy.package_engine_version:
            raise ExecutionPackageError("ENGINE_VERSION_MISMATCH")
        if (package.package_policy_uuid, package.policy_digest, package.package_policy_version) != (
                self.policy.package_policy_uuid, self.policy.package_policy_digest,
                self.policy.package_policy_version):
            raise ExecutionPackageError("POLICY_MISMATCH")


GovernedAdvisoryExecutionPackageAssemblyEngine = GovernedExecutionPackageAssemblyEngine
