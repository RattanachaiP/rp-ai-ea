"""Private Market Reasoning for the V26 compatibility runtime.

The reasoning object explains the already-interpreted market context.  It has
no decision, scoring, probability, expectancy, risk, or execution dependency
and is deliberately never published in ``decision.json``.
"""

from __future__ import annotations

from dataclasses import dataclass

from brain.market_understanding import MarketUnderstanding


@dataclass(frozen=True)
class MarketReasoning:
    """Immutable, internal-only explanation of a Market Understanding."""

    understanding: MarketUnderstanding
    market_state_explanation: str
    continuation_case: str
    reversal_case: str
    wait_case: str
    supporting_evidence: tuple[str, ...]
    conflicting_evidence: tuple[str, ...]
    uncertainty: tuple[str, ...]
    narrative: str


def reason_about_market(understanding: MarketUnderstanding) -> MarketReasoning:
    """Explain context without evaluating, selecting, or sizing a trade."""
    if not isinstance(understanding, MarketUnderstanding):
        raise TypeError("Market Reasoning requires a MarketUnderstanding object")

    support: list[str] = []
    conflict: list[str] = []
    uncertainty: list[str] = list(understanding.invalid_conditions)
    trend = understanding.trend_state
    structure = understanding.market_structure
    momentum = understanding.momentum_context

    if understanding.market_regime == "TRENDING":
        support.append(f"regime={understanding.market_regime}")
        support.append(f"trend_state={trend}")
    else:
        uncertainty.append(f"regime={understanding.market_regime}")
    if structure in {"HH_HL", "LH_LL"}:
        support.append(f"structure={structure}")
    else:
        uncertainty.append("structure is not confirmed")
    if momentum.endswith("MOMENTUM_ALIGNED"):
        support.append(f"momentum={momentum}")
    elif momentum == "MIXED_MOMENTUM":
        conflict.append("momentum is mixed")
    else:
        conflict.append(f"momentum={momentum}")
    if understanding.transition_state == "TRANSITION_OBSERVED":
        conflict.append("transition context is observed")
    if understanding.liquidity_context != "NO_LIQUIDITY_SWEEP_OBSERVED":
        conflict.append(f"liquidity={understanding.liquidity_context}")
    if understanding.expansion_compression == "COMPRESSION":
        uncertainty.append("compression may precede expansion in either direction")
    if understanding.context_quality != "COMPLETE":
        uncertainty.append(f"context_quality={understanding.context_quality}")

    explanation = (
        f"Market is described as {understanding.market_regime} with {trend}, "
        f"structure {structure}, and {momentum}."
    )
    continuation = (
        "Continuation is contextually possible when the established trend, "
        "structure, and aligned momentum remain intact."
        if support else
        "Continuation is possible only if currently incomplete context becomes aligned."
    )
    reversal = (
        "Reversal is contextually possible because " + "; ".join(conflict) + "."
        if conflict else
        "Reversal remains possible if the observed trend, structure, or momentum fails."
    )
    wait = (
        "Waiting may be preferable while " + "; ".join(uncertainty) + "."
        if uncertainty else
        "Waiting may be preferable until the current context remains coherent."
    )
    narrative = f"{explanation} {continuation} {reversal} {wait}"
    return MarketReasoning(
        understanding=understanding,
        market_state_explanation=explanation,
        continuation_case=continuation,
        reversal_case=reversal,
        wait_case=wait,
        supporting_evidence=tuple(support),
        conflicting_evidence=tuple(conflict),
        uncertainty=tuple(uncertainty),
        narrative=narrative,
    )
