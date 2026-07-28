"""PR263 dimensional correctness, lineage, fail-closed and replay tests."""
from dataclasses import FrozenInstanceError,replace
import math
import json
import pytest
from bridge.v28.account_risk_context import AccountRiskPolicy,assess_account_risk,create_account_state
from bridge.v28.broker_constraint_adapter import create_broker_constraints,create_symbol_specification
from bridge.v28.decision_contract import create_expectancy_evidence
from bridge.v28.decision_engine import decide_from_market_intelligence
from bridge.v28.execution_plan import ExecutableQuote,ExecutionConstraints,identity
from bridge.v28.executor_contract import build_executor_contract
from bridge.v28.market_snapshot import build_market_intelligence
from bridge.v28.portfolio_exposure import PortfolioExposure,PortfolioPolicy
from bridge.v28.position_budget import construct_position_budget
from bridge.v28.risk_construction import construct_execution_plan
from bridge.v28.runtime_context import construct_runtime_context
from bridge.v28.demo_runtime_controller import DemoRuntimeController
from bridge.v28.execution_bridge import DeliveryReceipt,DemoExecutor,ExecutionBridge
from bridge.v28.execution_plan_publisher import ExecutionPlanPublisher,publication_for
from bridge.v28.execution_replay_validator import validate_execution_replay
from bridge.v28.executor_adapter import adapt_executor_contract,build_v27_compatibility_contract
from bridge.v28.publisher_contract import (BrokerSnapshot,ExecutionEnvironmentContract,HumanApprovalRecord,
    PR264_POLICY,RuntimeHealthSnapshot,replay_bound)
from bridge.v28.shadow_executor import ShadowExecutionRecord,ShadowExecutor
from runtime.broker_safety import BrokerOrderResult,BrokerOutcome,BrokerSymbol

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

EVAL="1970-01-01T00:01:43Z"; EXPIRES="1970-01-01T00:01:50Z"
def integration_boundary(plan=None):
    plan=plan or construct_execution_plan(**inputs()); contract=build_executor_contract(plan)
    environment_values=dict(environment="DEMO",account_identifier="demo-1",account_type="DEMO",broker_server="demo-server",
        terminal_instance_identity="terminal-1",executor_instance_identity="demo-executor-1",verified_source_authority="DEMO_TERMINAL_REGISTRY",
        verification_timestamp="1970-01-01T00:01:42Z",expires_at=EXPIRES,policy_reference=PR264_POLICY)
    environment=replay_bound(ExecutionEnvironmentContract,"V28_EXECUTION_ENVIRONMENT_REPLAY",**environment_values)
    health_values=dict(healthy=True,runtime_sequence_id=plan.runtime_sequence_id,source_authority="RUNTIME_HEALTH_AUTHORITY",
        observed_at="1970-01-01T00:01:42Z",evaluation_time=EVAL,expires_at=EXPIRES,maximum_age_seconds=5,policy_reference=PR264_POLICY)
    health=replay_bound(RuntimeHealthSnapshot,"V28_RUNTIME_HEALTH_SNAPSHOT_REPLAY",**health_values)
    broker_values=dict(account_environment="DEMO",account_identifier="demo-1",broker_server="demo-server",terminal_instance_identity="terminal-1",
        symbol=plan.symbol,runtime_sequence_id=plan.runtime_sequence_id,trading_enabled=True,session_state="OPEN",symbol_trade_mode="ENABLED",
        connection_state="CONNECTED",source_authority="DEMO_BROKER_AUTHORITY",observed_at="1970-01-01T00:01:42Z",
        evaluation_time=EVAL,expires_at=EXPIRES,maximum_age_seconds=5,policy_reference=PR264_POLICY)
    broker=replay_bound(BrokerSnapshot,"V28_BROKER_SNAPSHOT_REPLAY",**broker_values)
    publication=publication_for(plan,publisher_authority="EXECUTION_PLAN_PUBLISHER",publisher_instance_identity="publisher-1",
        publication_timestamp="1970-01-01T00:01:42Z",destination_identity="demo-file-1",generation=1,policy_reference=PR264_POLICY)
    approval_values=dict(approval_id="approval-1",approver_identity="operator-1",approval_authority="DEMO_EXECUTION_APPROVER",
        execution_plan_replay_identity=plan.replay_identity,executor_contract_replay_identity=contract.replay_identity,
        approved_environment_identity=environment.replay_identity,approval_timestamp="1970-01-01T00:01:42Z",expires_at=EXPIRES,
        policy_reference=PR264_POLICY,nonce="one-time-purpose-1")
    approval=replay_bound(HumanApprovalRecord,"V28_HUMAN_APPROVAL_REPLAY",**approval_values)
    compatibility=build_v27_compatibility_contract(contract,compatibility_policy_reference=PR264_POLICY)
    return plan,contract,compatibility,health,broker,publication,environment,approval

def test_pr264_publication_is_exact_immutable_atomic_and_replay_safe(tmp_path):
    plan,contract,compatibility,health,broker,publication,environment,approval=integration_boundary()
    path=tmp_path/"execution_plan.json"
    publisher=ExecutionPlanPublisher(path,publisher_authority="EXECUTION_PLAN_PUBLISHER",publisher_instance_identity="publisher-1",destination_identity="demo-file-1",policy_reference=PR264_POLICY)
    published=publisher.publish(plan,publication_timestamp="1970-01-01T00:01:42Z",generation=1)
    assert published==publication and path.exists() and published.plan_payload()["direction"]==plan.direction
    tampered=json.loads(published.canonical_plan_json); tampered["policy_references"].append("POISON")
    with pytest.raises(ValueError,match="HASH"): replace(published,canonical_plan_json=json.dumps(tampered,sort_keys=True,separators=(",",":")))
    assert validate_execution_replay(plan,contract,health,broker,published,environment,approval,evaluation_time=EVAL).valid

