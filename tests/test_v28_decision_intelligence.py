"""PR262 Decision Intelligence contract, gate, and replay tests."""
from dataclasses import FrozenInstanceError
import pytest

from bridge.v28.context_contracts import OpportunityContext
from bridge.v28.decision_engine import decide_from_market_intelligence
from bridge.v28.intelligence_policy import DEFAULT_POLICY
from bridge.v28.market_snapshot import build_market_intelligence


def bars(kind="up", sequence=11):
    closes = [101, 103, 105, 107, 109, 111] if kind == "up" else [111, 109, 107, 105, 103, 101]
    return [{"timestamp": 60 * (i + 1), "open": close - 1 if kind == "up" else close + 1,
             "high": close + 2, "low": close - 2, "close": close, "closed": True,
             "source_sequence_id": sequence} for i, close in enumerate(closes)]


def market(value, sequence=11):
    return {"symbol": "XAUUSD", "timeframe": "M1", "sequence_id": sequence, "heartbeat_unix": 100,
            "bid": 109.9, "ask": 110.1, "mid": 110, "bars": value}


def intelligence(side="UPWARD", *, executable=True, degraded=False):
    kind = "up" if side == "UPWARD" else "down"
    values = build_market_intelligence(market(bars(kind)))
    original = values["opportunity"]
    evidence = dict(original.evidence)
    evidence.update(executable=executable, market_side_context=side,
                    edge_verification={"win_probability": .6, "average_win_r": 2.0,
                        "average_loss_r": 1.0, "expected_cost_r": .1,
                        "net_expectancy_r": .7, "sample_size": 100,
                        "statistical_confidence": .9, "evidence_id": "HISTORICAL-EDGE-1"})
    values["opportunity"] = OpportunityContext("PRESENT", evidence, "governed executable opportunity",
        "DEGRADED" if degraded else "VALID", DEFAULT_POLICY.policy_id, DEFAULT_POLICY.version)
    return values


def decide(values):
    return decide_from_market_intelligence(**values)


@pytest.mark.parametrize(("side", "expected"), [("UPWARD", "BUY"), ("DOWNWARD", "SELL")])
def test_buy_and_sell_are_created_entirely_from_market_intelligence(side, expected):
    result = decide(intelligence(side))
    assert result.decision == expected and result.direction == expected
    assert result.expectancy.status == "POSITIVE_EXPECTANCY"
    assert result.risk_eligibility.status == "RISK_ELIGIBLE" and result.confidence.sufficient


@pytest.mark.parametrize("mutation", ["missing_edge", "not_executable", "degraded", "invalid_expectancy"])
def test_every_failed_gate_returns_hold(mutation):
    values = intelligence()
    opportunity = values["opportunity"]
    evidence = dict(opportunity.evidence)
    quality = opportunity.data_quality
    if mutation == "missing_edge": evidence.pop("edge_verification")
    if mutation == "not_executable": evidence["executable"] = False
    if mutation == "degraded": quality = "DEGRADED"
    if mutation == "invalid_expectancy":
        evidence["edge_verification"] = dict(evidence["edge_verification"])
        evidence["edge_verification"]["net_expectancy_r"] = -.1
    values["opportunity"] = OpportunityContext("PRESENT", evidence, "test", quality,
                                                DEFAULT_POLICY.policy_id, DEFAULT_POLICY.version)
    result = decide(values)
    assert result.decision == "HOLD" and result.direction == "NONE"


def test_replay_identity_explanation_lineage_and_immutability():
    first, second = decide(intelligence()), decide(intelligence())
    assert first == second and first.replay_identity == second.replay_identity
    assert first.policy_references and first.decision_lineage["expectancy_evidence_id"] == "HISTORICAL-EDGE-1"
    assert "expectancy=POSITIVE_EXPECTANCY" in first.decision_reason
    with pytest.raises(FrozenInstanceError):
        first.decision = "HOLD"
    with pytest.raises(TypeError):
        first.decision_lineage["bad"] = "mutation"


def test_confidence_is_context_agreement_not_indicator_scoring():
    result = decide(intelligence())
    assert set(result.confidence.factors) == {"market_agreement", "evidence_consistency",
        "opportunity_maturity", "context_reliability", "data_quality", "expectancy_quality"}
    assert result.confidence.value == pytest.approx(.983333)
