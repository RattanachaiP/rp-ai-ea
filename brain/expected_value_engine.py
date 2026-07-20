"""Analytical expected-value assessment for the private Brain pipeline.

This module evaluates the opportunity implied by the non-directional market
state distribution.  It is deliberately detached from the V26 decision path:
it does not select a direction, construct a payload, size a position, or make
an execution recommendation.
"""

from __future__ import annotations

from dataclasses import dataclass

from brain.market_reasoning import MarketReasoning
from brain.market_understanding import MarketUnderstanding
from brain.probability_engine import ProbabilityAssessment


@dataclass(frozen=True)
class ConfidenceInterval:
    """Bounded uncertainty interval for normalized expected value."""

    lower: float
    upper: float


@dataclass(frozen=True)
class ExpectedValueAssessment:
    """Immutable, non-directional analytical trade-quality assessment.

    Values are normalized opportunity units, not prices, lots, or instructions.
    A positive value describes the balance of observed favourable versus adverse
    market states only; it never authorizes a trade.
    """

    understanding: MarketUnderstanding
    reasoning: MarketReasoning
    probability_assessment: ProbabilityAssessment
    risk: float
    reward: float
    risk_reward_ratio: float
    opportunity_quality: str
    trade_quality: str
    expected_value: float
    uncertainty_impact: float
    confidence_interval: ConfidenceInterval
    methodology: str


def _quality(expected_value: float, interval: ConfidenceInterval, context_quality: str) -> tuple[str, str]:
    if context_quality == "INSUFFICIENT":
        return "INSUFFICIENT_CONTEXT", "ANALYTICAL_ONLY_INSUFFICIENT_CONTEXT"
    if interval.lower > 0:
        return "POSITIVE_EDGE_OBSERVED", "ANALYTICAL_ONLY_POSITIVE_EDGE"
    if expected_value > 0:
        return "UNCERTAIN_POSITIVE_EDGE", "ANALYTICAL_ONLY_UNCERTAIN_EDGE"
    if expected_value == 0:
        return "BALANCED_OR_NEUTRAL", "ANALYTICAL_ONLY_NEUTRAL"
    return "NEGATIVE_EDGE_OBSERVED", "ANALYTICAL_ONLY_NEGATIVE_EDGE"


def evaluate_expected_value(
    understanding: MarketUnderstanding,
    reasoning: MarketReasoning,
    probability_assessment: ProbabilityAssessment,
) -> ExpectedValueAssessment:
    """Evaluate a market opportunity without creating a production decision.

    Continuation and breakout are favourable states.  Reversal and no-trade are
    adverse/opportunity-cost states.  Range is neutral.  Risk and reward are
    therefore normalized probability-weighted units; they are not stop-loss,
    take-profit, currency, or position-sizing values.
    """
    if not isinstance(understanding, MarketUnderstanding):
        raise TypeError("Expected Value Engine requires a MarketUnderstanding object")
    if not isinstance(reasoning, MarketReasoning):
        raise TypeError("Expected Value Engine requires a MarketReasoning object")
    if not isinstance(probability_assessment, ProbabilityAssessment):
        raise TypeError("Expected Value Engine requires a ProbabilityAssessment object")
    if reasoning.understanding is not understanding:
        raise ValueError("Expected Value Engine requires reasoning for the supplied understanding")
    if probability_assessment.understanding is not understanding:
        raise ValueError("Expected Value Engine requires probabilities for the supplied understanding")
    if probability_assessment.reasoning is not reasoning:
        raise ValueError("Expected Value Engine requires probabilities for the supplied reasoning")

    reward = round(probability_assessment.continuation.probability + probability_assessment.breakout.probability, 4)
    risk = round(probability_assessment.reversal.probability + probability_assessment.no_trade.probability, 4)
    ratio = round(reward / risk, 4) if risk else float("inf")
    expected_value = round(reward - risk, 4)
    uncertainty = round(
        sum(item.uncertainty_estimate for item in (
            probability_assessment.continuation, probability_assessment.reversal,
            probability_assessment.range, probability_assessment.breakout,
            probability_assessment.no_trade,
        )) / 5,
        4,
    )
    uncertainty_impact = round(uncertainty * (reward + risk), 4)
    interval = ConfidenceInterval(
        lower=round(expected_value - uncertainty_impact, 4),
        upper=round(expected_value + uncertainty_impact, 4),
    )
    opportunity_quality, trade_quality = _quality(expected_value, interval, understanding.context_quality)
    return ExpectedValueAssessment(
        understanding=understanding,
        reasoning=reasoning,
        probability_assessment=probability_assessment,
        risk=risk,
        reward=reward,
        risk_reward_ratio=ratio,
        opportunity_quality=opportunity_quality,
        trade_quality=trade_quality,
        expected_value=expected_value,
        uncertainty_impact=uncertainty_impact,
        confidence_interval=interval,
        methodology=(
            "non-directional normalized state EV: favourable continuation plus breakout "
            "minus adverse reversal plus no-trade; range is neutral; interval is "
            "mean state uncertainty times exposed opportunity units"
        ),
    )
