"""Decision-risk precheck only; this module does not claim full risk eligibility."""
from .decision_contract import DecisionRiskPrecheck


def evaluate_risk_precheck(expectancy, candidate, opportunity, *contexts):
    if any(context.data_quality != "VALID" for context in (opportunity,) + contexts):
        return DecisionRiskPrecheck("DECISION_RISK_PRECHECK_REJECTED", ("CONTEXT_QUALITY_NOT_VALID",),
                                    "degraded Market Intelligence fails closed")
    if not candidate.authorized:
        return DecisionRiskPrecheck("DECISION_RISK_PRECHECK_REJECTED", candidate.authorization_reasons,
                                    "candidate scope or authority is incomplete")
    if expectancy.status != "POSITIVE_EXPECTANCY":
        return DecisionRiskPrecheck("DECISION_RISK_PRECHECK_REJECTED", ("POSITIVE_EXPECTANCY_REQUIRED",),
                                    "risk review cannot rescue an unverified edge")
    return DecisionRiskPrecheck("RISK_REVIEW_READY", ("EXPECTANCY_VERIFIED", "CANDIDATE_AUTHORIZED"),
                                "candidate may proceed to separately governed full risk review")
