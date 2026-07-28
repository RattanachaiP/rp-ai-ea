"""Describe visible price pools and untraded gaps."""
from __future__ import annotations
from typing import Any, Mapping


def describe_liquidity(snapshot: Mapping[str, Any]) -> dict[str, Any]:
    bars = snapshot["bars"]
    if len(bars) < 5:
        return {"nearest_pool": "UNDETERMINED", "features": (), "explanation": "fewer than 5 valid closed bars"}
    span = max(x["high"] for x in bars[-5:]) - min(x["low"] for x in bars[-5:])
    tolerance = span * .05
    features: list[str] = []
    if abs(bars[-1]["high"] - bars[-2]["high"]) <= tolerance:
        features.append("EQUAL_HIGH")
    if abs(bars[-1]["low"] - bars[-2]["low"]) <= tolerance:
        features.append("EQUAL_LOW")
    if bars[-1]["low"] > bars[-2]["high"] or bars[-1]["high"] < bars[-2]["low"]:
        features.append("LIQUIDITY_VOID")
    mid = snapshot["mid"]
    upper, lower = max(x["high"] for x in bars[-5:]), min(x["low"] for x in bars[-5:])
    nearest = "EXTERNAL_HIGH" if upper - mid <= mid - lower else "EXTERNAL_LOW"
    return {"nearest_pool": nearest, "features": tuple(features) or ("INTERNAL",),
            "explanation": f"nearest five-bar external boundary is {nearest.lower()}"}
