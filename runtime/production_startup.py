"""Canonical production startup from one exact governed PR184 intelligence.

PR185 owns Recommendation construction.  This composition resolves an exact
PR184 identity, asks PR185 to persist its deterministic Recommendation, and
hands that exact owner-produced identity to PR209.  It never selects a latest
record or constructs an identity itself.
"""

import argparse
import logging
from dataclasses import dataclass
from math import isfinite
from pathlib import Path
from typing import Callable, Optional, Sequence
from uuid import UUID

from learning.decision_intelligence import DecisionIntelligenceRepository
from learning.decision_intelligence.exceptions import DecisionIntelligenceError
from learning.pattern_memory.models import valid_digest
from learning.decision_recommendation import (
    DecisionRecommendationRepository,
    GovernedDecisionRecommendationEngine,
)
from learning.execution_environment.policy import ENVIRONMENT_DIMENSIONS
from runtime.production_execution_initialization import (
    ProductionExecutionInitializationConfiguration,
    ProductionExecutionInitializer,
)
from runtime.environment_observation import (
    EnvironmentObservationError,
    GovernedEnvironmentObservationProducer,
    canonical_market_state_path,
)


class ProductionStartupError(ValueError):
    """The governed startup chain was rejected before Runtime invocation."""


@dataclass(frozen=True)
class ProductionStartupConfiguration:
    decision_intelligence_uuid: str
    decision_intelligence_digest: str
    decision_intelligence_snapshot_uuid: str
    decision_intelligence_snapshot_digest: str
    decision_intelligence_repository_digest: str
    intelligence_policy_uuid: str
    intelligence_policy_digest: str
    intelligence_policy_version: str
    intelligence_engine_version: str
    observations: tuple[tuple[str, float], ...]
    captured_at: str
    intelligence_root: Path = Path("learning_data/decision_intelligence")
    recommendation_root: Path = Path("learning_data/decision_recommendation")
    readiness_root: Path = Path("learning_data/execution_readiness")
    environment_root: Path = Path("learning_data/execution_environment")
    feasibility_root: Path = Path("learning_data/execution_feasibility")
    package_root: Path = Path("learning_data/execution_package")

    @classmethod
    def from_canonical_repository(
        cls,
        *,
        observations,
        captured_at,
        intelligence_root=Path("learning_data/decision_intelligence"),
        **roots,
    ):
        """Resolve the sole owner-activated PR184 identity without head selection."""
        repository = DecisionIntelligenceRepository(intelligence_root)
        try:
            activations = repository.activations()
        except DecisionIntelligenceError as exc:
            raise ProductionStartupError(str(exc)) from exc
        if not activations:
            raise ProductionStartupError("DECISION_INTELLIGENCE_ACTIVATION_MISSING")
        if len(activations) != 1:
            raise ProductionStartupError("DECISION_INTELLIGENCE_ACTIVATION_AMBIGUOUS")
        activation = activations[0]
        try:
            intelligence, _ = repository.exact(
                intelligence_uuid=activation.intelligence_uuid,
                intelligence_digest=activation.intelligence_digest,
                snapshot_uuid=activation.snapshot_uuid,
                snapshot_digest=activation.snapshot_digest,
                repository_digest=activation.repository_digest,
                intelligence_policy_uuid=activation.intelligence_policy_uuid,
                intelligence_policy_digest=activation.intelligence_policy_digest,
                intelligence_policy_version=activation.intelligence_policy_version,
                intelligence_engine_version=activation.intelligence_engine_version,
            )
        except DecisionIntelligenceError as exc:
            raise ProductionStartupError(str(exc)) from exc
        if intelligence.intelligence_state != "DECISION_INTELLIGENCE_READY":
            raise ProductionStartupError("ACTIVATED_DECISION_INTELLIGENCE_NOT_READY")
        return cls(
            decision_intelligence_uuid=intelligence.intelligence_uuid,
            decision_intelligence_digest=intelligence.intelligence_digest,
            decision_intelligence_snapshot_uuid=activation.snapshot_uuid,
            decision_intelligence_snapshot_digest=activation.snapshot_digest,
            decision_intelligence_repository_digest=activation.repository_digest,
            intelligence_policy_uuid=activation.intelligence_policy_uuid,
            intelligence_policy_digest=activation.intelligence_policy_digest,
            intelligence_policy_version=activation.intelligence_policy_version,
            intelligence_engine_version=activation.intelligence_engine_version,
            observations=observations,
            captured_at=captured_at,
            intelligence_root=intelligence_root,
            **roots,
        )

    def __post_init__(self):
        for value in (
            self.decision_intelligence_uuid,
            self.decision_intelligence_snapshot_uuid,
            self.intelligence_policy_uuid,
        ):
            try:
                canonical = str(UUID(value)) if type(value) is str else None
            except (ValueError, TypeError, AttributeError):
                canonical = None
            if canonical != value:
                raise ProductionStartupError("INVALID_DECISION_INTELLIGENCE_IDENTITY")
        if not all(
            valid_digest(value)
            for value in (
                self.decision_intelligence_digest,
                self.decision_intelligence_snapshot_digest,
                self.decision_intelligence_repository_digest,
                self.intelligence_policy_digest,
            )
        ) or any(
            type(value) is not str or not value or value != value.strip()
            for value in (
                self.intelligence_policy_version,
                self.intelligence_engine_version,
            )
        ):
            raise ProductionStartupError("INVALID_DECISION_INTELLIGENCE_IDENTITY")
        try:
            observations = tuple(tuple(item) for item in self.observations)
        except (TypeError, ValueError):
            raise ProductionStartupError(
                "INVALID_ENVIRONMENT_OBSERVATIONS"
            ) from None
        object.__setattr__(self, "observations", observations)
        if (
            tuple(item[0] for item in observations if len(item) == 2)
            != ENVIRONMENT_DIMENSIONS
            or any(len(item) != 2 for item in observations)
            or any(
                type(value) is not float or not isfinite(value) or value < 0.0
                for _, value in observations
            )
        ):
            raise ProductionStartupError("INVALID_ENVIRONMENT_OBSERVATIONS")
        if type(self.captured_at) is not str or not self.captured_at.strip():
            raise ProductionStartupError("INVALID_CAPTURED_AT")
        if any(
            not isinstance(root, Path)
            for root in (
                self.intelligence_root,
                self.recommendation_root,
                self.readiness_root,
                self.environment_root,
                self.feasibility_root,
                self.package_root,
            )
        ):
            raise ProductionStartupError("INVALID_REPOSITORY_ROOT")


