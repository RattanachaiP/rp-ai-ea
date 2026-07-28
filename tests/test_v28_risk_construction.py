"""PR263 risk construction, fail-closed, replay, and Executor boundary tests."""
from dataclasses import FrozenInstanceError, replace
import pytest

from bridge.v28.account_risk_context import AccountRiskPolicy, AccountState
from bridge.v28.broker_constraint_adapter import BrokerConstraints
from bridge.v28.decision_contract import create_expectancy_evidence
from bridge.v28.decision_engine import decide_from_market_intelligence
from bridge.v28.execution_plan import ExecutionConstraints
from bridge.v28.executor_contract import build_executor_contract
from bridge.v28.market_snapshot import build_market_intelligence
from bridge.v28.portfolio_exposure import PortfolioExposure, PortfolioPolicy
from bridge.v28.risk_construction import construct_execution_plan
from bridge.v28.runtime_context import construct_runtime_context

def authorized_inputs():
    bars=[{"timestamp":60*(i+1), "open":c-1, "high":c+2, "low":c-2, "close":c,
           "closed":True, "source_sequence_id":11} for i,c in enumerate([101,103,105,107,109,111])]
    market={"symbol":"XAUUSD", "timeframe":"M1", "sequence_id":11, "heartbeat_unix":100,
            "bid":109.9, "ask":110.1, "mid":110, "bars":bars}
    intelligence=build_market_intelligence(market)
    evidence=create_expectancy_evidence(source_authority="GOVERNED_HISTORICAL_EXPECTANCY", symbol="XAUUSD",
        timeframe="M1", opportunity_archetype=intelligence["opportunity"].evidence["archetype"],
        market_side_context="UPWARD", authorized_direction="BUY", regime_scope=intelligence["regime"].state,
        market_policy_version="1.0.0", execution_model_id="EXEC-1", cost_model_id="COST-1", sample_size=200,
        sample_period_start="2025-01-01", sample_period_end="2025-06-30", win_probability=.6,
        average_win_r=2, average_loss_r=1, expected_cost_r=.1, net_expectancy_r=.7,
        statistical_method="BOOTSTRAP_LOWER_CONFIDENCE_BOUND", confidence_measure=.9,
        lower_confidence_bound_r=.2, return_variance=.8, maximum_drawdown_r=8, evidence_quality="VALID",
        recency_status="CURRENT", expires_on="2026-12-31", costs_included=True, slippage_included=True,
        duplicates_excluded=True, out_of_sample=True, sample_scope_consistent=True)
    decision=decide_from_market_intelligence(**intelligence, expectancy_evidence=evidence, symbol="XAUUSD",
        timeframe="M1", execution_model_id="EXEC-1", cost_model_id="COST-1", as_of="2026-07-28")
    return decision, construct_runtime_context(market, now=101)

def inputs():
    decision,runtime=authorized_inputs()
    return dict(decision=decision, runtime=runtime,
        account=AccountState(100000,50000,0,0,0,True,"2026-07-28T00:00:00Z"),
        execution_constraints=ExecutionConstraints(110,108,114,1,.8,1.5,5,"EXEC-1"),
        broker_constraints=BrokerConstraints(.1,100,.1,.5,.1,100,True,True,"2026-07-28T00:00:00Z"),
        account_policy=AccountRiskPolicy(10,2000,10000,1000,.01,.5),
        portfolio_exposure=PortfolioExposure(0,0,0,0),
        portfolio_policy=PortfolioPolicy(5,5,5,5))

def test_approved_plan_is_immutable_replay_safe_and_executor_compatible():
    first=construct_execution_plan(**inputs()); second=construct_execution_plan(**inputs())
    assert first == second and first.execution_ready and first.approval_status == "APPROVED"
    assert first.validation_reasons == ("ALL_RISK_CONSTRUCTION_CHECKS_VALID",)
    contract=build_executor_contract(first)
    assert contract.execution_plan_replay_identity == first.replay_identity and contract.execution_ready
    with pytest.raises(FrozenInstanceError): first.volume=2

@pytest.mark.parametrize(("path", "value", "reason"), [
    ("execution_constraints", None, "EXECUTION_REQUIREMENT_MISSING"),
    ("account", False, "ACCOUNT_TRADING_DISABLED"),
    ("broker_constraints", False, "TRADING_SESSION_CLOSED"),
    ("portfolio_exposure", 5, "SYMBOL_CONCENTRATION")])
def test_every_missing_or_failed_requirement_fails_closed(path, value, reason):
    values=inputs()
    if path == "execution_constraints": values[path]=replace(values[path], protective_stop=value)
    elif path == "account": values[path]=replace(values[path], trading_enabled=value)
    elif path == "broker_constraints": values[path]=replace(values[path], trading_session_open=value)
    else: values[path]=replace(values[path], symbol_exposure=value)
    plan=construct_execution_plan(**values)
    assert not plan.execution_ready and reason in plan.validation_reasons
    with pytest.raises(ValueError, match="NOT_READY"): build_executor_contract(plan)

def test_hold_decision_cannot_become_execution_ready():
    values=inputs(); decision=values["decision"]
    object.__setattr__(decision, "decision", "HOLD")
    plan=construct_execution_plan(**values)
    assert not plan.execution_ready and "DECISION_NOT_AUTHORIZED" in plan.validation_reasons

def test_risk_construction_does_not_inspect_raw_market_indicators():
    values=inputs()
    # Replacing opaque raw market content cannot affect the risk result except the allowed sequence identity.
    object.__setattr__(values["runtime"], "market", {"sequence_id":11, "forbidden_raw_indicator":"poison"})
    assert construct_execution_plan(**values).execution_ready
