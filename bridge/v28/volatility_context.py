"""Describe volatility level separately from volatility phase."""
from .context_contracts import VolatilityContext
from .intelligence_policy import IntelligencePolicy


def describe_volatility(snapshot, policy: IntelligencePolicy) -> VolatilityContext:
    common = (policy.policy_id, policy.version)
    if snapshot.data_quality != "VALID":
        return VolatilityContext("UNDETERMINED", {"rejection_reasons": snapshot.rejection_reasons,
            "valid_bar_count": snapshot.valid_bar_count}, "volatility evidence unavailable", snapshot.data_quality, *common)
    governed_window = snapshot.ranges[-policy.minimum_bars:]
    baseline_values = governed_window[:policy.volatility_baseline_window]
    recent_values = snapshot.ranges[-policy.volatility_recent_window:]
    baseline, recent = sum(baseline_values) / len(baseline_values), sum(recent_values) / len(recent_values)
    ratio = recent / baseline if baseline > 0 else 1.0
    level = "HIGH" if ratio >= policy.high_level_ratio else "LOW" if ratio <= policy.low_level_ratio else "NORMAL"
    phase = "COMPRESSION" if ratio <= policy.compression_ratio else "EXPANSION" if ratio >= policy.expansion_ratio else "STABLE"
    state = "SHIFT" if phase != "STABLE" else "STABLE"
    evidence = {"volatility_level": level, "volatility_phase": phase, "raw_ratio": ratio,
                "baseline_ranges": baseline_values, "recent_ranges": recent_values,
                "thresholds": {"compression": policy.compression_ratio, "low_level": policy.low_level_ratio,
                               "expansion": policy.expansion_ratio, "high_level": policy.high_level_ratio}}
    return VolatilityContext(state, evidence, f"volatility level is {level.lower()} while phase is {phase.lower()}", "VALID", *common)
