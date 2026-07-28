"""Report observed price geometry; liquidity remains a labelled hypothesis."""
from .context_contracts import LiquidityContext


def describe_liquidity(snapshot, policy):
    if snapshot.data_quality != "VALID":
        return LiquidityContext("UNDETERMINED", {"rejection_reasons": snapshot.rejection_reasons,
            "valid_bar_count": snapshot.valid_bar_count}, "price geometry is unavailable", snapshot.data_quality, policy.policy_id, policy.version)
    bars = snapshot.bars[-policy.liquidity_window:]
    upper, lower = max(x["high"] for x in bars), min(x["low"] for x in bars)
    span, mid = upper - lower, snapshot.mid
    tolerance = span * policy.equal_extrema_tolerance_ratio
    facts = []
    if abs(bars[-1]["high"] - bars[-2]["high"]) <= tolerance: facts.append("VISIBLE_EQUAL_HIGH")
    if abs(bars[-1]["low"] - bars[-2]["low"]) <= tolerance: facts.append("VISIBLE_EQUAL_LOW")
    if bars[-1]["low"] > bars[-2]["high"]: facts.append("PRICE_GAP_UP")
    if bars[-1]["high"] < bars[-2]["low"]: facts.append("PRICE_GAP_DOWN")
    location = "ABOVE_OBSERVED_RANGE" if mid > upper else "BELOW_OBSERVED_RANGE" if mid < lower else "INSIDE_OBSERVED_RANGE"
    distances = {"upper": max(0.0, upper-mid), "lower": max(0.0, mid-lower)} if location == "INSIDE_OBSERVED_RANGE" else {"upper": abs(upper-mid), "lower": abs(mid-lower)}
    nearest = "UPPER" if distances["upper"] <= distances["lower"] else "LOWER"
    evidence = {"observed_facts": tuple(facts), "observed_range": {"upper": upper, "lower": lower},
                "price_location": location, "boundary_distances": distances, "nearest_observed_boundary": nearest,
                "equal_extrema_tolerance": tolerance, "hypothesis": "POTENTIAL_LIQUIDITY_NEAR_VISIBLE_GEOMETRY",
                "hypothesis_evidence_quality": "GEOMETRY_ONLY"}
    return LiquidityContext("OBSERVED_GEOMETRY", evidence, "visible geometry is factual; liquidity interpretation is hypothesis only", "VALID", policy.policy_id, policy.version)
