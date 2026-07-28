"""Construct governed actions exclusively from Decision Intelligence inputs."""
from .decision_contract import (DECISION_POLICY_ID, DECISION_POLICY_VERSION,
                                DECISION_SCHEMA_VERSION, DecisionContext, replay_identity)
from .decision_explainer import explain_decision
from .expectancy_engine import evaluate_expectancy
from .risk_eligibility import evaluate_risk_eligibility
from .confidence_engine import build_confidence


def construct_decision(expectancy, risk, confidence, opportunity):
    executable = opportunity.evidence.get("executable") is True
    side = opportunity.evidence.get("market_side_context")
    direction = {"UPWARD": "BUY", "DOWNWARD": "SELL"}.get(side)
    permitted = (expectancy.status == "POSITIVE_EXPECTANCY" and risk.status == "RISK_ELIGIBLE"
                 and confidence.sufficient and executable and direction is not None
                 and opportunity.data_quality == "VALID")
    decision = direction if permitted else "HOLD"
    lineage = {"opportunity_evidence_id": str(opportunity.evidence.get("evidence_id", "MISSING")),
               "expectancy_evidence_id": expectancy.evidence_reference,
               "market_policy": f"{opportunity.policy_id}@{opportunity.policy_version}",
               "decision_policy": f"{DECISION_POLICY_ID}@{DECISION_POLICY_VERSION}"}
    reason = explain_decision(decision, expectancy, risk, confidence, executable)
    payload = {"schema_version": DECISION_SCHEMA_VERSION, "decision": decision,
               "direction": decision if decision != "HOLD" else "NONE", "expectancy": expectancy.status,
               "confidence": confidence.value, "risk": risk.status, "reason": reason,
               "supporting": expectancy.supporting_evidence, "conflicting": expectancy.conflicting_evidence,
               "lineage": lineage, "policy": DECISION_POLICY_VERSION}
    return DecisionContext(decision, payload["direction"], expectancy, confidence, risk, reason,
                           expectancy.supporting_evidence, expectancy.conflicting_evidence, lineage,
                           (f"{DECISION_POLICY_ID}@{DECISION_POLICY_VERSION}", "V28_EXPECTANCY_FIRST_ARCHITECTURE"),
                           replay_identity(payload))


def decide_from_market_intelligence(*, structure, regime, trend, momentum, volatility, liquidity, opportunity):
    """Run the complete layer using only the seven Market Intelligence contexts."""
    expectancy = evaluate_expectancy(opportunity, trend, structure, momentum, volatility, liquidity)
    risk = evaluate_risk_eligibility(expectancy, opportunity, structure, regime, trend, momentum,
                                     volatility, liquidity)
    confidence = build_confidence(expectancy, opportunity, structure, regime, trend, momentum,
                                  volatility, liquidity)
    return construct_decision(expectancy, risk, confidence, opportunity)
