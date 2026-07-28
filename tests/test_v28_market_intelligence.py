from dataclasses import FrozenInstanceError
import pytest
from bridge.v28.context_contracts import StructureContext
from bridge.v28.intelligence_policy import DEFAULT_POLICY, IntelligencePolicy
from bridge.v28.market_snapshot import build_market_intelligence, build_market_snapshot
from bridge.v28.runtime_context import construct_runtime_context


def bars(kind="up", ranges=None, *, mid=110, sequence=11):
    closes = [101, 103, 105, 107, 109, 111] if kind == "up" else [111, 109, 107, 105, 103, 101] if kind == "down" else [105]*6
    result = []
    for i, close in enumerate(closes):
        width = ranges[i] if ranges else 4
        result.append({"timestamp": 60*(i+1), "open": close-1 if kind != "down" else close+1,
                       "high": close+width/2, "low": close-width/2, "close": close,
                       "closed": True, "source_sequence_id": sequence})
    return result


def market(value=None, mid=106, sequence=11):
    return {"symbol": "XAUUSD", "timeframe": "M1", "sequence_id": sequence, "heartbeat_unix": 100,
            "bid": mid-.1, "ask": mid+.1, "mid": mid, "bars": bars(sequence=sequence) if value is None else value}


@pytest.mark.parametrize(("kind", "expected"), [("up", "ADVANCING"), ("down", "DECLINING"), ("flat", "RANGE")])
def test_structure_semantics(kind, expected):
    assert build_market_intelligence(market(bars(kind)))["structure"].state == expected


@pytest.mark.parametrize(("ranges", "phase"), [([4,4,4,8,8,8], "EXPANSION"), ([8,8,8,4,4,4], "COMPRESSION")])
def test_expansion_and_compression(ranges, phase):
    assert build_market_intelligence(market(bars(ranges=ranges)))["volatility"].evidence["volatility_phase"] == phase


def test_volatility_level_is_separate_and_thresholds_are_inclusive():
    value = build_market_intelligence(market(bars(ranges=[4,4,4,7,7,7])))["volatility"]
    assert value.evidence["volatility_level"] == "HIGH"
    assert value.evidence["volatility_phase"] == "EXPANSION"


@pytest.mark.parametrize(("mutation", "reason"), [
    (lambda x: x.reverse(), "NON_MONOTONIC_ORDER"),
    (lambda x: x[1].update(timestamp=x[0]["timestamp"]), "DUPLICATE_TIMESTAMP"),
    (lambda x: x[2].update(closed=False), "BAR_2_FORMING"),
    (lambda x: x[2].pop("high"), "BAR_2_MISSING_HIGH"),
])
def test_bar_identity_failures_fail_entire_window_closed(mutation, reason):
    value = bars(); mutation(value); snapshot = build_market_snapshot(market(value))
    assert snapshot.data_quality == "FAIL_CLOSED" and reason in snapshot.rejection_reasons and not snapshot.bars


def test_counts_rejections_and_never_silently_classifies_partial_corruption():
    value = bars(); value.append({"bad": 1}); snapshot = build_market_snapshot(market(value))
    assert (snapshot.input_bar_count, snapshot.valid_bar_count, snapshot.rejected_bar_count) == (7, 6, 1)
    assert snapshot.data_quality == "FAIL_CLOSED"
    assert build_market_intelligence(market(value))["structure"].state == "UNDETERMINED"


@pytest.mark.parametrize(("mid", "location"), [(200, "ABOVE_OBSERVED_RANGE"), (1, "BELOW_OBSERVED_RANGE"), (106, "INSIDE_OBSERVED_RANGE")])
def test_price_location_has_non_negative_distances(mid, location):
    evidence = build_market_intelligence(market(mid=mid))["liquidity"].evidence
    assert evidence["price_location"] == location and min(evidence["boundary_distances"].values()) >= 0


def test_equal_extrema_tolerance_boundary_and_zero_bodies_are_valid():
    value = bars("flat"); value[-1]["high"] = value[-2]["high"] + .2
    evidence = build_market_intelligence(market(value))["liquidity"].evidence
    assert "VISIBLE_EQUAL_HIGH" in evidence["observed_facts"]
    assert build_market_intelligence(market(bars("flat")))["momentum"].state == "CONTINUATION"


def test_complete_opportunity_policy_ontology_replay_and_immutability():
    first = build_market_intelligence(market()); second = build_market_intelligence(market())
    opportunity = first["opportunity"]
    assert first == second
    assert set(opportunity.evidence) == {"presence", "archetype", "market_side_context", "supporting_evidence",
        "conflicting_evidence", "evidence_quality", "invalidation_conditions", "executable", "evidence_id"}
    assert opportunity.policy_id == DEFAULT_POLICY.policy_id and opportunity.evidence["executable"] is False
    with pytest.raises(FrozenInstanceError): opportunity.state = "ABSENT"
    with pytest.raises(TypeError): opportunity.evidence["presence"] = False
    with pytest.raises(ValueError):
        StructureContext("INVENTED", {"x": 1}, "bad", "VALID", DEFAULT_POLICY.policy_id, DEFAULT_POLICY.version)
    with pytest.raises(ValueError): IntelligencePolicy(structure_prior_window=4, structure_recent_window=3)


def test_runtime_context_and_regime_contract_are_complete():
    context = construct_runtime_context(market(), now=101)
    assert context.regime.state in {"TREND", "EXPANSION"}
    assert context.structure.evidence["cohorts_overlap"] is False
    assert context.opportunity.schema_version == "V28.MARKET_CONTEXT.1.0"
