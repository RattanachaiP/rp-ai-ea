"""PR263 dimensional correctness, lineage, fail-closed and replay tests."""
from dataclasses import FrozenInstanceError,replace
import math
import pytest
from bridge.v28.account_risk_context import AccountRiskPolicy,assess_account_risk,create_account_state
from bridge.v28.broker_constraint_adapter import create_broker_constraints,create_symbol_specification
from bridge.v28.decision_contract import create_expectancy_evidence
from bridge.v28.decision_engine import decide_from_market_intelligence
from bridge.v28.execution_plan import ExecutableQuote,ExecutionConstraints
from bridge.v28.executor_contract import build_executor_contract
from bridge.v28.market_snapshot import build_market_intelligence
from bridge.v28.portfolio_exposure import PortfolioExposure,PortfolioPolicy
from bridge.v28.position_budget import construct_position_budget
from bridge.v28.risk_construction import construct_execution_plan
from bridge.v28.runtime_context import construct_runtime_context
from bridge.v28.demo_runtime_controller import DemoRuntimeController
from bridge.v28.execution_bridge import ExecutionBridge
from bridge.v28.execution_plan_publisher import ExecutionPlanPublisher,publication_for
from bridge.v28.execution_replay_validator import validate_execution_replay
from bridge.v28.executor_adapter import adapt_executor_contract
from bridge.v28.publisher_contract import BrokerSnapshot,RuntimeHealthSnapshot
from bridge.v28.shadow_executor import ShadowExecutor

NOW="1970-01-01T00:01:41Z"; STATE_TIME="1970-01-01T00:01:40Z"
def decision_runtime(side="BUY"):
    up=side=="BUY"; closes=[101,103,105,107,109,111] if up else [111,109,107,105,103,101]
    bars=[{"timestamp":60*(i+1),"open":c-1 if up else c+1,"high":c+2,"low":c-2,"close":c,"closed":True,"source_sequence_id":11} for i,c in enumerate(closes)]
    market={"symbol":"XAUUSD","timeframe":"M1","sequence_id":11,"heartbeat_unix":100,"bid":109.9,"ask":110.1,"mid":110,"bars":bars}
    intel=build_market_intelligence(market); context="UPWARD" if up else "DOWNWARD"
    evidence=create_expectancy_evidence(source_authority="GOVERNED_HISTORICAL_EXPECTANCY",symbol="XAUUSD",timeframe="M1",opportunity_archetype=intel["opportunity"].evidence["archetype"],market_side_context=context,authorized_direction=side,regime_scope=intel["regime"].state,market_policy_version="1.0.0",execution_model_id="EXEC-1",cost_model_id="COST-1",sample_size=200,sample_period_start="2025-01-01",sample_period_end="2025-06-30",win_probability=.6,average_win_r=2,average_loss_r=1,expected_cost_r=.1,net_expectancy_r=.7,statistical_method="BOOTSTRAP_LOWER_CONFIDENCE_BOUND",confidence_measure=.9,lower_confidence_bound_r=.2,return_variance=.8,maximum_drawdown_r=8,evidence_quality="VALID",recency_status="CURRENT",expires_on="2026-12-31",costs_included=True,slippage_included=True,duplicates_excluded=True,out_of_sample=True,sample_scope_consistent=True)
    decision=decide_from_market_intelligence(**intel,expectancy_evidence=evidence,symbol="XAUUSD",timeframe="M1",execution_model_id="EXEC-1",cost_model_id="COST-1",as_of="2026-07-28")
    return decision,construct_runtime_context(market,now=101)

def inputs(side="BUY"):
    decision,runtime=decision_runtime(side); buy=side=="BUY"
    quote=ExecutableQuote("XAUUSD",109.9,110.1,STATE_TIME,11,"GOVERNED_QUOTE",5,.1)
    constraints=ExecutionConstraints(quote,108 if buy else 112,114 if buy else 106,.8,None,1.3,5,3,2,"EXEC-1","COST-1",NOW,5,5,11,True)
    spec_values=dict(symbol="XAUUSD",digits=1,point_size=.1,tick_size=.1,tick_value_per_volume=10,contract_size=1000,minimum_volume=.1,maximum_volume=100,volume_step=.1,stop_level_points=5,freeze_level_points=1,margin_required_per_volume=1000,profit_currency="USD",margin_currency="USD",account_currency="USD",account_currency_conversion_identity="USDUSD@1",account_currency_conversion_rate=1,as_of=STATE_TIME)
    return dict(decision=decision,runtime=runtime,account=create_account_state(equity_account_currency=100000,free_margin_account_currency=50000,open_exposure_account_currency=0,daily_realized_loss_amount=0,current_drawdown_amount=0,trading_enabled=True,account_currency="USD",as_of=STATE_TIME,source="ACCOUNT_FEED"),execution_constraints=constraints,broker_constraints=create_broker_constraints(symbol="XAUUSD",trading_session_open=True,symbol_available=True,as_of=STATE_TIME,evaluation_time=NOW,source="BROKER"),symbol_specification=create_symbol_specification(**spec_values),account_policy=AccountRiskPolicy(1_000_000,2000,10000,1000,.01,.5),portfolio_exposure=PortfolioExposure(0,0,0,0,"USD"),portfolio_policy=PortfolioPolicy(1_000_000,1_000_000,1_000_000,1_000_000))