def test_pr264_adapter_projects_governed_authority_and_meets_real_v27_requirements():
    plan,contract,compatibility,*_=integration_boundary(); adapted=adapt_executor_contract(compatibility)
    assert adapted.valid and adapted.snapshot.payload["volume"]==plan.approved_volume
    assert adapted.snapshot.payload["entry_permission"] is compatibility.entry_permission
    assert adapted.snapshot.payload["construction_action"]==compatibility.construction_action
    object.__setattr__(compatibility,"entry_permission",False)
    assert not adapt_executor_contract(compatibility).valid

def test_pr264_shadow_buy_sell_and_hold_never_grant_ordersend():
    for side in ("BUY","SELL"):
        plan,*_,publication,environment,approval=integration_boundary(construct_execution_plan(**inputs(side)))
        record=ShadowExecutor().execute(plan,publication,recorded_at=EVAL)
        assert record.action==side and not record.ordersend_permitted
    invalid=inputs(); invalid["execution_constraints"]=replace(invalid["execution_constraints"],runtime_health_valid=False)
    plan=construct_execution_plan(**invalid); record=ShadowExecutor().execute(plan,None,recorded_at=EVAL)
    assert record.action=="HOLD" and not record.ordersend_permitted
    with pytest.raises(ValueError,match="REPLAY"): replace(record,action="BUY")

def test_pr264_fail_closed_replay_health_staleness_and_approval_gate():
    plan,contract,compatibility,health,broker,publication,environment,approval=integration_boundary()
    object.__setattr__(contract,"decision_replay_identity","wrong")
    assert not validate_execution_replay(plan,contract,health,broker,publication,environment,approval,evaluation_time=EVAL).valid
    plan,contract,compatibility,health,broker,publication,environment,approval=integration_boundary()
    assert not validate_execution_replay(plan,contract,health,broker,None,environment,approval,evaluation_time=EVAL,require_delivery_authority=True).valid
    stale_values=approval.canonical_payload(); stale_values["expires_at"]="1970-01-01T00:01:42Z"
    stale=replay_bound(HumanApprovalRecord,"V28_HUMAN_APPROVAL_REPLAY",**stale_values)
    assert not validate_execution_replay(plan,contract,health,broker,publication,environment,stale,evaluation_time=EVAL,require_delivery_authority=True).valid

class DemoBroker:
    def __init__(self): self.requests=[]
    def symbol_info(self,_): return BrokerSymbol(True,True,.1,100,.1)
    def free_margin(self): return 100000
    def required_margin(self,_): return 10
    def send_order(self,request): self.requests.append(request); return BrokerOrderResult(BrokerOutcome.ACCEPTED,"DONE",ticket="demo-1")

def test_pr264_demo_capability_receipt_and_no_boolean_or_production_bypass():
    plan,contract,compatibility,health,broker,publication,environment,approval=integration_boundary(); demo_broker=DemoBroker()
    with pytest.raises(TypeError): DemoRuntimeController(object())
    demo=DemoExecutor(environment,demo_broker,id_factory=lambda:"exec-demo")
    controller=DemoRuntimeController(demo)
    result=controller.run("DEMO",plan,contract,compatibility,health,broker,publication,environment,approval,evaluation_time=EVAL)
    assert result.completed and result.result.status=="DELIVERED" and len(demo_broker.requests)==1
    with pytest.raises(ValueError,match="MODE"): controller.run("PRODUCTION",plan,contract,compatibility,health,broker,publication,environment,approval,evaluation_time=EVAL)
    with pytest.raises(TypeError): ExecutionBridge(object())
    with pytest.raises(ValueError,match="REPLAY"): replace(result.result,reason="tampered")

def test_pr264_mismatched_projected_field_and_stale_environment_block_before_executor():
    plan,contract,compatibility,health,broker,publication,environment,approval=integration_boundary(); object.__setattr__(contract,"target",999)
    validation=validate_execution_replay(plan,contract,health,broker,publication,environment,approval,evaluation_time=EVAL,require_delivery_authority=True)
    assert not validation.valid and "EXECUTOR_PLAN_TARGET_MISMATCH" in validation.reasons
    plan,contract,compatibility,health,broker,publication,environment,approval=integration_boundary()
    stale_values=environment.canonical_payload(); stale_values["expires_at"]="1970-01-01T00:01:42Z"
    stale=replay_bound(ExecutionEnvironmentContract,"V28_EXECUTION_ENVIRONMENT_REPLAY",**stale_values)
    assert not validate_execution_replay(plan,contract,health,broker,publication,stale,approval,evaluation_time=EVAL,require_delivery_authority=True).valid

def test_pr264_invalid_adapter_and_missing_publication_never_reach_v27_executor():
    plan,contract,compatibility,health,broker,publication,environment,approval=integration_boundary(); demo_broker=DemoBroker()
    demo=DemoExecutor(environment,demo_broker,id_factory=lambda:"exec-demo"); bridge=ExecutionBridge(demo)
    object.__setattr__(compatibility,"replay_identity","tampered")
    receipt=bridge.deliver(plan,contract,compatibility,health,broker,publication,environment,approval,delivered_at=EVAL)
    assert receipt.status=="REJECTED" and receipt.reason=="V27_COMPATIBILITY_REPLAY_INVALID" and not demo_broker.requests
    plan,contract,compatibility,health,broker,publication,environment,approval=integration_boundary()
    receipt=bridge.deliver(plan,contract,compatibility,health,broker,None,environment,approval,delivered_at=EVAL)
    assert receipt.status=="REJECTED" and receipt.reason=="PUBLICATION_REQUIRED" and not demo_broker.requests
