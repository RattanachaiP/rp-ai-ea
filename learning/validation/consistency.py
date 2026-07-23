"""Stability and consistency metrics."""
from __future__ import annotations
from collections.abc import Iterable
from statistics import pstdev

def coefficient_of_variation(values: Iterable[float]) -> float:
    items = [float(value) for value in values]
    if len(items) < 2: return 0.0
    mean = sum(items) / len(items)
    return 0.0 if mean == 0.0 else abs(pstdev(items) / mean)

def stability_score(values: Iterable[float]) -> float:
    """A deterministic [0, 1] score: one means no observed variation."""
    return 1.0 / (1.0 + coefficient_of_variation(values))

def consistency_score(*series: Iterable[float]) -> float:
    scores = [stability_score(values) for values in series]
    return sum(scores) / len(scores) if scores else 0.0
