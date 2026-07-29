"""PR268 outcome collection, identity, lifecycle, registry, and replay tests."""
from dataclasses import replace

import pytest

from bridge.v28.outcome_contract import (create_entry_evidence, create_evidence_snapshot,
                                         create_exit_evidence, create_outcome_record,
                                         create_trade_lifecycle, create_trade_result)
from bridge.v28.outcome_evidence import publish_outcome_evidence, replay_validate
from bridge.v28.outcome_registry import create_outcome_registry


def outcome(trade_identity="trade-42"):
    entry = create_entry_evidence(order_identity="order-42", observed_at="2026-07-29T10:00:00Z",
                                  requested_price=3300.0, filled_price=3300.2, spread=.2, slippage=.2)
    exit_evidence = create_exit_evidence(deal_identity="deal-42", observed_at="2026-07-29T10:30:00Z",
                                         requested_price=3310.0, filled_price=3309.8,
                                         exit_reason="TAKE_PROFIT", slippage=.2)
    lifecycle = create_trade_lifecycle(trade_identity=trade_identity, entry=entry, exit=exit_evidence)
    result = create_trade_result(gross_profit=96.0, commission=-4.0, swap=-2.0, initial_risk=45.0,
                                 entry_time=entry.observed_at, exit_time=exit_evidence.observed_at)
    snapshot = lambda identity, **payload: create_evidence_snapshot(source_identity=identity,
                                                                     captured_payload=payload)
    return create_outcome_record(
        trade_identity=trade_identity, symbol="XAUUSD", direction="BUY",
        entry_time=entry.observed_at, exit_time=exit_evidence.observed_at,
        entry_price=entry.filled_price, exit_price=exit_evidence.filled_price,
        stop_loss=3295.0, take_profit=3310.0, position_size=.1,
        spread=entry.spread, slippage=entry.slippage + exit_evidence.slippage,
        lifecycle=lifecycle, result=result,
        runtime_snapshot=snapshot("runtime-7", sequence_id=7),
        market_regime_snapshot=snapshot("regime-7", state="TREND"),
        opportunity_snapshot=snapshot("opportunity-7", archetype="PULLBACK"),
        decision_snapshot=snapshot("decision-7", action="BUY"),
        risk_snapshot=snapshot("risk-7", initial_risk=45.0),
        execution_snapshot=snapshot("plan-7", approved_volume=.1), confidence=.8,
        execution_plan_identity="plan-7", qualification_identity="qualification-3",
        readiness_identity="readiness-2")


def test_completed_trade_produces_complete_immutable_deterministic_record():
    first = outcome()
    second = outcome()
    assert first == second and first.outcome_identity == second.outcome_identity
    assert first.result.net_profit == 90.0
    assert first.result.r_multiple == 2.0
    assert first.result.holding_time_seconds == 1800
    assert first.lifecycle.exit.exit_reason == "TAKE_PROFIT"
    with pytest.raises(Exception):
        first.symbol = "EURUSD"
    with pytest.raises(TypeError):
        first.runtime_snapshot.captured_payload["sequence_id"] = 8


def test_registry_is_append_only_identity_bound_and_replay_safe():
    empty = create_outcome_registry()
    first = empty.append(outcome())
    assert not empty.entries and len(first.entries) == 1
    assert first.entries[0].outcome.outcome_identity == outcome().outcome_identity
    with pytest.raises(ValueError, match="REPLAY_DUPLICATE"):
        first.append(outcome())
    values = outcome().canonical_payload()
    values["readiness_identity"] = "readiness-3"
    with pytest.raises(ValueError, match="TRADE_DUPLICATE"):
        first.append(create_outcome_record(**values))


def test_registry_entry_and_snapshot_tampering_fail_closed():
    record = outcome()
    object.__setattr__(record.runtime_snapshot, "source_identity", "forged")
    with pytest.raises(ValueError, match="SNAPSHOT_IDENTITY"):
        create_outcome_registry().append(record)
    registry = create_outcome_registry().append(outcome())
    object.__setattr__(registry.entries[0], "previous_entry_identity", "forged")
    with pytest.raises(ValueError, match="ENTRY_SEQUENCE"):
        publish_outcome_evidence(registry)


def test_lifecycle_result_and_upstream_lineage_must_be_complete():
    record = outcome()
    with pytest.raises(ValueError, match="LIFECYCLE_FIELDS"):
        create_outcome_record(**(record.canonical_payload() | {"entry_price": 1.0}))
    with pytest.raises(ValueError, match="EXECUTION_LINEAGE"):
        create_outcome_record(**(record.canonical_payload() | {"execution_plan_identity": "other"}))
    with pytest.raises(ValueError, match="NET_INVALID"):
        replace(record.result, net_profit=999.0, result_identity=record.result.result_identity)


def test_evidence_contract_is_only_authoritative_future_learning_input():
    registry = create_outcome_registry().append(outcome())
    evidence = publish_outcome_evidence(registry)
    assert evidence.authoritative_source == "OUTCOME_REGISTRY_ONLY"
    assert evidence.learning_performed is False
    assert evidence.outcome_identities == (outcome().outcome_identity,)
    assert registry.expectancy_dataset == (outcome(),)
    assert replay_validate(registry, evidence)
    object.__setattr__(evidence, "record_count", 2)
    assert not replay_validate(registry, evidence)


def test_invalid_times_exit_reason_and_risk_are_rejected():
    with pytest.raises(ValueError, match="EXIT_EVIDENCE"):
        create_exit_evidence(deal_identity="deal", observed_at="2026-07-29T10:00:00Z",
                             requested_price=1.0, filled_price=1.0, exit_reason="LEARN", slippage=0.0)
    with pytest.raises(ValueError, match="NUMERIC"):
        create_trade_result(gross_profit=1.0, commission=0.0, swap=0.0, initial_risk=0.0,
                            entry_time="2026-07-29T10:00:00Z", exit_time="2026-07-29T10:01:00Z")