class GovernedProductionStartup:
    """Compose PR185 -> PR209 -> PR208 -> the authorized V26 Runtime."""

    def __init__(self, configuration: ProductionStartupConfiguration):
        if type(configuration) is not ProductionStartupConfiguration:
            raise ProductionStartupError("INVALID_CONFIGURATION")
        self.configuration = configuration

    def start(self, runtime: Optional[Callable[[], object]] = None):
        if runtime is not None and not callable(runtime):
            raise ProductionStartupError("UNAUTHORIZED_RUNTIME_TARGET")
        config = self.configuration
        try:
            intelligence_repository = DecisionIntelligenceRepository(
                config.intelligence_root
            )
            try:
                intelligence, intelligence_snapshot = intelligence_repository.exact(
                    intelligence_uuid=config.decision_intelligence_uuid,
                    intelligence_digest=config.decision_intelligence_digest,
                    snapshot_uuid=config.decision_intelligence_snapshot_uuid,
                    snapshot_digest=config.decision_intelligence_snapshot_digest,
                    repository_digest=config.decision_intelligence_repository_digest,
                    intelligence_policy_uuid=config.intelligence_policy_uuid,
                    intelligence_policy_digest=config.intelligence_policy_digest,
                    intelligence_policy_version=config.intelligence_policy_version,
                    intelligence_engine_version=config.intelligence_engine_version,
                )
            except DecisionIntelligenceError as exc:
                raise ProductionStartupError(str(exc)) from exc
            recommendation_repository = DecisionRecommendationRepository(
                config.recommendation_root
            )
            report = GovernedDecisionRecommendationEngine(
                intelligence_repository, recommendation_repository
            ).run(intelligence_snapshot)
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
    parser.add_argument("--market-state", type=Path, default=None,
                        help="canonical publication (default: RP_AI_SHARED_ROOT/XAUUSD/market_state.json)")
    parser.add_argument("--observation-window", type=float, default=5.0)
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
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    try:
        evidence = GovernedEnvironmentObservationProducer(
            arguments.market_state or canonical_market_state_path(),
            window_seconds=arguments.observation_window,
        ).collect()
    except EnvironmentObservationError as exc:
        raise ProductionStartupError(str(exc)) from exc
    return GovernedProductionStartup(
        ProductionStartupConfiguration.from_canonical_repository(
            observations=evidence.observations,
            captured_at=evidence.captured_at,
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
