"""Pure validation statistics and evidence classification."""
from __future__ import annotations

from math import isfinite
from typing import Any

MINIMUM_SAMPLE_COUNT = 30


def assess(*, sample_count: int, support: float, expectancy: float,
           confidence: float) -> tuple[str, tuple[str, ...], dict[str, Any]]:
    reasons: list[str] = []
    if sample_count == 0 and (support != 0 or confidence != 0):
        reasons.append("SAMPLE_CONSISTENCY_FAILED")
    if sample_count > 0 and support <= 0:
        reasons.append("SUPPORT_CONSISTENCY_FAILED")
    if not isfinite(expectancy):
        reasons.append("EXPECTANCY_CONSISTENCY_FAILED")
    if confidence > support:
        reasons.append("CONFIDENCE_CONSISTENCY_FAILED")
    statistics = {"sample_count": sample_count, "support": support, "expectancy": expectancy,
                  "confidence": confidence, "minimum_sample_count": MINIMUM_SAMPLE_COUNT}
    if reasons:
        return "INVALID", tuple(reasons), statistics
    if sample_count < MINIMUM_SAMPLE_COUNT:
        return "INSUFFICIENT_EVIDENCE", ("MINIMUM_SAMPLE_COUNT_NOT_MET",), statistics
    return "VALIDATED", ("HISTORICAL_VALIDATION_PASSED",), statistics
