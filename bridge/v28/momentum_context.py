"""Describe displacement quality without indicator scoring."""
from .context_contracts import MomentumContext


def describe_momentum(snapshot, trend, policy):
    if trend.data_quality != "VALID":
        return MomentumContext("UNDETERMINED", {"trend_state": trend.state}, "trend evidence is unavailable", trend.data_quality, policy.policy_id, policy.version)
    baseline_values = snapshot.bodies[-(policy.momentum_baseline_window + policy.momentum_recent_window):-policy.momentum_recent_window]
    recent_values = snapshot.bodies[-policy.momentum_recent_window:]
    baseline, recent = sum(baseline_values)/len(baseline_values), sum(recent_values)/len(recent_values)
    ratio = recent / baseline if baseline > 0 else 1.0
    state = "ACCELERATION" if ratio >= policy.momentum_acceleration_ratio else "DECELERATION" if ratio <= policy.momentum_deceleration_ratio else "CONTINUATION"
    signs = tuple(bar["close"] - bar["open"] for bar in snapshot.bars[-policy.momentum_recent_window:])
    aligned = trend.state in ("UPWARD", "DOWNWARD") and all(x > 0 for x in signs) if trend.state == "UPWARD" else trend.state == "DOWNWARD" and all(x < 0 for x in signs)
    return MomentumContext(state, {"raw_ratio": ratio, "baseline_bodies": baseline_values, "recent_bodies": recent_values,
        "alignment": "ALIGNED" if aligned else "MIXED", "thresholds": {"deceleration": policy.momentum_deceleration_ratio,
        "acceleration": policy.momentum_acceleration_ratio}}, f"body displacement is {state.lower()}", "VALID", policy.policy_id, policy.version)
