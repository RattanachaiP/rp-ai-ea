"""Verify governed historical expectancy without modifying Market Intelligence."""
from datetime import date
from .decision_contract import DecisionCandidate, ExpectancyContext, ExpectancyEvidenceRecord

_PROFILE_DIRECTIONS = {
    ("DIRECTIONAL_CONTINUATION", "UPWARD"): "BUY",
    ("DIRECTIONAL_CONTINUATION", "DOWNWARD"): "SELL",
    ("DIRECTIONAL_EXPANSION", "UPWARD"): "BUY",
    ("DIRECTIONAL_EXPANSION", "DOWNWARD"): "SELL",
}


def build_decision_candidate(opportunity, regime, evidence: ExpectancyEvidenceRecord, *, symbol: str,
                             timeframe: str, execution_model_id: str, cost_model_id: str) -> DecisionCandidate:
    """Bind separately governed evidence to an unchanged advisory opportunity."""
    archetype = str(opportunity.evidence.get("archetype", "NONE"))
    side = str(opportunity.evidence.get("market_side_context", "NEUTRAL"))
    direction = _PROFILE_DIRECTIONS.get((archetype, side), "NONE")
    matches = {
        "SYMBOL_MATCH": evidence.symbol == symbol,
        "TIMEFRAME_MATCH": evidence.timeframe == timeframe,
        "ARCHETYPE_MATCH": evidence.opportunity_archetype == archetype,
        "MARKET_SIDE_MATCH": evidence.market_side_context == side,
        "REGIME_MATCH": evidence.regime_scope == regime.state,
        "MARKET_POLICY_MATCH": evidence.market_policy_version == opportunity.policy_version,
        "EXECUTION_MODEL_MATCH": evidence.execution_model_id == execution_model_id,
        "COST_MODEL_MATCH": evidence.cost_model_id == cost_model_id,
        "DIRECTION_PROFILE_MATCH": evidence.authorized_direction == direction,
        "PR261_OPPORTUNITY_ADVISORY": opportunity.evidence.get("executable") is False,
        "OPPORTUNITY_PRESENT": opportunity.state == "PRESENT" and opportunity.data_quality == "VALID",
        "REGIME_VALID": regime.data_quality == "VALID",
    }
    reasons = tuple(name for name, passed in matches.items() if not passed)
    authorized = not reasons
    return DecisionCandidate(symbol, timeframe, str(opportunity.evidence.get("evidence_id", "")), archetype,
                             side, regime.state, opportunity.policy_version, execution_model_id, cost_model_id,
                             direction if authorized else "NONE", evidence.replay_identity, authorized,
                             reasons or ("ALL_SCOPE_BINDINGS_VERIFIED",))


def evaluate_expectancy(candidate: DecisionCandidate, evidence: ExpectancyEvidenceRecord, *, as_of: str):
    start, end, expiry, evaluation_date = map(date.fromisoformat,
        (evidence.sample_period_start, evidence.sample_period_end, evidence.expires_on, as_of))
    calculated = (evidence.win_probability * evidence.average_win_r
                  - (1 - evidence.win_probability) * evidence.average_loss_r - evidence.expected_cost_r)
    governance = {
        "CANDIDATE_AUTHORIZED": candidate.authorized,
        "EVIDENCE_IDENTITY_VERIFIED": evidence.identity_valid(),
        "IDENTITY_BOUND": candidate.evidence_replay_identity == evidence.replay_identity,
        "SOURCE_GOVERNED": evidence.source_authority == "GOVERNED_HISTORICAL_EXPECTANCY",
        "SAMPLE_SUFFICIENT": evidence.sample_size >= 100,
        "MINIMUM_DATE_SPAN": (end - start).days >= 90,
        "COSTS_INCLUDED": evidence.costs_included and evidence.expected_cost_r > 0,
        "SLIPPAGE_INCLUDED": evidence.slippage_included,
        "DUPLICATES_EXCLUDED": evidence.duplicates_excluded,
        "OUT_OF_SAMPLE": evidence.out_of_sample,
        "SCOPE_CONSISTENT": evidence.sample_scope_consistent,
        "RECENT_AND_UNEXPIRED": evidence.recency_status == "CURRENT" and evaluation_date <= expiry,
        "SUPPORTED_METHOD": evidence.statistical_method == "BOOTSTRAP_LOWER_CONFIDENCE_BOUND",
        "QUALITY_VALID": evidence.evidence_quality == "VALID",
        "POINT_ESTIMATE_CONSISTENT": abs(calculated - evidence.net_expectancy_r) <= 1e-9,
        "POSITIVE_POINT_ESTIMATE": evidence.net_expectancy_r > 0,
        "POSITIVE_LOWER_BOUND": evidence.lower_confidence_bound_r > 0,
        "DISPERSION_RECORDED": evidence.return_variance > 0,
        "DRAWDOWN_RECORDED": evidence.maximum_drawdown_r >= 0,
        "CALIBRATED_CONFIDENCE": .75 <= evidence.confidence_measure <= 1,
    }
    rejected = tuple(name for name, passed in governance.items() if not passed)
    positive = not rejected
    supporting = tuple(name for name, passed in governance.items() if passed)
    return ExpectancyContext("POSITIVE_EXPECTANCY" if positive else "EXPECTANCY_NOT_ESTABLISHED",
        evidence.evidence_quality, supporting, rejected,
        "all governed historical evidence requirements passed" if positive else "expectancy governance failed closed",
        evidence.replay_identity, evidence.lower_confidence_bound_r)
