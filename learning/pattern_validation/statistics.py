"""Governed historical-quality checks; consistency never grants authority."""
from __future__ import annotations
from typing import Any


def assess(*, sample_count: int, support: float, expectancy: float, confidence: float,
           config: dict[str, Any]) -> tuple[str, tuple[str, ...], dict[str, Any]]:
    structural = []
    if sample_count == 0 and (support != 0 or confidence != 0):
        structural.append("SAMPLE_CONSISTENCY_FAILED")
    if sample_count > 0 and support <= 0:
        structural.append("SUPPORT_CONSISTENCY_FAILED")
    if confidence > support:
        structural.append("CONFIDENCE_CONSISTENCY_FAILED")
    statistics = {"sample_count": sample_count, "support": support, "expectancy": expectancy,
                  "confidence": confidence, "thresholds": dict(config)}
    if structural:
        return "INVALID", tuple(structural), statistics
    if sample_count < config["minimum_sample_count"]:
        return "INSUFFICIENT_EVIDENCE", ("MINIMUM_SAMPLE_COUNT_NOT_MET",), statistics
    failures = []
    for field in ("support", "confidence", "expectancy"):
        if statistics[field] < config[f"minimum_{field}"]:
            failures.append(f"MINIMUM_{field.upper()}_NOT_MET")
    if failures:
        return "INVALID", tuple(failures), statistics
    return "STATISTICALLY_CONSISTENT", ("GOVERNED_HISTORICAL_CHECKS_PASSED",), statistics
