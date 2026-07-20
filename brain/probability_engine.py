"""Internal market-state probability estimates for the V26 compatibility runtime.

The engine consumes only Brain interpretation and explanation objects.  Its
immutable output is analytical telemetry kept in process: it is not a trade
signal, confidence value, score, risk instruction, or publication payload.
"""

from __future__ import annotations

from dataclasses import dataclass

from brain.market_reasoning import MarketReasoning
from brain.market_understanding import MarketUnderstanding


@dataclass(frozen=True)
class MarketStateProbability:
    """One bounded market-state estimate with its analytical evidence."""

    probability: float
    supporting_evidence: tuple[str, ...]
    conflicting_evidence: tuple[str, ...]
    uncertainty_estimate: float
    uncertainty_evidence: tuple[str, ...]


@dataclass(frozen=True)
class ProbabilityAssessment:
    """Private, immutable distribution across non-directional market states."""

    understanding: MarketUnderstanding
    reasoning: MarketReasoning
    continuation: MarketStateProbability
    reversal: MarketStateProbability
    range: MarketStateProbability
    breakout: MarketStateProbability
    no_trade: MarketStateProbability
    methodology: str


def _evidence(items: list[str], fallback: str) -> tuple[str, ...]:
    return tuple(items) if items else (fallback,)


def _uncertainty(understanding: MarketUnderstanding, reasoning: MarketReasoning) -> tuple[float, tuple[str, ...]]:
    evidence = list(reasoning.uncertainty)
    if understanding.context_quality == "INSUFFICIENT":
        evidence.append("context quality is insufficient")
    elif understanding.context_quality == "PARTIAL":
        evidence.append("context quality is partial")
    estimate = min(1.0, 0.10 + 0.12 * len(set(evidence)))
    return round(estimate, 4), _evidence(evidence, "context is coherent")


def _estimate(weight: float, support: list[str], conflict: list[str], uncertainty: float,
              uncertainty_evidence: tuple[str, ...]) -> MarketStateProbability:
    return MarketStateProbability(
        probability=round(weight, 4),
        supporting_evidence=_evidence(support, "no state-specific support observed"),
        conflicting_evidence=_evidence(conflict, "no state-specific conflict observed"),
        uncertainty_estimate=uncertainty,
        uncertainty_evidence=uncertainty_evidence,
    )


def estimate_market_probabilities(
    understanding: MarketUnderstanding, reasoning: MarketReasoning,
) -> ProbabilityAssessment:
    """Estimate market states only; never infer a BUY or SELL probability.

    A transparent additive evidence model starts each state at equal weight,
    applies context-only adjustments, clips at zero, and normalizes to one.
    The result is intentionally detached from every production decision path.
    """
    if not isinstance(understanding, MarketUnderstanding):
        raise TypeError("Probability Engine requires a MarketUnderstanding object")
    if not isinstance(reasoning, MarketReasoning):
        raise TypeError("Probability Engine requires a MarketReasoning object")
    if reasoning.understanding is not understanding:
        raise ValueError("Probability Engine requires reasoning for the supplied understanding")

    weights = {name: 1.0 for name in ("continuation", "reversal", "range", "breakout", "no_trade")}
    support = {name: [] for name in weights}
    conflict = {name: [] for name in weights}

    if understanding.market_regime == "TRENDING":
        weights["continuation"] += 1.4
        support["continuation"].append("trending regime")
        conflict["range"].append("trending regime conflicts with range persistence")
    elif understanding.market_regime == "RANGE_OR_UNDEFINED":
        weights["range"] += 1.4
        support["range"].append("range or undefined regime")
        conflict["continuation"].append("no established trend regime")
    else:
        weights["reversal"] += 0.7
        weights["no_trade"] += 0.5
        support["reversal"].append("transition context")
        support["no_trade"].append("transition context")

    if understanding.market_structure in {"HH_HL", "LH_LL"}:
        weights["continuation"] += 0.8
        support["continuation"].append(f"confirmed structure={understanding.market_structure}")
    else:
        weights["no_trade"] += 0.6
        support["no_trade"].append("structure is unconfirmed")

    if understanding.momentum_context.endswith("MOMENTUM_ALIGNED"):
        weights["continuation"] += 0.8
        support["continuation"].append(f"{understanding.momentum_context}")
    elif understanding.momentum_context == "MIXED_MOMENTUM":
        weights["range"] += 0.5
        weights["no_trade"] += 0.4
        support["range"].append("mixed momentum")
        support["no_trade"].append("mixed momentum")
    else:
        weights["reversal"] += 0.6
        conflict["continuation"].append(understanding.momentum_context)
        support["reversal"].append("momentum and impulse diverge")

    if understanding.expansion_compression == "COMPRESSION":
        weights["breakout"] += 1.0
        support["breakout"].append("compression context")
    elif understanding.expansion_compression == "EXPANSION":
        weights["continuation"] += 0.4
        support["continuation"].append("expansion context")

    if understanding.transition_state == "TRANSITION_OBSERVED":
        weights["reversal"] += 0.8
        weights["no_trade"] += 0.5
        support["reversal"].append("transition observed")
        support["no_trade"].append("transition observed")
        conflict["continuation"].append("transition conflicts with stable continuation")
    if understanding.liquidity_context != "NO_LIQUIDITY_SWEEP_OBSERVED":
        weights["reversal"] += 0.7
        support["reversal"].append(understanding.liquidity_context)
        conflict["continuation"].append(understanding.liquidity_context)

    uncertainty, uncertainty_evidence = _uncertainty(understanding, reasoning)
    if understanding.context_quality != "COMPLETE":
        weights["no_trade"] += 1.2
        support["no_trade"].append(f"context_quality={understanding.context_quality}")
    total = sum(max(0.0, value) for value in weights.values())
    normalized = {name: max(0.0, value) / total for name, value in weights.items()}

    return ProbabilityAssessment(
        understanding=understanding, reasoning=reasoning,
        continuation=_estimate(normalized["continuation"], support["continuation"], conflict["continuation"], uncertainty, uncertainty_evidence),
        reversal=_estimate(normalized["reversal"], support["reversal"], conflict["reversal"], uncertainty, uncertainty_evidence),
        range=_estimate(normalized["range"], support["range"], conflict["range"], uncertainty, uncertainty_evidence),
        breakout=_estimate(normalized["breakout"], support["breakout"], conflict["breakout"], uncertainty, uncertainty_evidence),
        no_trade=_estimate(normalized["no_trade"], support["no_trade"], conflict["no_trade"], uncertainty, uncertainty_evidence),
        methodology="equal-prior additive context evidence normalized across market states",
    )
