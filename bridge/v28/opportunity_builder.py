"""Build a neutral, non-executable opportunity representation."""
from .context_contracts import OpportunityContext


def build_opportunity(structure, regime, trend, momentum, volatility, liquidity, policy):
    contexts = (structure, regime, trend, momentum, volatility, liquidity)
    quality = next((x.data_quality for x in contexts if x.data_quality != "VALID"), "VALID")
    supporting, conflicting = [], []
    if regime.state in ("TREND", "EXPANSION"): supporting.append(f"REGIME_{regime.state}")
    else: conflicting.append(f"REGIME_{regime.state}")
    if momentum.evidence.get("alignment") == "ALIGNED": supporting.append("MOMENTUM_ALIGNED")
    else: conflicting.append("MOMENTUM_NOT_ALIGNED")
    present = quality == "VALID" and len(supporting) == 2
    state = "PRESENT" if present else "UNDETERMINED" if quality != "VALID" else "ABSENT"
    archetype = "DIRECTIONAL_CONTINUATION" if present and regime.state == "TREND" else "DIRECTIONAL_EXPANSION" if present else "NONE"
    side = trend.state if trend.state in ("UPWARD", "DOWNWARD") else "NEUTRAL"
    evidence = {"presence": present, "archetype": archetype, "market_side_context": side,
                "supporting_evidence": tuple(supporting), "conflicting_evidence": tuple(conflicting),
                "evidence_quality": quality, "invalidation_conditions": ("CONTEXT_QUALITY_NOT_VALID",
                "REGIME_COHERENCE_LOST", "MOMENTUM_ALIGNMENT_LOST"), "executable": False}
    return OpportunityContext(state, evidence, "neutral market opportunity representation; no action authority", quality, policy.policy_id, policy.version)
