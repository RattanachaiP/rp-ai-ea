"""Construct governed decisions exclusively from PR261 contexts and external evidence."""
from .confidence_engine import build_confidence
from .decision_contract import (DECISION_POLICY_ID, DECISION_POLICY_VERSION, DECISION_SCHEMA_VERSION, DecisionContext,
                                decision_replay_identity)
from .decision_explainer import explain_decision
from .expectancy_engine import build_decision_candidate, evaluate_expectancy
from .risk_eligibility import evaluate_risk_precheck


def construct_decision(expectancy, precheck, confidence, candidate):
    permitted = (expectancy.status == "POSITIVE_EXPECTANCY" and precheck.status == "RISK_REVIEW_READY"
                 and confidence.sufficient and candidate.authorized)
    decision = candidate.direction if permitted else "HOLD"
    lineage = {"opportunity_evidence_id": candidate.opportunity_evidence_id,
               "expectancy_evidence_replay_identity": expectancy.evidence_replay_identity,
               "market_policy": candidate.market_policy_version,
               "decision_policy": f"{DECISION_POLICY_ID}@{DECISION_POLICY_VERSION}"}
    reason = explain_decision(decision, expectancy, precheck, confidence, candidate)
    values = dict(decision=decision, direction=decision if decision != "HOLD" else "NONE",
                  expectancy=expectancy, confidence=confidence, risk_precheck=precheck, candidate=candidate,
                  decision_reason=reason, supporting_evidence=expectancy.supporting_evidence,
                  conflicting_evidence=expectancy.conflicting_evidence, decision_lineage=lineage,
                  policy_references=(f"{DECISION_POLICY_ID}@{DECISION_POLICY_VERSION}",
                                     "V28_EXPECTANCY_FIRST_ARCHITECTURE"),
                  policy_version=DECISION_POLICY_VERSION, schema_version=DECISION_SCHEMA_VERSION)
    return DecisionContext(**values, replay_identity=decision_replay_identity(values))


def decide_from_market_intelligence(*, structure, regime, trend, momentum, volatility, liquidity,
                                    opportunity, expectancy_evidence, symbol, timeframe,
                                    execution_model_id, cost_model_id, as_of):
    """Run the real authority flow without changing the advisory OpportunityContext."""
    candidate = build_decision_candidate(opportunity, regime, expectancy_evidence, symbol=symbol,
        timeframe=timeframe, execution_model_id=execution_model_id, cost_model_id=cost_model_id)
    expectancy = evaluate_expectancy(candidate, expectancy_evidence, as_of=as_of)
    precheck = evaluate_risk_precheck(expectancy, candidate, opportunity, structure, regime, trend,
                                     momentum, volatility, liquidity)
    confidence = build_confidence(expectancy, expectancy_evidence)
    return construct_decision(expectancy, precheck, confidence, candidate)
