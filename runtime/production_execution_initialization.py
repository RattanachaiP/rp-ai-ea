"""Production composition for PR186 through the PR208 Runtime bootstrap.

The operator supplies one exact, canonical PR185 recommendation identity and
the observed PR187 environment values.  Every downstream identity is derived
and persisted by its owning governed engine; this module never invents or
selects a downstream UUID.
"""

import argparse
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Optional, Sequence
from uuid import UUID

from learning.decision_recommendation import DecisionRecommendationRepository
from learning.execution_environment import (
    ExecutionEnvironmentEvidence,
    ExecutionEnvironmentEvidenceRepository,
    ExecutionEnvironmentRepository,
    GovernedExecutionEnvironmentEngine,
)
from learning.execution_environment.policy import ENVIRONMENT_DIMENSIONS
from learning.execution_feasibility import (
    ExecutionFeasibilityRepository,
    GovernedExecutionFeasibilityEngine,
)
from learning.execution_readiness import (
    ExecutionReadinessRepository,
    GovernedExecutionReadinessEngine,
)
from runtime.execution_package_bootstrap import (
    ExecutionPackageBootstrapConfiguration,
    ExecutionPackageRuntimeBootstrap,
)


class ProductionExecutionInitializationError(ValueError):
    """A terminal initialization failure; the Runtime has not been invoked."""


@dataclass(frozen=True)
class ProductionExecutionInitializationConfiguration:
    recommendation_uuid: str
    observations: tuple[tuple[str, float], ...]
    captured_at: str
    recommendation_root: Path = Path("learning_data/decision_recommendation")
    readiness_root: Path = Path("learning_data/execution_readiness")
    environment_root: Path = Path("learning_data/execution_environment")
    feasibility_root: Path = Path("learning_data/execution_feasibility")
    package_root: Path = Path("learning_data/execution_package")

    def __post_init__(self):
        try:
            canonical_uuid = (
                str(UUID(self.recommendation_uuid))
                if type(self.recommendation_uuid) is str
                else None
            )
        except (ValueError, AttributeError, TypeError):
            canonical_uuid = None
        if canonical_uuid != self.recommendation_uuid:
            raise ProductionExecutionInitializationError(
                "INVALID_RECOMMENDATION_UUID"
            )
        observations = tuple(tuple(item) for item in self.observations)
        object.__setattr__(self, "observations", observations)
        if (
            tuple(name for name, _ in observations) != ENVIRONMENT_DIMENSIONS
            or any(type(value) is not float for _, value in observations)
        ):
            raise ProductionExecutionInitializationError(
                "INVALID_ENVIRONMENT_OBSERVATIONS"
            )
        if type(self.captured_at) is not str or not self.captured_at:
            raise ProductionExecutionInitializationError("INVALID_CAPTURED_AT")
        roots = (
            self.recommendation_root,
            self.readiness_root,
            self.environment_root,
            self.feasibility_root,
            self.package_root,
        )
        if any(not isinstance(root, Path) for root in roots):
            raise ProductionExecutionInitializationError("INVALID_REPOSITORY_ROOT")


