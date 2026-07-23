"""Deterministic, dependency-free significance calculations."""
from __future__ import annotations
import math

# Two-sided 95% normal critical value.  This is intentionally fixed so results
# cannot drift with a third-party statistics package version.
Z_95 = 1.959963984540054

def win_rate_standard_error(wins: int, samples: int) -> float:
    if samples <= 0: return 0.0
    p = wins / samples
    return math.sqrt(p * (1.0 - p) / samples)

def is_win_rate_significant(wins: int, samples: int, *, baseline: float = 0.5, alpha_z: float = Z_95) -> bool:
    """Return whether the observed win rate differs from *baseline* at 95%."""
    if samples <= 0 or not 0.0 <= baseline <= 1.0: return False
    se = math.sqrt(baseline * (1.0 - baseline) / samples)
    return se == 0.0 or abs((wins / samples) - baseline) >= alpha_z * se
def calculate_significance(wins: int, samples: int, *, baseline: float = 0.5) -> float:
    """Return the absolute normal-test z score against the supplied baseline."""
    if samples <= 0 or not 0.0 < baseline < 1.0: return 0.0
    return abs((wins / samples - baseline) / math.sqrt(baseline * (1 - baseline) / samples))
