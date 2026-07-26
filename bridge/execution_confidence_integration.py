"""PR191 immutable production boundary between PR190 and the V26 runtime."""
from dataclasses import dataclass
from learning.execution_package import ExecutionPackage
from learning.execution_package_consumer import ExecutionPackageConsumer

class ExecutionConfidenceIntegrationError(ValueError):
    """A fail-closed execution-confidence integration failure."""

@dataclass(frozen=True)
class ExecutionConfidenceContext:
    """The complete, advisory-only governance input visible to V26."""
    execution_package_uuid: str
    execution_package_digest: str
    package_state: str
    package_reason: str
    execution_readiness: str
    environment_assessment: str
    feasibility_assessment: str
    package_policy_version: str
    package_engine_version: str
    package_created_at: str
    replay_identity: str
    advisory_only: bool = True

    def __post_init__(self):
        ready = self.package_state == "PACKAGE_READY"
        expected = (("EXECUTION_READY_FOR_ENVIRONMENT_CHECK", "ENVIRONMENT_READY_FOR_FEASIBILITY",
                     "EXECUTION_FEASIBLE") if ready else ("NOT_CONFIRMED_BY_PACKAGE",) * 3)
        actual = (self.execution_readiness, self.environment_assessment, self.feasibility_assessment)
        if actual != expected or self.advisory_only is not True or self.replay_identity != self.execution_package_uuid:
            raise ExecutionConfidenceIntegrationError("INVALID_CONFIDENCE_CONTEXT")

    def to_v26_inputs(self):
        """Return fresh metadata; neither the context nor package is exposed."""
        return {"execution_package_uuid": self.execution_package_uuid,
                "execution_package_digest": self.execution_package_digest,
                "execution_package_state": self.package_state,
                "execution_package_reason": self.package_reason,
                "execution_readiness": self.execution_readiness,
                "execution_environment_assessment": self.environment_assessment,
                "execution_feasibility_assessment": self.feasibility_assessment,
                "execution_package_policy_version": self.package_policy_version,
                "execution_package_engine_version": self.package_engine_version,
                "execution_package_created_at": self.package_created_at,
                "execution_package_replay_identity": self.replay_identity,
                "execution_governance_advisory_only": True}

class ExecutionConfidenceIntegration:
    """Load one immutable package through PR190 and project V26 inputs."""
    def __init__(self, consumer):
        if type(consumer) is not ExecutionPackageConsumer:
            raise ExecutionConfidenceIntegrationError("CONSUMER_FAILURE")
        self._consumer = consumer

    def consume(self, package_uuid):
        try:
            package = self._consumer.load(package_uuid)
        except Exception as exc:
            raise ExecutionConfidenceIntegrationError("PACKAGE_REJECTED") from exc
        if type(package) is not ExecutionPackage or package.advisory_only is not True:
            raise ExecutionConfidenceIntegrationError("INVALID_PACKAGE")
        ready = package.package_state == "PACKAGE_READY"
        return ExecutionConfidenceContext(
            package.execution_package_uuid, package.execution_package_digest,
            package.package_state, package.package_reason,
            "EXECUTION_READY_FOR_ENVIRONMENT_CHECK" if ready else "NOT_CONFIRMED_BY_PACKAGE",
            "ENVIRONMENT_READY_FOR_FEASIBILITY" if ready else "NOT_CONFIRMED_BY_PACKAGE",
            "EXECUTION_FEASIBLE" if ready else "NOT_CONFIRMED_BY_PACKAGE",
            package.package_policy_version, package.package_engine_version,
            package.created_at, package.execution_package_uuid)
