"""Describe non-overlapping price-structure cohorts."""
from .context_contracts import StructureContext
from .intelligence_policy import IntelligencePolicy


def describe_structure(snapshot, policy: IntelligencePolicy) -> StructureContext:
    common = (policy.policy_id, policy.version)
    if snapshot.data_quality != "VALID":
        return StructureContext("UNDETERMINED", {"input_bar_count": snapshot.input_bar_count,
            "valid_bar_count": snapshot.valid_bar_count, "rejection_reasons": snapshot.rejection_reasons},
            "closed-bar evidence did not pass policy", snapshot.data_quality, *common)
    prior = snapshot.bars[-(policy.structure_prior_window + policy.structure_recent_window):-policy.structure_recent_window]
    recent = snapshot.bars[-policy.structure_recent_window:]
    old_high, new_high = max(x["high"] for x in prior), max(x["high"] for x in recent)
    old_low, new_low = min(x["low"] for x in prior), min(x["low"] for x in recent)
    if new_high > old_high and new_low > old_low: state = "ADVANCING"
    elif new_high < old_high and new_low < old_low: state = "DECLINING"
    elif new_high <= old_high and new_low >= old_low: state = "RANGE"
    else: state = "EXPANSION"
    evidence = {"prior_timestamps": tuple(x["timestamp"] for x in prior), "recent_timestamps": tuple(x["timestamp"] for x in recent),
                "prior_extrema": {"high": old_high, "low": old_low}, "recent_extrema": {"high": new_high, "low": new_low},
                "cohorts_overlap": False}
    return StructureContext(state, evidence, f"independent extrema cohorts describe {state.lower()} structure", "VALID", *common)
