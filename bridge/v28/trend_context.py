"""Describe directional environment; this module has no trading vocabulary."""
from __future__ import annotations
from typing import Any, Mapping


def describe_trend(snapshot: Mapping[str, Any], structure: Mapping[str, Any]) -> dict[str, Any]:
    bars = snapshot["bars"]
    if len(bars) < 5:
        return {"direction": "UNDETERMINED", "persistence": "UNKNOWN", "explanation": "insufficient structure history"}
    direction = {"ADVANCING": "UPWARD", "DECLINING": "DOWNWARD"}.get(structure["condition"], "SIDEWAYS")
    changes = [bars[i]["close"] - bars[i - 1]["close"] for i in range(1, len(bars))]
    aligned = sum(change > 0 for change in changes[-4:]) if direction == "UPWARD" else sum(change < 0 for change in changes[-4:]) if direction == "DOWNWARD" else 0
    persistence = "PERSISTENT" if aligned >= 3 else "MIXED"
    return {"direction": direction, "persistence": persistence,
            "explanation": f"{structure['condition']} structure with {aligned}/4 aligned close changes"}
