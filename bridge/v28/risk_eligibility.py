"""Determine risk eligibility without reconstructing market analysis."""
from .decision_contract import RiskEligibility


def evaluate_risk_eligibility(expectancy, opportunity, *contexts):
    all_contexts = (opportunity,) + contexts
    if any(c.data_quality != "VALID" for c in all_contexts):
        return RiskEligibility("RISK_REJECTED", ("CONTEXT_QUALITY_NOT_VALID",), "degraded evidence fails closed")
    if opportunity.state != "PRESENT":
        return RiskEligibility("RISK_DEFERRED", ("OPPORTUNITY_NOT_PRESENT",), "opportunity is not mature")
    if expectancy.status != "POSITIVE_EXPECTANCY":
        return RiskEligibility("RISK_REJECTED", ("POSITIVE_EXPECTANCY_REQUIRED",), "risk cannot rescue an unverified edge")
    if opportunity.evidence.get("evidence_quality") != "VALID":
        return RiskEligibility("RISK_REJECTED", ("EVIDENCE_QUALITY_NOT_VALID",), "evidence quality is insufficient")
    return RiskEligibility("RISK_ELIGIBLE", ("EDGE_VERIFIED", "CONTEXTS_CONSISTENT", "OPPORTUNITY_MATURE"),
                           "verified edge and consistent contexts justify risk review")
