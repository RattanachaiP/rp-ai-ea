"""Construct deterministic, explainable confidence from context reliability."""
from .decision_contract import Confidence


def build_confidence(expectancy, opportunity, *contexts):
    valid_ratio = sum(c.data_quality == "VALID" for c in (opportunity,) + contexts) / (len(contexts) + 1)
    maturity = 1.0 if opportunity.state == "PRESENT" else 0.0
    supporting = len(expectancy.supporting_evidence)
    conflicting = len(expectancy.conflicting_evidence)
    agreement = supporting / max(1, supporting + conflicting)
    factors = {"market_agreement": agreement, "evidence_consistency": agreement,
               "opportunity_maturity": maturity, "context_reliability": valid_ratio,
               "data_quality": valid_ratio, "expectancy_quality": expectancy.expected_quality}
    value = round(sum(factors.values()) / len(factors), 6)
    band = "HIGH" if value >= .9 else "SUFFICIENT" if value >= .75 else "INSUFFICIENT"
    return Confidence(value, band, factors, f"deterministic mean of {len(factors)} governed factors", value >= .75)
