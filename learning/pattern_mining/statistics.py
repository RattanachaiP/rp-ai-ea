"""Pure, deterministic candidate-pattern statistics."""
from __future__ import annotations

from math import isfinite
from typing import Iterable

from .exceptions import PatternMiningError


def calculate(outcomes: Iterable[float], total_samples: int) -> dict[str, int | float]:
    values = tuple(outcomes)
    if (not isinstance(total_samples, int) or isinstance(total_samples, bool) or total_samples < 0
            or not values or any(isinstance(x, bool) or not isinstance(x, (int, float)) or not isfinite(x) for x in values)
            or len(values) > total_samples):
        raise PatternMiningError("INVALID_STATISTICS")
    wins = sum(value > 0 for value in values)
    losses = sum(value < 0 for value in values)
    neutral = len(values) - wins - losses
    support = len(values) / total_samples if total_samples else 0.0
    expectancy = sum(values) / len(values)
    confidence = support * ((wins + neutral * 0.5) / len(values))
    if not all(isfinite(x) for x in (support, expectancy, confidence)):
        raise PatternMiningError("INVALID_STATISTICS")
    return {"sample_count": len(values), "win_count": wins, "loss_count": losses,
            "neutral_count": neutral, "support": support, "expectancy": expectancy,
            "confidence": confidence}
