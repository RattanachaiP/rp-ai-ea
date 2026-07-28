"""Describe relative bar-range behaviour."""
from __future__ import annotations
from typing import Any, Mapping


def describe_volatility(snapshot: Mapping[str, Any]) -> dict[str, Any]:
    ranges = snapshot["ranges"]
    if len(ranges) < 5:
        return {"state": "UNDETERMINED", "range_ratio": None, "explanation": "fewer than 5 valid closed bars"}
    baseline = sum(ranges[:-2]) / len(ranges[:-2])
    recent = sum(ranges[-2:]) / 2
    ratio = recent / baseline if baseline > 0 else 1.0
    state = "COMPRESSION" if ratio < .65 else "LOW_VOLATILITY" if ratio < .85 else "HIGH_VOLATILITY" if ratio > 1.75 else "EXPANSION" if ratio > 1.25 else "NORMAL"
    return {"state": state, "range_ratio": round(ratio, 6),
            "explanation": f"recent mean range is {ratio:.2f}x its preceding baseline"}
