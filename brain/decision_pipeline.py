"""Pure composition boundary for the internal Brain decision pipeline.

This module deliberately delegates all analysis and construction rules to the
Brain modules that own them.  It only orders, validates, and aggregates their
immutable outputs; it has no runtime publication or execution dependencies.
"""
from __future__ import annotations

from dataclasses import dataclass
from math import isfinite
from typing import Callable

from brain.adaptive_position_construction import PositionBudget, PositionLifecycle
from brain.entry_construction_coordinator import (
    ConstructionAction,
    EntryConstructionCoordinator,
    EntryConstructionDecision,
    EntryConstructionRequest,
)
from brain.entry_location_intelligence import (
    EntryLocationAssessment,
    EntryLocationInput,
    EntryLocationIntelligence,
    EntryState,
)
from brain.expected_value_engine import ExpectedValueAssessment, evaluate_expected_value
from brain.market_reasoning import MarketReasoning
from brain.market_understanding import MarketUnderstanding
from brain.probability_engine import ProbabilityAssessment, estimate_market_probabilities


@dataclass(frozen=True)
class DecisionPipelineInput:
    """All pre-existing domain inputs required to compose one decision."""

    understanding: MarketUnderstanding
    reasoning: MarketReasoning
    location_input: EntryLocationInput
    construction_request: EntryConstructionRequest
    lifecycle: PositionLifecycle
    budget: PositionBudget


@dataclass(frozen=True)
class DecisionPackage:
    """Internal, non-publishing aggregate of the ordered Brain pipeline."""

    direction: str
    confidence: float
    probability: float
    expected_value: float
    location_score: float
    entry_permission: bool
    entry_state: str
    construction_action: str
    position_budget_total: float
    position_budget_used: float
    position_budget_remaining: float
    decision: str
    decision_trace: tuple[str, ...]
    # These are publisher-owned execution instructions supplied by the
    # upstream construction contract.  The pipeline never invents them.
    symbol: str | None = None
    volume: float | None = None
    entry_price: float | None = None
    stop_loss: float | None = None
    take_profit: float | None = None