class ProductionExecutionInitializer:
    """Create governed PR186-PR188 records, then hand them to PR208."""

    def __init__(self, configuration: ProductionExecutionInitializationConfiguration):
        if type(configuration) is not ProductionExecutionInitializationConfiguration:
            raise ProductionExecutionInitializationError("INVALID_CONFIGURATION")
        self.configuration = configuration

    @staticmethod
    def _exact(records, expected_uuid):
        matches = tuple(
            record
            for record in records
            if record.recommendation_uuid == expected_uuid
        )
        if len(matches) != 1:
            raise ProductionExecutionInitializationError("RECOMMENDATION_MISSING")
        return matches[0]

    def start(self, runtime: Optional[Callable[[], object]] = None):
        """Run each owner once and invoke the Runtime only for a complete chain."""
        if runtime is not None and not callable(runtime):
            raise ProductionExecutionInitializationError("INVALID_RUNTIME")
        config = self.configuration
        try:
            recommendation_repository = DecisionRecommendationRepository(
                config.recommendation_root
            )
            recommendation = self._exact(
                recommendation_repository.records(), config.recommendation_uuid
            )

            readiness_repository = ExecutionReadinessRepository(config.readiness_root)
            readiness_report = GovernedExecutionReadinessEngine(
                recommendation_repository, readiness_repository
            ).run(recommendation)
            readiness = readiness_report.execution_readiness_records[0]
            if readiness.readiness_state != "EXECUTION_READY_FOR_ENVIRONMENT_CHECK":
                raise ProductionExecutionInitializationError("READINESS_NOT_READY")

            readiness_snapshot = readiness_repository.latest_snapshot()
            if readiness_snapshot is None:
                raise ProductionExecutionInitializationError("READINESS_SNAPSHOT_MISSING")
            evidence = ExecutionEnvironmentEvidence.create(
                execution_readiness_uuid=readiness.execution_readiness_uuid,
                execution_readiness_digest=readiness.execution_readiness_digest,
                observations=config.observations,
                captured_at=config.captured_at,
                readiness_snapshot_uuid=readiness_snapshot.snapshot_uuid,
                readiness_snapshot_digest=readiness_snapshot.snapshot_digest,
                readiness_repository_digest=readiness_snapshot.repository_digest,
                readiness_policy_uuid=readiness_snapshot.readiness_policy_uuid,
                readiness_policy_digest=readiness_snapshot.readiness_policy_digest,
                readiness_policy_version=readiness_snapshot.readiness_policy_version,
                readiness_engine_version=readiness_snapshot.readiness_engine_version,
                advisory_only=True,
            )
            evidence_repository = ExecutionEnvironmentEvidenceRepository(
                config.environment_root / "evidence"
            )
            evidence_repository.save(evidence)
            environment_repository = ExecutionEnvironmentRepository(
                config.environment_root
            )
            environment_report = GovernedExecutionEnvironmentEngine(
                readiness_repository,
                environment_repository,
                evidence_repository=evidence_repository,
            ).run(readiness)
            environment = environment_report.execution_environment_records[0]
            if environment.environment_state != "ENVIRONMENT_READY_FOR_FEASIBILITY":
                raise ProductionExecutionInitializationError("ENVIRONMENT_NOT_READY")

            feasibility_repository = ExecutionFeasibilityRepository(
                config.feasibility_root
            )
            feasibility_report = GovernedExecutionFeasibilityEngine(
                readiness_repository,
                environment_repository,
                feasibility_repository,
            ).run(readiness, environment)
            feasibility = feasibility_report.execution_feasibility_records[0]
            if feasibility.feasibility_state != "EXECUTION_FEASIBLE":
                raise ProductionExecutionInitializationError("EXECUTION_NOT_FEASIBLE")

            return ExecutionPackageRuntimeBootstrap(
                ExecutionPackageBootstrapConfiguration(
                    readiness_uuid=readiness.execution_readiness_uuid,
                    environment_uuid=environment.execution_environment_uuid,
                    feasibility_uuid=feasibility.execution_feasibility_uuid,
                    readiness_root=config.readiness_root,
                    environment_root=config.environment_root,
                    feasibility_root=config.feasibility_root,
                    package_root=config.package_root,
                )
            ).start(runtime)
        except ProductionExecutionInitializationError:
            raise
        except Exception as exc:
            raise ProductionExecutionInitializationError(
                "PRODUCTION_INITIALIZATION_REJECTED"
            ) from exc


def _parser():
    parser = argparse.ArgumentParser(
        description="Build the governed PR186-PR190 chain and invoke PR208."
    )
    parser.add_argument("--recommendation-uuid", required=True)
    parser.add_argument("--captured-at", required=True)
    for dimension in ENVIRONMENT_DIMENSIONS:
        parser.add_argument("--" + dimension.replace("_", "-"), type=float, required=True)
    roots = (
        ("recommendation", "decision_recommendation"),
        ("readiness", "execution_readiness"),
        ("environment", "execution_environment"),
        ("feasibility", "execution_feasibility"),
        ("package", "execution_package"),
    )
    for name, directory in roots:
        parser.add_argument(
            f"--{name}-root",
            type=Path,
            default=Path("learning_data") / directory,
        )
    return parser


def main(argv: Optional[Sequence[str]] = None):
    arguments = _parser().parse_args(argv)
    return ProductionExecutionInitializer(
        ProductionExecutionInitializationConfiguration(
            recommendation_uuid=arguments.recommendation_uuid,
            observations=tuple(
                (dimension, getattr(arguments, dimension))
                for dimension in ENVIRONMENT_DIMENSIONS
            ),
            captured_at=arguments.captured_at,
            recommendation_root=arguments.recommendation_root,
            readiness_root=arguments.readiness_root,
            environment_root=arguments.environment_root,
            feasibility_root=arguments.feasibility_root,
            package_root=arguments.package_root,
        )
    ).start()


if __name__ == "__main__":
    main()