def test_monetary_risk_margin_and_floor_only_approved_volume():
    plan=construct_execution_plan(**inputs())
    # 21 stop ticks * $10 + $20 spread + $10 quote slippage + $5 commission + $3 model slippage + $2 other.
    assert plan.monetary_risk_per_volume==pytest.approx(250)
    assert plan.margin_required_per_volume==1000
    assert plan.approved_volume==4.0 and plan.execution_ready
    assert plan.stop_distance_price==pytest.approx(2.1) and plan.stop_distance_points==pytest.approx(21)

def test_margin_capacity_is_capital_divided_by_margin_per_volume_not_stop_distance():
    v=inputs(); assessment=assess_account_risk(v["account"],v["account_policy"])
    budget=construct_position_budget(v["account"],v["account_policy"],assessment,v["symbol_specification"],
        monetary_risk_per_volume=250,notional_per_volume=110100,
        available_exposure_account_currency=1_000_000)
    assert budget.risk_based_volume==4
    assert budget.margin_based_volume==50
    assert budget.approved_volume==4

@pytest.mark.parametrize(("side","entry"),[("BUY",110.1),("SELL",109.9)])
def test_side_aware_executable_quote_and_tick_normalization(side,entry):
    plan=construct_execution_plan(**inputs(side)); assert plan.executable_entry_price==entry
    assert plan.execution_ready

def test_requested_volume_is_only_a_floor_normalized_cap():
    v=inputs(); v["execution_constraints"]=replace(v["execution_constraints"],optional_requested_volume_cap=.37)
    assert construct_execution_plan(**v).approved_volume==.3

@pytest.mark.parametrize(("mutation","reason"),[("symbol","DECISION_RUNTIME_SYMBOL_MISMATCH"),("sequence","DECISION_RUNTIME_SEQUENCE_MISMATCH"),("account_stale","ACCOUNT_STATE_STALE"),("broker_stale","BROKER_STATE_STALE"),("health","RUNTIME_HEALTH_INVALID")])
def test_lineage_health_and_freshness_fail_closed(mutation,reason):
    v=inputs()
    if mutation=="symbol": object.__setattr__(v["runtime"],"market",{"symbol":"EURUSD","sequence_id":11})
    elif mutation=="sequence": v["execution_constraints"]=replace(v["execution_constraints"],decision_market_sequence_id=12)
    elif mutation=="account_stale":
        values=v["account"].canonical_payload(); values["as_of"]="1970-01-01T00:00:00Z"; v["account"]=create_account_state(**values)
    elif mutation=="broker_stale": v["broker_constraints"]=create_broker_constraints(symbol="XAUUSD",trading_session_open=True,symbol_available=True,as_of="1970-01-01T00:00:00Z",evaluation_time=NOW,source="BROKER")
    else: v["execution_constraints"]=replace(v["execution_constraints"],runtime_health_valid=False)
    plan=construct_execution_plan(**v); assert not plan.execution_ready and reason in plan.validation_reasons
    assert plan.approved_volume==0 and plan.executable_entry_price is None

def test_net_reward_risk_includes_spread_slippage_and_all_costs():
    base=construct_execution_plan(**inputs())
    v=inputs(); v["execution_constraints"]=replace(v["execution_constraints"],minimum_net_reward_risk_ratio=1.5,slippage_account_currency_per_volume=100)
    costly=construct_execution_plan(**v)
    assert base.execution_ready and not costly.execution_ready
    assert "MINIMUM_NET_REWARD_RISK_FAILED" in costly.validation_reasons

def test_missing_input_short_circuits_to_canonical_deferred_shape():
    v=inputs(); v["execution_constraints"]=replace(v["execution_constraints"],protective_stop=None)
    plan=construct_execution_plan(**v)
    assert plan.approval_status=="DEFERRED" and plan.approved_volume==0
    assert plan.executable_entry_price is None and plan.monetary_risk_per_volume is None

def test_unrepresentable_price_is_rejected_not_rounded():
    v=inputs(); v["execution_constraints"]=replace(v["execution_constraints"],protective_stop=108.05)
    plan=construct_execution_plan(**v); assert "PRICE_TICK_ALIGNMENT_INVALID" in plan.validation_reasons

