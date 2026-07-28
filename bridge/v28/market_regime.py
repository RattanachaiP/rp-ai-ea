"""Classify governed combinations of descriptive contexts."""
from .context_contracts import RegimeContext


def identify_regime(structure, volatility, momentum, policy):
    quality = next((x.data_quality for x in (structure, volatility, momentum) if x.data_quality != "VALID"), "VALID")
    evidence = {"structure_state": structure.state, "volatility_state": volatility.state,
                "volatility_phase": volatility.evidence.get("volatility_phase"), "momentum_state": momentum.state}
    if quality != "VALID":
        return RegimeContext("UNDETERMINED", evidence, "required contexts are unavailable", quality, policy.policy_id, policy.version)
    phase = volatility.evidence["volatility_phase"]
    if phase == "EXPANSION": state = "EXPANSION"
    elif phase == "COMPRESSION": state = "TRANSITION"
    elif structure.state in ("ADVANCING", "DECLINING"): state = "TREND"
    elif structure.state == "RANGE": state = "RANGE"
    else: state = "VOLATILITY_SHIFT"
    return RegimeContext(state, evidence, f"governed context combination describes {state.lower()}", "VALID", policy.policy_id, policy.version)
