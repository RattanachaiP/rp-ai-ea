"""Fail-closed PR189-to-PR191 bootstrap for the V26 AI Runtime."""

import argparse
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Optional, Sequence

from learning.execution_environment import ExecutionEnvironmentRepository
from learning.execution_feasibility import ExecutionFeasibilityRepository
from learning.execution_package import (
    ExecutionPackageRepository,
    GovernedExecutionPackageAssemblyEngine,
)
from learning.execution_package_consumer import ExecutionPackageConsumer
from learning.execution_readiness import ExecutionReadinessRepository


class ExecutionPackageBootstrapError(ValueError):
    """A terminal package assembly or Runtime bootstrap failure."""


@dataclass(frozen=True)
class ExecutionPackageBootstrapConfiguration:
    """Exact upstream identities and canonical repository locations."""

    readiness_uuid: str
    environment_uuid: str
    feasibility_uuid: str
    readiness_root: Path = Path("learning_data/execution_readiness")
    environment_root: Path = Path("learning_data/execution_environment")
    feasibility_root: Path = Path("learning_data/execution_feasibility")
    package_root: Path = Path("learning_data/execution_package")


class ExecutionPackageRuntimeBootstrap:
    """Compose existing authorities, export their result, then start V26."""

    def __init__(self, configuration: ExecutionPackageBootstrapConfiguration):
        if type(configuration) is not ExecutionPackageBootstrapConfiguration:
            raise ExecutionPackageBootstrapError("INVALID_CONFIGURATION")
        self.configuration = configuration

    @staticmethod
    def _exact(records, field: str, expected_uuid: str, missing_reason: str):
        matches = tuple(record for record in records if getattr(record, field) == expected_uuid)
        if len(matches) != 1:
            raise ExecutionPackageBootstrapError(missing_reason)
        return matches[0]

    def start(self, runtime: Optional[Callable[[], object]] = None):
        """Assemble, persist, re-consume, export, and invoke the Runtime once."""
        if runtime is not None and not callable(runtime):
            raise ExecutionPackageBootstrapError("INVALID_RUNTIME")
        config = self.configuration
        readiness_repository = ExecutionReadinessRepository(config.readiness_root)
        environment_repository = ExecutionEnvironmentRepository(config.environment_root)
        feasibility_repository = ExecutionFeasibilityRepository(config.feasibility_root)
        package_repository = ExecutionPackageRepository(config.package_root)

        try:
            readiness = self._exact(
                readiness_repository.records(), "execution_readiness_uuid",
                config.readiness_uuid, "READINESS_MISSING")
            environment = self._exact(
                environment_repository.records(), "execution_environment_uuid",
                config.environment_uuid, "ENVIRONMENT_MISSING")
            feasibility = self._exact(
                feasibility_repository.records(), "execution_feasibility_uuid",
                config.feasibility_uuid, "FEASIBILITY_MISSING")
            package, _ = GovernedExecutionPackageAssemblyEngine(
                readiness_repository, environment_repository, feasibility_repository,
                package_repository,
            ).assemble(readiness, environment, feasibility)
            # PR190 remains the sole loading boundary.  Do not export an identity
            # which the Runtime's consumer cannot load from the canonical snapshot.
            consumed = ExecutionPackageConsumer(package_repository).load(
                package.execution_package_uuid
            )
        except ExecutionPackageBootstrapError:
            raise
        except Exception as exc:
            raise ExecutionPackageBootstrapError("PACKAGE_BOOTSTRAP_REJECTED") from exc

        os.environ["RP_EXECUTION_PACKAGE_UUID"] = consumed.execution_package_uuid
        if runtime is None:
            from bridge.ai_decision_engine_xauusd_v26_execution_confidence_engine import run
            runtime = run
        return runtime()


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Assemble an exact governed ExecutionPackage and start the V26 Runtime."
    )
    parser.add_argument("--readiness-uuid", required=True)
    parser.add_argument("--environment-uuid", required=True)
    parser.add_argument("--feasibility-uuid", required=True)
    parser.add_argument("--readiness-root", type=Path, default=Path("learning_data/execution_readiness"))
    parser.add_argument("--environment-root", type=Path, default=Path("learning_data/execution_environment"))
    parser.add_argument("--feasibility-root", type=Path, default=Path("learning_data/execution_feasibility"))
    parser.add_argument("--package-root", type=Path, default=Path("learning_data/execution_package"))
    return parser


def main(argv: Optional[Sequence[str]] = None):
    arguments = _parser().parse_args(argv)
    return ExecutionPackageRuntimeBootstrap(
        ExecutionPackageBootstrapConfiguration(
            readiness_uuid=arguments.readiness_uuid,
            environment_uuid=arguments.environment_uuid,
            feasibility_uuid=arguments.feasibility_uuid,
            readiness_root=arguments.readiness_root,
            environment_root=arguments.environment_root,
            feasibility_root=arguments.feasibility_root,
            package_root=arguments.package_root,
        )
    ).start()


if __name__ == "__main__":
    main()
