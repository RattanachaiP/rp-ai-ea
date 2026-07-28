"""Classify the market environment from structural and volatility descriptions."""
from __future__ import annotations
from typing import Any, Mapping


def identify_regime(structure: Mapping[str, Any], volatility: Mapping[str, Any], momentum: Mapping[str, Any]) -> dict[str, Any]:
    if "UNDETERMINED" in (structure["condition"], volatility["state"], momentum["state"]):
        return {"state": "UNDETERMINED", "explanation": "one or more required contexts are undetermined"}
    if volatility["state"] in ("EXPANSION", "HIGH_VOLATILITY"):
        state = "EXPANSION"
    elif volatility["state"] == "COMPRESSION":
        state = "TRANSITION"
    elif structure["condition"] in ("ADVANCING", "DECLINING"):
        state = "EXHAUSTION" if momentum["state"] == "DECELERATION" else "TREND"
    else:
        state = "RANGE"
    return {"state": state, "explanation": f"{structure['condition'].lower()} structure, {volatility['state'].lower()} volatility, and {momentum['state'].lower()} momentum"}
