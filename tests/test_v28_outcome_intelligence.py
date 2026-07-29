"""PR268 outcome collection, identity, lifecycle, registry, and replay tests."""
from dataclasses import replace
from functools import lru_cache

import pytest

from bridge.v28.outcome_contract import (create_entry_evidence, create_evidence_snapshot,
                                         create_exit_evidence, create_outcome_record,
                                         create_trade_execution_facts, create_trade_lifecycle,
                                         create_trade_result)
from bridge.v28.outcome_evidence import publish_outcome_evidence, replay_validate
from bridge.v28.outcome_governance import create_outcome_governance_evidence
from bridge.v28.outcome_registry import create_outcome_registry
from bridge.v28.outcome_registry import OutcomeRegistry
from bridge.v28.pipeline_validator import certification_identity
from bridge.v28.production_readiness_report import build_production_readiness_report
from bridge.v28.production_readiness_report import ProductionReadinessReport
from bridge.v28.qualification_report import QualificationReport
from tests.test_v28_production_readiness_governance import evidence as readiness_evidence


@lru_cache
def governed_lineage():
    candidate, readiness_registry = readiness_evidence()
    readiness_report = build_production_readiness_report(candidate, readiness_registry)
    governance = create_outcome_governance_evidence(
        qualification_registry=candidate.qualification_registry,
        qualification_report=candidate.qualification_report,
        readiness_candidate=candidate, readiness_registry=readiness_registry,
        readiness_report=readiness_report)
    return candidate, readiness_report, governance


def outcome(trade_identity="trade-42"):
    candidate, readiness_report, governance = governed_lineage()
    entry = create_entry_evidence(order_identity="order-42", observed_at="2026-07-29T10:00:00Z",
                                  requested_price=3300.0, filled_price=3300.2, spread=.2, slippage=.2)
    exit_evidence = create_exit_evidence(deal_identity="deal-42", observed_at="2026-07-29T10:30:00Z",
                                         requested_price=3310.0, filled_price=3309.8,
                                         exit_reason="TAKE_PROFIT", slippage=.2)
    lifecycle = create_trade_lifecycle(trade_identity=trade_identity, entry=entry, exit=exit_evidence)
    result = create_trade_result(gross_profit=96.0, commission=-4.0, swap=-2.0, initial_risk=45.0,
                                 entry_time=entry.observed_at, exit_time=exit_evidence.observed_at)
    pipeline = "pipeline-7"
    snapshot = lambda role, identity, **payload: create_evidence_snapshot(
        source_identity=identity, evidence_role=role, pipeline_identity=pipeline,
        captured_payload=payload)
    facts = create_trade_execution_facts(
        trade_identity=trade_identity, symbol="XAUUSD", direction="BUY", position_size=.1,
        stop_loss=3295.0, take_profit=3310.0, execution_plan_identity="plan-7")
    return create_outcome_record(
        trade_identity=trade_identity, symbol="XAUUSD", direction="BUY",
        entry_time=entry.observed_at, exit_time=exit_evidence.observed_at,
        entry_price=entry.filled_price, exit_price=exit_evidence.filled_price,
        stop_loss=3295.0, take_profit=3310.0, position_size=.1,
        spread=entry.spread, slippage=entry.slippage + exit_evidence.slippage,
        lifecycle=lifecycle, result=result, execution_facts=facts, pipeline_identity=pipeline,
        runtime_snapshot=snapshot("RUNTIME", "runtime-7", sequence_id=7),
        market_regime_snapshot=snapshot("MARKET_STATE", "market-7", state="TREND"),
        opportunity_snapshot=snapshot("OPPORTUNITY", "opportunity-7", archetype="PULLBACK"),
        decision_snapshot=snapshot("DECISION", "decision-7", action="BUY"),
        risk_snapshot=snapshot("RISK", "risk-7", initial_risk=45.0),
        execution_snapshot=snapshot("EXECUTION", "plan-7", approved_volume=.1), confidence=.8,
        runtime_identity="runtime-7", market_state_identity="market-7",
        opportunity_identity="opportunity-7", decision_identity="decision-7", risk_identity="risk-7",
        execution_plan_identity="plan-7", governance_evidence=governance,
        qualification_identity=candidate.qualification_report.replay_identity,
        readiness_identity=readiness_report.report_identity)


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
    values["confidence"] = .9
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
    with pytest.raises(ValueError, match="EXECUTION_FACTS"):
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


