"""Verify positive expectancy from governed Market Intelligence evidence only."""
from math import isfinite
from collections.abc import Mapping
from .decision_contract import ExpectancyContext


def evaluate_expectancy(opportunity, trend, structure, momentum, volatility, liquidity):
    contexts = (opportunity, trend, structure, momentum, volatility, liquidity)
    degraded = tuple(type(c).__name__ for c in contexts if c.data_quality != "VALID")
    support = tuple(str(x) for x in opportunity.evidence.get("supporting_evidence", ()))
    conflicts = tuple(str(x) for x in opportunity.evidence.get("conflicting_evidence", ()))
    edge = opportunity.evidence.get("edge_verification", {})
    required = ("win_probability", "average_win_r", "average_loss_r", "expected_cost_r",
                "net_expectancy_r", "sample_size", "statistical_confidence", "evidence_id")
    valid = isinstance(edge, Mapping) and all(k in edge for k in required)
    if valid:
        numbers = tuple(edge[k] for k in required[:-1])
        valid = all(type(x) in (int, float) and isfinite(x) for x in numbers)
    if valid:
        calculated = edge["win_probability"] * edge["average_win_r"] - (
            1 - edge["win_probability"]) * edge["average_loss_r"] - edge["expected_cost_r"]
        valid = (0 <= edge["win_probability"] <= 1 and edge["average_win_r"] > 0
                 and edge["average_loss_r"] > 0 and edge["expected_cost_r"] >= 0
                 and edge["sample_size"] >= 30 and 0 <= edge["statistical_confidence"] <= 1
                 and abs(calculated - edge["net_expectancy_r"]) <= 1e-9)
    positive = valid and edge["net_expectancy_r"] > 0 and edge["statistical_confidence"] >= .75 and not degraded
    quality = min(1.0, max(0.0, float(edge.get("statistical_confidence", 0.0)))) if valid else 0.0
    why = "historical opportunity evidence establishes positive net expectancy" if positive else "positive expectancy is not established"
    rejected = conflicts + tuple(f"DEGRADED_{x}" for x in degraded)
    return ExpectancyContext("POSITIVE_EXPECTANCY" if positive else "EXPECTANCY_NOT_ESTABLISHED",
                             quality, support, rejected, why, str(edge.get("evidence_id", "MISSING")))
