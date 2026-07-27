"""Canonical production startup from one exact governed PR184 intelligence.

PR185 owns Recommendation construction.  This composition resolves an exact
PR184 identity, asks PR185 to persist its deterministic Recommendation, and
hands that exact owner-produced identity to PR209.  It never selects a latest
record or constructs an identity itself.
"""

import argparse
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Optional, Sequence
from uuid import UUID

from learning.decision_intelligence import DecisionIntelligenceRepository
from learning.decision_recommendation import (
    DecisionRecommendationRepository,
    GovernedDecisionRecommendationEngine,
)
from learning.execution_environment.policy import ENVIRONMENT_DIMENSIONS
from runtime.production_execution_initialization import (
    ProductionExecutionInitializationConfiguration,
    ProductionExecutionInitializer,
)


class ProductionStartupError(ValueError):
    """The governed startup chain was rejected before Runtime invocation."""


@dataclass(frozen=True)
class ProductionStartupConfiguration:
    decision_intelligence_uuid: str
    observations: tuple[tuple[str, float], ...]
    captured_at: str
    intelligence_root: Path = Path("learning_data/decision_intelligence")
    recommendation_root: Path = Path("learning_data/decision_recommendation")
    readiness_root: Path = Path("learning_data/execution_readiness")
    environment_root: Path = Path("learning_data/execution_environment")
    feasibility_root: Path = Path("learning_data/execution_feasibility")
    package_root: Path = Path("learning_data/execution_package")

    def __post_init__(self):
        try:
            canonical = str(UUID(self.decision_intelligence_uuid))
        except (ValueError, TypeError, AttributeError):
            canonical = None
        if type(self.decision_intelligence_uuid) is not str or canonical != self.decision_intelligence_uuid:
            raise ProductionStartupError("INVALID_DECISION_INTELLIGENCE_UUID")


class GovernedProductionStartup:
    """Compose PR185 -> PR209 -> PR208 -> the authorized V26 Runtime."""

    def __init__(self, configuration: ProductionStartupConfiguration):
        if type(configuration) is not ProductionStartupConfiguration:
            raise ProductionStartupError("INVALID_CONFIGURATION")
        self.configuration = configuration

    @staticmethod
    def _exact(records, expected_uuid):
        matches = tuple(
            item for item in records if item.intelligence_uuid == expected_uuid
        )
        if len(matches) != 1:
            raise ProductionStartupError("DECISION_INTELLIGENCE_MISSING")
        return matches[0]

    def start(self, runtime: Optional[Callable[[], object]] = None):
        if runtime is not None and not callable(runtime):
            raise ProductionStartupError("UNAUTHORIZED_RUNTIME_TARGET")
        config = self.configuration
        try:
            intelligence_repository = DecisionIntelligenceRepository(
                config.intelligence_root
            )
            intelligence = self._exact(
                intelligence_repository.records(), config.decision_intelligence_uuid
            )
            recommendation_repository = DecisionRecommendationRepository(
                config.recommendation_root
            )
            report = GovernedDecisionRecommendationEngine(
                intelligence_repository, recommendation_repository
            ).run(intelligence)
            matches = tuple(
                item
                for item in report.recommendations
                if item.decision_intelligence_uuid == config.decision_intelligence_uuid
            )
            if len(matches) != 1:
                raise ProductionStartupError("RECOMMENDATION_MISSING")
            recommendation = matches[0]
            if recommendation.recommendation_state != "RECOMMENDATION_READY":
                raise ProductionStartupError("RECOMMENDATION_NOT_READY")
            initializer = ProductionExecutionInitializer(
                ProductionExecutionInitializationConfiguration(
                    recommendation_uuid=recommendation.recommendation_uuid,
                    observations=config.observations,
                    captured_at=config.captured_at,
                    recommendation_root=config.recommendation_root,
                    readiness_root=config.readiness_root,
                    environment_root=config.environment_root,
                    feasibility_root=config.feasibility_root,
                    package_root=config.package_root,
                )
            )
            return initializer.start(runtime)
        except ProductionStartupError:
            raise
        except Exception as exc:
            raise ProductionStartupError("PRODUCTION_STARTUP_REJECTED") from exc


def _parser():
    parser = argparse.ArgumentParser(
        description="Create PR185 from an exact PR184 record and start the governed Runtime."
    )
    parser.add_argument("--decision-intelligence-uuid", required=True)
    parser.add_argument("--captured-at", required=True)
    for dimension in ENVIRONMENT_DIMENSIONS:
        parser.add_argument("--" + dimension.replace("_", "-"), type=float, required=True)
    for name, directory in (
        ("intelligence", "decision_intelligence"),
        ("recommendation", "decision_recommendation"),
        ("readiness", "execution_readiness"),
        ("environment", "execution_environment"),
        ("feasibility", "execution_feasibility"),
        ("package", "execution_package"),
    ):
        parser.add_argument(f"--{name}-root", type=Path, default=Path("learning_data") / directory)
    return parser


def main(argv: Optional[Sequence[str]] = None):
    arguments = _parser().parse_args(argv)
    return GovernedProductionStartup(
        ProductionStartupConfiguration(
            decision_intelligence_uuid=arguments.decision_intelligence_uuid,
            observations=tuple(
                (dimension, getattr(arguments, dimension))
                for dimension in ENVIRONMENT_DIMENSIONS
            ),
            captured_at=arguments.captured_at,
            intelligence_root=arguments.intelligence_root,
            recommendation_root=arguments.recommendation_root,
            readiness_root=arguments.readiness_root,
            environment_root=arguments.environment_root,
            feasibility_root=arguments.feasibility_root,
            package_root=arguments.package_root,
        )
    ).start()


if __name__ == "__main__":
    main()
