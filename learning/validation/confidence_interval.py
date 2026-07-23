"""Confidence intervals used in validation reports."""
from __future__ import annotations
import math
from .significance import Z_95

def proportion_confidence_interval(successes: int, samples: int, *, z: float = Z_95) -> tuple[float, float]:
    """Wilson score interval, bounded to [0, 1]."""
    if samples <= 0: return (0.0, 0.0)
    p = successes / samples; denominator = 1 + z * z / samples
    centre = (p + z * z / (2 * samples)) / denominator
    margin = z * math.sqrt((p * (1 - p) + z * z / (4 * samples)) / samples) / denominator
    return (max(0.0, centre - margin), min(1.0, centre + margin))
calculate_confidence_interval = proportion_confidence_interval
