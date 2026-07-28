"""PR262 real authority-flow, governance, invariant, and replay tests."""
from dataclasses import FrozenInstanceError, replace
import pytest
from bridge.v28.decision_contract import (Confidence, DecisionCandidate, DecisionContext,
    DecisionRiskPrecheck, ExpectancyContext, create_expectancy_evidence, decision_replay_identity)
from bridge.v28.decision_engine import decide_from_market_intelligence
from bridge.v28.market_snapshot import build_market_intelligence


def bars(kind="up", sequence=11):
    closes = [101, 103, 105, 107, 109, 111] if kind == "up" else [111, 109, 107, 105, 103, 101]
    return [{"timestamp": 60*(i+1), "open": close-1 if kind == "up" else close+1,
             "high": close+2, "low": close-2, "close": close, "closed": True,
             "source_sequence_id": sequence} for i, close in enumerate(closes)]


def intelligence(side="UPWARD"):
    kind = "up" if side == "UPWARD" else "down"
    market = {"symbol": "XAUUSD", "timeframe": "M1", "sequence_id": 11, "heartbeat_unix": 100,
              "bid": 109.9, "ask": 110.1, "mid": 110, "bars": bars(kind)}
    return build_market_intelligence(market)


def evidence(values, side="UPWARD", **overrides):
    direction = "BUY" if side == "UPWARD" else "SELL"
    fields = dict(source_authority="GOVERNED_HISTORICAL_EXPECTANCY", symbol="XAUUSD", timeframe="M1",
        opportunity_archetype=values["opportunity"].evidence["archetype"], market_side_context=side,
        authorized_direction=direction, regime_scope=values["regime"].state,
        market_policy_version=values["opportunity"].policy_version, execution_model_id="EXEC-1",
        cost_model_id="COST-1", sample_size=200, sample_period_start="2025-01-01",
        sample_period_end="2025-06-30", win_probability=.6, average_win_r=2.0, average_loss_r=1.0,
        expected_cost_r=.1, net_expectancy_r=.7, statistical_method="BOOTSTRAP_LOWER_CONFIDENCE_BOUND",
        confidence_measure=.9, lower_confidence_bound_r=.2, return_variance=.8, maximum_drawdown_r=8.0,
        evidence_quality="VALID", recency_status="CURRENT", expires_on="2026-12-31", costs_included=True,
        slippage_included=True, duplicates_excluded=True, out_of_sample=True, sample_scope_consistent=True)
    fields.update(overrides)
    return create_expectancy_evidence(**fields)


def decide(values, record, **overrides):
    args = dict(values, expectancy_evidence=record, symbol="XAUUSD", timeframe="M1",
                execution_model_id="EXEC-1", cost_model_id="COST-1", as_of="2026-07-28")
    args.update(overrides)
    return decide_from_market_intelligence(**args)


@pytest.mark.parametrize(("side", "expected"), [("UPWARD", "BUY"), ("DOWNWARD", "SELL")])
def test_buy_and_sell_use_advisory_opportunity_plus_separate_evidence(side, expected):
    values = intelligence(side)
    assert values["opportunity"].evidence["executable"] is False
    result = decide(values, evidence(values, side))
    assert result.decision == expected and result.candidate.authorized
    assert result.risk_precheck.status == "RISK_REVIEW_READY"


@pytest.mark.parametrize(("field", "value"), [("symbol", "EURUSD"), ("timeframe", "M5"),
    ("opportunity_archetype", "OTHER"), ("market_side_context", "DOWNWARD"),
    ("regime_scope", "RANGE"), ("market_policy_version", "bad"),
    ("execution_model_id", "bad"), ("cost_model_id", "bad")])
def test_every_scope_mismatch_fails_closed(field, value):
    values = intelligence()
    result = decide(values, evidence(values, **{field: value}))
    assert result.decision == "HOLD" and not result.candidate.authorized


@pytest.mark.parametrize(("field", "value"), [("costs_included", False), ("slippage_included", False),
    ("duplicates_excluded", False), ("out_of_sample", False), ("sample_scope_consistent", False),
    ("sample_size", 99), ("sample_period_start", "2025-06-01"), ("recency_status", "STALE"),
    ("expires_on", "2026-01-01"), ("lower_confidence_bound_r", 0.0), ("return_variance", 0.0),
    ("statistical_method", "UNSUPPORTED")])
def test_methodology_and_quality_requirements_fail_closed(field, value):
    values = intelligence()
    result = decide(values, evidence(values, **{field: value}))
    assert result.decision == "HOLD" and result.expectancy.status == "EXPECTANCY_NOT_ESTABLISHED"


def test_evidence_identity_is_canonical_and_tampering_is_rejected():
    values = intelligence(); record = evidence(values)
    assert record == evidence(values)
    with pytest.raises(ValueError, match="IDENTITY"):
        replace(record, sample_size=999)
    tampered = evidence(values)
    object.__setattr__(tampered, "sample_size", 999)
    assert decide(values, tampered).decision == "HOLD"


def test_confidence_is_categorical_not_averaged_scoring():
    values = intelligence(); result = decide(values, evidence(values))
    assert result.confidence.assessment == "GOVERNED_EVIDENCE_SUFFICIENT"
    assert result.confidence.confidence_measure == .9
    assert not hasattr(result.confidence, "factors")


def test_full_decision_replay_and_immutability():
    values = intelligence(); first = decide(values, evidence(values)); second = decide(values, evidence(values))
    assert first == second and first.replay_identity == second.replay_identity
    assert first.decision_lineage["expectancy_evidence_replay_identity"] == first.expectancy.evidence_replay_identity
    with pytest.raises(FrozenInstanceError): first.decision = "HOLD"
    changed = dict(first.canonical_payload()); changed["decision_reason"] = "changed"
    assert decision_replay_identity(changed) != first.replay_identity


def test_contract_itself_rejects_unauthorized_buy_even_with_valid_hash():
    values = intelligence(); good = decide(values, evidence(values))
    bad_candidate = replace(good.candidate, authorized=False, direction="NONE", authorization_reasons=("NO",))
    payload = dict(good.canonical_payload()); payload.update(candidate=bad_candidate, direction="BUY", decision="BUY")
    with pytest.raises(ValueError, match="AUTHORITY_INVARIANT"):
        DecisionContext(**payload, replay_identity=decision_replay_identity(payload))