def test_registry_predecessor_is_derived_and_cannot_be_forged_or_reordered():
    first = create_outcome_registry().append(outcome("trade-a"))
    second = first.append(outcome("trade-b"))
    forged_values = second.canonical_payload() | {"previous_registry_identity": "forged"}
    forged_identity = certification_identity("V28_OUTCOME_REGISTRY", forged_values)
    with pytest.raises(ValueError, match="PREDECESSOR"):
        OutcomeRegistry(**forged_values, registry_identity=forged_identity)
    reordered = create_outcome_registry().append(outcome("trade-b")).append(outcome("trade-a"))
    assert second.registry_identity != reordered.registry_identity
    entries = tuple(reversed(second.entries))
    values = {"entries": entries, "previous_registry_identity": second.previous_registry_identity,
              "schema_version": second.schema_version}
    with pytest.raises(ValueError, match="LINEAGE|SEQUENCE|PREDECESSOR"):
        OutcomeRegistry(**values, registry_identity=certification_identity("V28_OUTCOME_REGISTRY", values))


@pytest.mark.parametrize("field,value", [
    ("symbol", "EURUSD"), ("direction", "SELL"), ("position_size", .2),
    ("stop_loss", 3290.0), ("take_profit", 3320.0), ("execution_plan_identity", "other-plan"),
])
def test_duplicate_execution_projections_cannot_diverge(field, value):
    record = outcome()
    with pytest.raises(ValueError, match="EXECUTION_FACTS"):
        create_outcome_record(**(record.canonical_payload() | {field: value}))


def test_mixed_pipeline_and_governance_lineage_fail_closed():
    record = outcome()
    mixed = create_evidence_snapshot(source_identity=record.decision_identity, evidence_role="DECISION",
                                     pipeline_identity="another-pipeline", captured_payload={"action": "BUY"})
    with pytest.raises(ValueError, match="SNAPSHOT_LINEAGE"):
        create_outcome_record(**(record.canonical_payload() | {"decision_snapshot": mixed}))
    with pytest.raises(ValueError, match="GOVERNANCE_PROJECTION"):
        create_outcome_record(**(record.canonical_payload() | {"qualification_identity": "another-candidate"}))
    with pytest.raises(ValueError, match="GOVERNANCE_PROJECTION"):
        create_outcome_record(**(record.canonical_payload() | {"readiness_identity": "another-candidate"}))


def test_governed_artifacts_from_other_candidates_fail_closed():
    candidate, report, governance = governed_lineage()
    qualification_values = governance.qualification_report.canonical_payload() | {"campaign_identity": "other"}
    other_qualification = QualificationReport(
        **qualification_values, replay_identity=certification_identity(
            "V28_OPERATIONAL_QUALIFICATION_REPORT", qualification_values))
    values = governance.canonical_payload() | {"qualification_report": other_qualification}
    with pytest.raises(ValueError, match="GOVERNANCE_LINEAGE"):
        create_outcome_governance_evidence(**values)
    readiness_values = report.canonical_payload() | {"candidate_identity": "other"}
    other_readiness = ProductionReadinessReport(
        **readiness_values, report_identity=certification_identity(
            "V28_PRODUCTION_READINESS_REPORT", readiness_values))
    values = governance.canonical_payload() | {"readiness_report": other_readiness}
    with pytest.raises(ValueError, match="GOVERNANCE_LINEAGE"):
        create_outcome_governance_evidence(**values)


def test_signed_slippage_and_signed_broker_adjustments_are_preserved():
    favorable = create_entry_evidence(order_identity="order", observed_at="2026-07-29T10:00:00Z",
                                      requested_price=10.0, filled_price=9.9, spread=.1, slippage=-.1)
    assert favorable.slippage == -.1
    cases = ((-4.0, -2.0, 94.0), (2.0, -2.0, 100.0), (-4.0, 3.0, 99.0), (2.0, 3.0, 105.0))
    for commission, swap, net in cases:
        result = create_trade_result(gross_profit=100.0, commission=commission, swap=swap,
                                     initial_risk=50.0, entry_time="2026-07-29T10:00:00Z",
                                     exit_time="2026-07-29T10:01:00Z")
        assert result.net_profit == net


@pytest.mark.parametrize("value", [float("nan"), float("inf"), True])
def test_non_finite_and_boolean_numeric_values_fail_closed(value):
    with pytest.raises((TypeError, ValueError)):
        create_trade_result(gross_profit=value, commission=0.0, swap=0.0, initial_risk=1.0,
                            entry_time="2026-07-29T10:00:00Z", exit_time="2026-07-29T10:01:00Z")


def test_nested_snapshot_payload_is_frozen_and_tampering_invalidates_replay():
    source = {"levels": [{"price": 1.0}]}
    snapshot = create_evidence_snapshot(source_identity="runtime", evidence_role="RUNTIME",
                                        pipeline_identity="pipeline", captured_payload=source)
    source["levels"][0]["price"] = 2.0
    assert snapshot.captured_payload["levels"][0]["price"] == 1.0
    with pytest.raises(TypeError):
        snapshot.captured_payload["levels"][0]["price"] = 3.0
    object.__setattr__(snapshot, "captured_payload", {"levels": ({"price": 9.0},)})
    with pytest.raises(ValueError, match="SNAPSHOT_IDENTITY"):
        type(snapshot)(**snapshot.__dict__)
