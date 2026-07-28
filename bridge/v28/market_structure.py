"""Describe price structure without producing trading intent."""
from __future__ import annotations
from typing import Any, Mapping


def describe_structure(snapshot: Mapping[str, Any]) -> dict[str, Any]:
    bars = snapshot["bars"]
    if len(bars) < 5:
        return {"condition": "UNDETERMINED", "high_pattern": "UNKNOWN", "low_pattern": "UNKNOWN",
                "explanation": "fewer than 5 valid closed bars"}
    older, recent = bars[-5:-2], bars[-3:]
    old_high, new_high = max(x["high"] for x in older), max(x["high"] for x in recent)
    old_low, new_low = min(x["low"] for x in older), min(x["low"] for x in recent)
    high_pattern = "HIGHER_HIGH" if new_high > old_high else "LOWER_HIGH" if new_high < old_high else "EQUAL_HIGH"
    low_pattern = "HIGHER_LOW" if new_low > old_low else "LOWER_LOW" if new_low < old_low else "EQUAL_LOW"
    if high_pattern == "HIGHER_HIGH" and low_pattern == "HIGHER_LOW":
        condition = "ADVANCING"
    elif high_pattern == "LOWER_HIGH" and low_pattern == "LOWER_LOW":
        condition = "DECLINING"
    elif new_high <= old_high and new_low >= old_low:
        condition = "RANGE"
    else:
        condition = "EXPANSION"
    return {"condition": condition, "high_pattern": high_pattern, "low_pattern": low_pattern,
            "explanation": f"recent extremes {new_low:g}-{new_high:g} versus prior {old_low:g}-{old_high:g}"}