class DecisionPipeline:
    """Execute the approved Brain composition order with a fail-safe outcome."""

    def __init__(
        self,
        *,
        probability_estimator: Callable[[MarketUnderstanding, MarketReasoning], ProbabilityAssessment] = estimate_market_probabilities,
        expected_value_evaluator: Callable[[MarketUnderstanding, MarketReasoning, ProbabilityAssessment], ExpectedValueAssessment] = evaluate_expected_value,
        location_intelligence: EntryLocationIntelligence | None = None,
        construction_coordinator: EntryConstructionCoordinator | None = None,
    ) -> None:
        self._probability_estimator = probability_estimator
        self._expected_value_evaluator = expected_value_evaluator
        self._location_intelligence = location_intelligence or EntryLocationIntelligence()
        self._construction_coordinator = construction_coordinator or EntryConstructionCoordinator()

    def decide(self, data: DecisionPipelineInput) -> DecisionPackage:
        """Compose one package, returning ``WAIT`` for any failed contract."""
        try:
            self._validate_input(data)
            probability = self._probability_estimator(data.understanding, data.reasoning)
            self._validate_probability(probability, data)
            expected_value = self._expected_value_evaluator(data.understanding, data.reasoning, probability)
            self._validate_expected_value(expected_value, probability, data)
            location = self._location_intelligence.assess(data.location_input)
            self._validate_location(location, data)
            construction = self._construction_coordinator.decide(
                location, data.construction_request, data.lifecycle, data.budget,
            )
            self._validate_construction(construction, location)
        except Exception as error:
            return self._wait_package(data, f"{type(error).__name__}:{error}")

        trace = (
            f"Probability={probability.continuation.probability:.4f}",
            f"ExpectedValue={expected_value.expected_value:.4f}",
            f"ELI={location.entry_state.value}",
            f"Coordinator={construction.construction_action.value}",
            "APC=BudgetPreserved" if construction.budget_preserved else "APC=BudgetChanged",
        )
        return DecisionPackage(
            direction=location.direction,
            confidence=round(float(data.location_input.execution_confidence), 4),
            probability=probability.continuation.probability,
            expected_value=expected_value.expected_value,
            location_score=location.location_score,
            entry_permission=location.entry_permission,
            entry_state=location.entry_state.value,
            construction_action=construction.construction_action.value,
            position_budget_total=construction.budget_total,
            position_budget_used=construction.budget_used,
            position_budget_remaining=construction.budget_remaining,
            decision="TRADE" if construction.construction_permission else "WAIT",
            decision_trace=trace,
        )

    @staticmethod
    def _validate_input(data: DecisionPipelineInput) -> None:
        if not isinstance(data, DecisionPipelineInput):
            raise TypeError("INVALID_PIPELINE_INPUT")
        if data.location_input.direction != data.construction_request.direction:
            raise ValueError("DIRECTION_MISMATCH")
        if not isfinite(data.location_input.execution_confidence) or not 0 <= data.location_input.execution_confidence <= 100:
            raise ValueError("INVALID_EXECUTION_CONFIDENCE")

    @staticmethod
    def _validate_probability(value: ProbabilityAssessment, data: DecisionPipelineInput) -> None:
        if not isinstance(value, ProbabilityAssessment):
            raise TypeError("INVALID_PROBABILITY_OUTPUT")
        if value.understanding is not data.understanding or value.reasoning is not data.reasoning:
            raise ValueError("UNMATCHED_PROBABILITY_CONTEXT")
        states = (value.continuation, value.reversal, value.range, value.breakout, value.no_trade)
        if any(not isfinite(item.probability) or item.probability < 0 or item.probability > 1 for item in states):
            raise ValueError("INVALID_PROBABILITY_VALUES")
        if abs(sum(item.probability for item in states) - 1.0) > 0.001:
            raise ValueError("INVALID_PROBABILITY_DISTRIBUTION")

    @staticmethod
    def _validate_expected_value(value: ExpectedValueAssessment, probability: ProbabilityAssessment,
                                 data: DecisionPipelineInput) -> None:
        if not isinstance(value, ExpectedValueAssessment):
            raise TypeError("INVALID_EXPECTED_VALUE_OUTPUT")
        if (value.understanding is not data.understanding or value.reasoning is not data.reasoning
                or value.probability_assessment is not probability):
            raise ValueError("UNMATCHED_EXPECTED_VALUE_CONTEXT")
        if not isfinite(value.expected_value):
            raise ValueError("INVALID_EXPECTED_VALUE")

    @staticmethod
    def _validate_location(value: EntryLocationAssessment, data: DecisionPipelineInput) -> None:
        if not isinstance(value, EntryLocationAssessment) or not isinstance(value.entry_state, EntryState):
            raise TypeError("INVALID_ELI_OUTPUT")
        if value.direction != data.construction_request.direction:
            raise ValueError("UNMATCHED_ELI_DIRECTION")
        if not isfinite(value.location_score) or not 0 <= value.location_score <= 100:
            raise ValueError("INVALID_LOCATION_SCORE")

    @staticmethod
    def _validate_construction(value: EntryConstructionDecision, location: EntryLocationAssessment) -> None:
        if not isinstance(value, EntryConstructionDecision):
            raise TypeError("INVALID_COORDINATOR_OUTPUT")
        if not isinstance(value.construction_action, ConstructionAction):
            raise TypeError("INVALID_CONSTRUCTION_ACTION")
        if value.eli_entry_state != location.entry_state.value:
            raise ValueError("UNMATCHED_COORDINATOR_ELI_STATE")
        if not all(isfinite(item) and item >= 0 for item in (
            value.budget_total, value.budget_used, value.budget_remaining,
        )):
            raise ValueError("INVALID_POSITION_BUDGET")

    @staticmethod
    def _wait_package(data: object, reason: str) -> DecisionPackage:
        direction = data.location_input.direction if isinstance(data, DecisionPipelineInput) else "WAIT"
        return DecisionPackage(direction, 0.0, 0.0, 0.0, 0.0, False, "INVALID", "NO_ACTION",
                               0.0, 0.0, 0.0, "WAIT", (f"FAIL_SAFE={reason}",))
