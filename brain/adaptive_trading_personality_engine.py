"""Private Adaptive Trading Personality Engine (ATPE) shadow analysis.

ATPE selects a descriptive management posture from the existing typed Brain
lineage.  It is deliberately non-directional and non-executable: the result
is not connected to V26, ``decision.json``, MT5, the Executor, or the
dashboard.
"""

from __future__ import annotations

from dataclasses import dataclass

from brain.expected_value_engine import ExpectedValueAssessment
from brain.market_reasoning import MarketReasoning
from brain.market_understanding import MarketUnderstanding
from brain.position_intelligence import PositionIntelligenceAssessment
from brain.probability_engine import ProbabilityAssessment


@dataclass(frozen=True)
class TradingPersonalityAssessment:
    """Immutable analytical posture; policy labels never issue trade instructions."""

    understanding: MarketUnderstanding
    reasoning: MarketReasoning
    probability_assessment: ProbabilityAssessment
    expected_value_assessment: ExpectedValueAssessment
    position_intelligence_assessment: PositionIntelligenceAssessment
    trading_personality: str
    personality_confidence: float
    management_policy: str
    allowed_actions: tuple[str, ...]
    risk_aggression: str
    protection_level: str
    runner_policy: str
    break_even_policy: str
    take_profit_policy: str
    partial_exit_policy: str
    methodology: str


def _selection(
    understanding: MarketUnderstanding,
    probabilities: ProbabilityAssessment,
    expected_value: ExpectedValueAssessment,
    position: PositionIntelligenceAssessment,
) -> tuple[str, float]:
    """Choose a posture from analytical context, without selecting a trade."""
    if (understanding.context_quality != "COMPLETE" or
            position.position_uncertainty_class == "HIGH_UNCERTAINTY" or
            probabilities.no_trade.probability >= probabilities.continuation.probability):
        return "OBSERVER", 0.82
    if (expected_value.expected_value <= 0 or
            expected_value.confidence_interval.lower <= 0 or
            position.position_eligibility == "CONTEXTUALLY_RESTRICTED"):
        return "RECOVERY_MODE", 0.88
    if (understanding.market_regime == "TRENDING" and
            position.runner_suitability == "SUITABLE"):
        return "TREND_RIDER", 0.91
    if (understanding.expansion_compression == "COMPRESSION" and
            probabilities.breakout.probability > probabilities.reversal.probability):
        return "MOMENTUM_HUNTER", 0.78
    return "CAPITAL_PROTECTOR", 0.74


def _policies(personality: str) -> tuple[str, tuple[str, ...], str, str, str, str, str, str]:
    """Map a posture to analytical-only management labels."""
    policies = {
        "TREND_RIDER": ("ANALYTICAL_TREND_CONTINUATION", ("MONITOR_CONTEXT", "REASSESS_INVALIDATION"), "ANALYTICAL_STANDARD", "STRUCTURE_AWARE", "CONTEXTUAL_RUNNER_ELIGIBLE", "CONTEXTUAL_REVIEW", "CONTINUATION_CONTEXT", "CONTEXTUAL_PARTIAL_REVIEW"),
        "MOMENTUM_HUNTER": ("ANALYTICAL_MOMENTUM_EXPANSION", ("MONITOR_CONTEXT", "REASSESS_EXPANSION"), "ANALYTICAL_MEASURED", "ELEVATED", "RUNNER_RESTRICTED_PENDING_PERSISTENCE", "EARLY_CONTEXTUAL_REVIEW", "EXPANSION_CONTEXT", "UNCERTAINTY_AWARE_REVIEW"),
        "CAPITAL_PROTECTOR": ("ANALYTICAL_CAPITAL_PRESERVATION", ("MONITOR_CONTEXT", "REASSESS_RISK"), "ANALYTICAL_CONSERVATIVE", "HIGH", "RUNNER_RESTRICTED", "PROTECTIVE_CONTEXTUAL_REVIEW", "CONSERVATIVE_CONTEXT", "PARTIAL_EXIT_CONTEXT_REVIEW"),
        "OBSERVER": ("ANALYTICAL_OBSERVATION_ONLY", ("OBSERVE_CONTEXT", "WAIT_FOR_COHERENCE"), "ANALYTICAL_MINIMAL", "MAXIMUM", "NO_RUNNER_CONTEXT", "NOT_APPLICABLE", "NO_TARGET_CONTEXT", "NOT_APPLICABLE"),
        "RECOVERY_MODE": ("ANALYTICAL_RECOVERY_AND_PROTECTION", ("OBSERVE_CONTEXT", "REASSESS_INVALIDATION", "WAIT_FOR_POSITIVE_EDGE"), "ANALYTICAL_MINIMAL", "MAXIMUM", "NO_RUNNER_CONTEXT", "NOT_APPLICABLE", "NO_TARGET_CONTEXT", "NOT_APPLICABLE"),
    }
    return policies[personality]


def select_trading_personality(
    understanding: MarketUnderstanding,
    reasoning: MarketReasoning,
    probability_assessment: ProbabilityAssessment,
    expected_value_assessment: ExpectedValueAssessment,
    position_intelligence_assessment: PositionIntelligenceAssessment,
) -> TradingPersonalityAssessment:
    """Select a shadow-only personality with strict typed-lineage validation."""
    expected_types = (
        (understanding, MarketUnderstanding, "Market Understanding"),
        (reasoning, MarketReasoning, "Market Reasoning"),
        (probability_assessment, ProbabilityAssessment, "Probability"),
        (expected_value_assessment, ExpectedValueAssessment, "Expected Value"),
        (position_intelligence_assessment, PositionIntelligenceAssessment, "Position Intelligence"),
    )
    for value, expected_type, name in expected_types:
        if not isinstance(value, expected_type):
            raise TypeError(f"ATPE requires a {name} object")
    if (reasoning.understanding is not understanding or
            probability_assessment.understanding is not understanding or
            probability_assessment.reasoning is not reasoning or
            expected_value_assessment.understanding is not understanding or
            expected_value_assessment.reasoning is not reasoning or
            expected_value_assessment.probability_assessment is not probability_assessment or
            position_intelligence_assessment.understanding is not understanding or
            position_intelligence_assessment.reasoning is not reasoning or
            position_intelligence_assessment.probability_assessment is not probability_assessment or
            position_intelligence_assessment.expected_value_assessment is not expected_value_assessment):
        raise ValueError("ATPE requires matching Brain analytical lineage")

    personality, confidence = _selection(understanding, probability_assessment, expected_value_assessment, position_intelligence_assessment)
    management, actions, aggression, protection, runner, breakeven, take_profit, partial_exit = _policies(personality)
    return TradingPersonalityAssessment(
        understanding, reasoning, probability_assessment, expected_value_assessment,
        position_intelligence_assessment, personality, confidence, management, actions,
        aggression, protection, runner, breakeven, take_profit, partial_exit,
        "deterministic descriptive posture selection from private Brain context, "
        "non-directional probabilities, normalized expected value, and position "
        "intelligence; shadow mode only with no execution authority",
    )