@pytest.mark.parametrize("bad",[math.nan,math.inf,-1,0])
def test_malformed_symbol_specification_and_numeric_contracts_rejected(bad):
    v=inputs(); values=v["symbol_specification"].canonical_payload(); values["tick_size"]=bad
    with pytest.raises(ValueError): create_symbol_specification(**values)

def test_malformed_policies_rejected():
    with pytest.raises(ValueError): AccountRiskPolicy(1,1,1,1,1.1,.5)
    with pytest.raises(ValueError): PortfolioPolicy(1,math.inf,1,1)

def test_malformed_execution_constraints_rejected():
    c=inputs()["execution_constraints"]
    with pytest.raises(ValueError): replace(c,minimum_net_reward_risk_ratio=math.nan)
    with pytest.raises(ValueError): replace(c,maximum_boundary_age_seconds=0)

def test_plan_and_executor_are_replay_safe_immutable_and_tamper_rejected():
    first=construct_execution_plan(**inputs()); second=construct_execution_plan(**inputs())
    assert first==second
    contract=build_executor_contract(first); assert contract==build_executor_contract(second)
    assert contract.execution_plan_replay_identity==first.replay_identity
    with pytest.raises(FrozenInstanceError): contract.approved_volume=2
    with pytest.raises(ValueError,match="REPLAY"): replace(contract,approved_volume=2)
    object.__setattr__(first,"approved_volume",2)
    with pytest.raises(ValueError,match="REPLAY"): build_executor_contract(first)

def test_risk_construction_never_reads_raw_indicators():
    v=inputs(); object.__setattr__(v["runtime"],"market",{"symbol":"XAUUSD","sequence_id":11,"raw_indicator":"poison"})
    assert construct_execution_plan(**v).execution_ready

def integration_boundary(plan=None):
    plan=plan or construct_execution_plan(**inputs()); contract=build_executor_contract(plan)
    health=RuntimeHealthSnapshot(True,plan.runtime_sequence_id,NOW,0)
    broker=BrokerSnapshot(plan.symbol,plan.runtime_sequence_id,STATE_TIME,True)
    return plan,contract,health,broker,publication_for(plan)

def test_pr264_publication_is_exact_immutable_atomic_and_replay_safe(tmp_path):
    plan,contract,health,broker,publication=integration_boundary()
    path=tmp_path/"execution_plan.json"; published=ExecutionPlanPublisher(path).publish(plan)
    assert published==publication and path.exists() and dict(published.payload)==plan.canonical_payload()
    with pytest.raises(TypeError): published.payload["direction"]="SELL"
    assert validate_execution_replay(plan,contract,health,broker,published).valid

def test_pr264_adapter_preserves_v27_executor_interface_without_submission():
    plan,contract,*_=integration_boundary(); snapshot=adapt_executor_contract(contract)
    assert snapshot.accepted and snapshot.payload["volume"]==plan.approved_volume
    assert snapshot.payload["stop_loss"]==plan.protective_stop and snapshot.payload["take_profit"]==plan.target

def test_pr264_shadow_buy_sell_and_hold_never_grant_ordersend():
    for side in ("BUY","SELL"):
        plan=construct_execution_plan(**inputs(side)); record=ShadowExecutor().execute(plan)
        assert record.action==side and record.expected_execution and not record.ordersend_permitted
    invalid=inputs(); invalid["execution_constraints"]=replace(invalid["execution_constraints"],runtime_health_valid=False)
    record=ShadowExecutor().execute(construct_execution_plan(**invalid))
    assert record.action=="HOLD" and not record.expected_execution and not record.ordersend_permitted

def test_pr264_fail_closed_replay_health_staleness_and_approval_gate():
    plan,contract,health,broker,publication=integration_boundary()
    object.__setattr__(contract,"decision_replay_identity","wrong")
    assert not validate_execution_replay(plan,contract,health,broker,publication).valid
    plan,contract,health,broker,publication=integration_boundary()
    assert not validate_execution_replay(plan,contract,replace(health,healthy=False),broker,publication).valid
    assert not validate_execution_replay(plan,contract,replace(health,boundary_age_seconds=6),broker,publication).valid
    class ForbiddenExecutor:
        def execute(self,_snapshot): raise AssertionError("executor must not be invoked")
    result=ExecutionBridge(ForbiddenExecutor()).deliver(plan,contract,health,broker,publication)
    assert not result.delivered and result.reason=="HUMAN_APPROVAL_REQUIRED"

def test_pr264_demo_requires_isolation_and_human_approval_and_has_no_production_mode():
    plan,contract,health,broker,publication=integration_boundary()
    controller=DemoRuntimeController(executor=object())
    assert controller.run("VALIDATION",plan,contract,health,broker,publication).completed
    assert not controller.run("DEMO",plan,contract,health,broker,publication,human_approved=True).completed
    with pytest.raises(ValueError,match="PRODUCTION"):
        controller.run("PRODUCTION",plan,contract,health,broker,publication)
