"""Private position-structure analytics for the Brain Phase 6 shadow layer.

This module describes whether the *market context* can support position
structures.  Its normalized labels are deliberately not executable prices,
stops, targets, lot sizes, directions, or recommendations.  The V26 runtime
continues to own every production position and payload decision.
"""

from __future__ import annotations

from dataclasses import dataclass

from brain.expected_value_engine import ExpectedValueAssessment
from brain.market_reasoning import MarketReasoning
from brain.market_understanding import MarketUnderstanding
from brain.probability_engine import ProbabilityAssessment


@dataclass(frozen=True)
class PositionIntelligenceAssessment:
    """Immutable, non-executable assessment of contextual position structure."""

    understanding: MarketUnderstanding
    reasoning: MarketReasoning
    probability_assessment: ProbabilityAssessment
    expected_value_assessment: ExpectedValueAssessment
    position_eligibility: str
    risk_budget_class: str
    stop_loss_context: str
    target_context: str
    risk_reward_feasibility: str
    position_style: str
    scalp_suitability: str
    intraday_suitability: str
    runner_suitability: str
    scale_in_suitability: str
    partial_exit_suitability: str
    invalidation_context: tuple[str, ...]
    position_uncertainty: float
    position_uncertainty_class: str
    position_quality: str
    methodology: str


def _style(understanding: MarketUnderstanding) -> str:
    if understanding.market_regime == "TRENDING":
        return "TREND_CONTEXT"
    if understanding.expansion_compression == "COMPRESSION":
        return "BREAKOUT_CONTEXT"
    if understanding.market_regime == "RANGE_OR_UNDEFINED":
        return "RANGE_CONTEXT"
    return "TRANSITION_CONTEXT"


def _uncertainty_class(value: float) -> str:
    if value >= 0.6:
        return "HIGH_UNCERTAINTY"
    if value >= 0.35:
        return "MODERATE_UNCERTAINTY"
    return "LOW_UNCERTAINTY"


def assess_position_intelligence(
    understanding: MarketUnderstanding,
    reasoning: MarketReasoning,
    probability_assessment: ProbabilityAssessment,
    expected_value_assessment: ExpectedValueAssessment,
) -> PositionIntelligenceAssessment:
    """Assess normalized structure only; never construct or recommend a position."""
    if not isinstance(understanding, MarketUnderstanding):
        raise TypeError("Position Intelligence requires a MarketUnderstanding object")
    if not isinstance(reasoning, MarketReasoning):
        raise TypeError("Position Intelligence requires a MarketReasoning object")
    if not isinstance(probability_assessment, ProbabilityAssessment):
        raise TypeError("Position Intelligence requires a ProbabilityAssessment object")
    if not isinstance(expected_value_assessment, ExpectedValueAssessment):
        raise TypeError("Position Intelligence requires an ExpectedValueAssessment object")
    if reasoning.understanding is not understanding:
        raise ValueError("Position Intelligence requires reasoning for the supplied understanding")
    if probability_assessment.understanding is not understanding or probability_assessment.reasoning is not reasoning:
        raise ValueError("Position Intelligence requires matching probability inputs")
    if (expected_value_assessment.understanding is not understanding
            or expected_value_assessment.reasoning is not reasoning
            or expected_value_assessment.probability_assessment is not probability_assessment):
        raise ValueError("Position Intelligence requires matching expected-value inputs")

    uncertainty = round(min(1.0, max(0.0, expected_value_assessment.uncertainty_impact)), 4)
    uncertainty_class = _uncertainty_class(uncertainty)
    style = _style(understanding)
    coherent = understanding.context_quality == "COMPLETE" and uncertainty_class != "HIGH_UNCERTAINTY"
    positive = expected_value_assessment.expected_value > 0 and expected_value_assessment.confidence_interval.lower > 0
    eligibility = "CONTEXTUALLY_ELIGIBLE" if coherent and positive else "CONTEXTUALLY_RESTRICTED"
    risk_budget = "ANALYTICAL_STANDARD" if eligibility == "CONTEXTUALLY_ELIGIBLE" else "ANALYTICAL_CONSERVATIVE"
    stop_context = "STRUCTURE_INVALIDATION_CONTEXT" if understanding.market_structure in {"HH_HL", "LH_LL"} else "NO_CONFIRMED_STRUCTURE_INVALIDATION"
    target_context = "CONTINUATION_OR_EXPANSION_CONTEXT" if style in {"TREND_CONTEXT", "BREAKOUT_CONTEXT"} else "NO_CLEAR_EXPANSION_CONTEXT"
    rr = "FAVOURABLE_NORMALIZED_FEASIBILITY" if expected_value_assessment.risk_reward_ratio >= 1.5 and positive else "UNCONFIRMED_NORMALIZED_FEASIBILITY"
    scalp = "SUITABLE" if uncertainty_class != "HIGH_UNCERTAINTY" else "RESTRICTED"
    intraday = "SUITABLE" if style == "TREND_CONTEXT" and positive else "CONTEXT_DEPENDENT"
    runner = "SUITABLE" if style == "TREND_CONTEXT" and rr.startswith("FAVOURABLE") else "RESTRICTED"
    scale_in = "SUITABLE_IF_CONTEXT_PERSISTS" if runner == "SUITABLE" else "NOT_SUPPORTED_BY_CONTEXT"
    partial_exit = "SUITABLE_FOR_UNCERTAINTY_MANAGEMENT" if uncertainty_class != "LOW_UNCERTAINTY" else "CONTEXT_DEPENDENT"
    invalidation = tuple(dict.fromkeys(
        (*understanding.invalid_conditions, *reasoning.conflicting_evidence,
         "trend_or_structure_failure", "momentum_coherence_failure")
    ))
    quality = "HIGH_CONTEXTUAL_POSITION_QUALITY" if eligibility == "CONTEXTUALLY_ELIGIBLE" and runner == "SUITABLE" else (
        "MODERATE_CONTEXTUAL_POSITION_QUALITY" if positive else "LOW_CONTEXTUAL_POSITION_QUALITY"
    )
    return PositionIntelligenceAssessment(
        understanding, reasoning, probability_assessment, expected_value_assessment,
        eligibility, risk_budget, stop_context, target_context, rr, style, scalp,
        intraday, runner, scale_in, partial_exit, invalidation, uncertainty,
        uncertainty_class, quality,
        "descriptive normalized position-structure assessment from market context, "
        "non-directional probabilities, and normalized expected value; no prices, "
        "lot sizes, risk instructions, or execution recommendation",
    )
