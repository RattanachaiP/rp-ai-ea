"""Describe price displacement quality from candle bodies."""
from __future__ import annotations
from typing import Any, Mapping


def describe_momentum(snapshot: Mapping[str, Any], trend: Mapping[str, Any]) -> dict[str, Any]:
    bodies = snapshot["bodies"]
    bars = snapshot["bars"]
    if len(bodies) < 5:
        return {"state": "UNDETERMINED", "alignment": "UNKNOWN", "explanation": "fewer than 5 valid closed bars"}
    previous = sum(bodies[-4:-2]) / 2
    recent = sum(bodies[-2:]) / 2
    ratio = recent / previous if previous > 0 else 1.0
    state = "ACCELERATION" if ratio > 1.3 else "DECELERATION" if ratio < .7 else "CONTINUATION"
    signs = [bar["close"] - bar["open"] for bar in bars[-2:]]
    expected_positive = trend["direction"] == "UPWARD"
    aligned = trend["direction"] in ("UPWARD", "DOWNWARD") and all((x > 0) == expected_positive and x != 0 for x in signs)
    return {"state": state, "alignment": "ALIGNED" if aligned else "MIXED", "body_ratio": round(ratio, 6),
            "explanation": f"recent mean body is {ratio:.2f}x the preceding two-bar mean"}
