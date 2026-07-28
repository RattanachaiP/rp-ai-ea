"""Fail-closed dimensional Risk Construction over approved boundary contracts only."""
from datetime import datetime, timezone
from decimal import Decimal
from .account_risk_context import assess_account_risk
from .broker_constraint_adapter import floor_volume,tick_aligned,validate_broker_constraints
from .decision_contract import decision_replay_identity
from .execution_plan import ExecutionPlan,POLICY_ID,POLICY_VERSION,SCHEMA_VERSION,identity,parse_utc
from .portfolio_exposure import assess_portfolio,exposure_capacity
from .position_budget import construct_position_budget
from .reward_risk_validator import calculate_reward_risk
from .stop_feasibility import validate_stop
from .takeprofit_feasibility import validate_take_profit

def _age_seconds(evaluation,value): return (parse_utc(evaluation)-parse_utc(value)).total_seconds()

def _nonready(decision,runtime,constraints,reasons,status="REJECTED"):
    direction=decision.direction if decision.decision in {"BUY","SELL"} else "NONE"
    values=dict(decision_replay_identity=decision.replay_identity,runtime_sequence_id=int(runtime.market.get("sequence_id",-1)),
        symbol=decision.candidate.symbol,direction=direction,executable_entry_price=None,approved_volume=0,
        volume_step=None,tick_size=None,
        protective_stop=None,target=None,stop_distance_price=None,stop_distance_points=None,
        monetary_risk_per_volume=None,margin_required_per_volume=None,
        execution_model_id=constraints.execution_model_id,cost_model_id=constraints.cost_model_id,
        evaluation_time=constraints.evaluation_time,approval_status=status,execution_ready=False,
        validation_reasons=tuple(dict.fromkeys(reasons)),policy_references=(f"{POLICY_ID}@{POLICY_VERSION}",),
        policy_version=POLICY_VERSION,schema_version=SCHEMA_VERSION)
    return ExecutionPlan(**values,replay_identity=identity("V28_EXECUTION_PLAN_REPLAY",values))

def construct_execution_plan(*,decision,runtime,account,execution_constraints,broker_constraints,
                             symbol_specification,account_policy,portfolio_exposure,portfolio_policy):
    c=execution_constraints; reasons=[]
    if decision.replay_identity!=decision_replay_identity(decision.canonical_payload()): reasons.append("DECISION_REPLAY_IDENTITY_INVALID")
    if account.replay_identity!=identity("V28_ACCOUNT_STATE_REPLAY",account.canonical_payload()): reasons.append("ACCOUNT_REPLAY_IDENTITY_INVALID")
    if broker_constraints.replay_identity!=identity("V28_BROKER_CONSTRAINT_REPLAY",broker_constraints.canonical_payload()): reasons.append("BROKER_REPLAY_IDENTITY_INVALID")
    if symbol_specification.replay_identity!=identity("V28_SYMBOL_SPEC_REPLAY",symbol_specification.canonical_payload()): reasons.append("SYMBOL_SPEC_REPLAY_IDENTITY_INVALID")
    if decision.decision not in {"BUY","SELL"}: reasons.append("DECISION_NOT_AUTHORIZED")
    runtime_symbol=runtime.market.get("symbol"); runtime_sequence=runtime.market.get("sequence_id")
    if decision.candidate.symbol!=runtime_symbol: reasons.append("DECISION_RUNTIME_SYMBOL_MISMATCH")
    if decision.candidate.symbol!=symbol_specification.symbol or broker_constraints.symbol!=decision.candidate.symbol: reasons.append("BOUNDARY_SYMBOL_MISMATCH")
    if runtime_sequence!=c.decision_market_sequence_id: reasons.append("DECISION_RUNTIME_SEQUENCE_MISMATCH")
    if not c.runtime_health_valid: reasons.append("RUNTIME_HEALTH_INVALID")
    if runtime.heartbeat_age_seconds>c.maximum_runtime_age_seconds: reasons.append("RUNTIME_CONTEXT_STALE")
    evaluation_epoch=parse_utc(c.evaluation_time).timestamp()
    if runtime.observed_at>evaluation_epoch or evaluation_epoch-runtime.observed_at>c.maximum_runtime_age_seconds: reasons.append("RUNTIME_EVALUATION_TIME_MISMATCH")
    if c.execution_model_id!=decision.candidate.execution_model_id: reasons.append("EXECUTION_MODEL_MISMATCH")
    if c.cost_model_id!=decision.candidate.cost_model_id: reasons.append("COST_MODEL_MISMATCH")
    if account.account_currency!=symbol_specification.account_currency or portfolio_exposure.account_currency!=account.account_currency: reasons.append("ACCOUNT_CURRENCY_MISMATCH")
    if broker_constraints.evaluation_time!=c.evaluation_time: reasons.append("EVALUATION_TIME_MISMATCH")
    for timestamp,code in ((account.as_of,"ACCOUNT_STATE_STALE"),(broker_constraints.as_of,"BROKER_STATE_STALE"),(symbol_specification.as_of,"SYMBOL_SPECIFICATION_STALE")):
        age=_age_seconds(c.evaluation_time,timestamp)
        if age<0 or age>c.maximum_boundary_age_seconds: reasons.append(code)
    required=(c.quote,c.protective_stop,c.target,c.volatility_distance_price)
    if any(v is None for v in required): return _nonready(decision,runtime,c,reasons+["EXECUTION_REQUIREMENT_MISSING"],"DEFERRED")
    quote=c.quote
    if quote.symbol!=decision.candidate.symbol or quote.sequence_id!=runtime_sequence: reasons.append("QUOTE_LINEAGE_MISMATCH")
    quote_age=_age_seconds(c.evaluation_time,quote.timestamp)
    if quote_age<0 or quote_age>min(quote.maximum_age_seconds,c.maximum_boundary_age_seconds): reasons.append("QUOTE_STALE")
    entry=quote.ask if decision.direction=="BUY" else quote.bid
    if not all(tick_aligned(v,symbol_specification) for v in (entry,c.protective_stop,c.target)): reasons.append("PRICE_TICK_ALIGNMENT_INVALID")
    if reasons: return _nonready(decision,runtime,c,reasons)
    d=lambda v: Decimal(str(v))
    stop_distance=float(d(entry)-d(c.protective_stop) if decision.direction=="BUY" else d(c.protective_stop)-d(entry))
    target_distance=float(d(c.target)-d(entry) if decision.direction=="BUY" else d(entry)-d(c.target))
    stop_points=float(d(stop_distance)/d(symbol_specification.point_size)); target_points=float(d(target_distance)/d(symbol_specification.point_size))
    stop=validate_stop(entry_price=entry,stop=c.protective_stop,direction=decision.direction,minimum_distance=symbol_specification.stop_level_points*symbol_specification.point_size,volatility_distance=c.volatility_distance_price)
    target=validate_take_profit(entry_price=entry,target=c.target,direction=decision.direction,minimum_distance=symbol_specification.stop_level_points*symbol_specification.point_size)
    rr=calculate_reward_risk(entry=entry,stop=c.protective_stop,target=c.target,spec=symbol_specification,quote=quote,constraints=c)
    for check in (stop,target,rr):
        state=getattr(check,"status",getattr(check,"execution_viability",None))
        if state!="VALID": reasons.extend(check.reasons)
    account_check=assess_account_risk(account,account_policy)
    if account_check.status!="VALID": reasons.extend(account_check.reasons)
    notional_per_volume=entry*symbol_specification.contract_size*symbol_specification.account_currency_conversion_rate
    available=min(account_check.available_exposure_account_currency,max(0,exposure_capacity(portfolio_exposure,portfolio_policy)))
    budget=construct_position_budget(account,account_policy,account_check,symbol_specification,
        monetary_risk_per_volume=rr.net_expected_risk_per_volume,notional_per_volume=notional_per_volume,
        available_exposure_account_currency=available,requested_cap=c.optional_requested_volume_cap)
    if budget.status!="VALID": reasons.append("POSITION_BUDGET_UNAVAILABLE")
    proposed=budget.approved_volume*notional_per_volume
    portfolio_status,portfolio_reasons=assess_portfolio(portfolio_exposure,portfolio_policy,proposed)
    if portfolio_status!="VALID": reasons.extend(portfolio_reasons)
    broker_status,broker_reasons=validate_broker_constraints(broker_constraints,symbol_specification,volume=budget.approved_volume,stop_distance_points=stop_points,target_distance_points=target_points,free_margin=account.free_margin_account_currency)
    if broker_status!="VALID": reasons.extend(broker_reasons)
    if reasons: return _nonready(decision,runtime,c,reasons)
    values=dict(decision_replay_identity=decision.replay_identity,runtime_sequence_id=runtime_sequence,symbol=decision.candidate.symbol,
        direction=decision.direction,executable_entry_price=entry,approved_volume=budget.approved_volume,
        volume_step=symbol_specification.volume_step,tick_size=symbol_specification.tick_size,
        protective_stop=c.protective_stop,target=c.target,stop_distance_price=stop_distance,stop_distance_points=stop_points,
        monetary_risk_per_volume=rr.net_expected_risk_per_volume,margin_required_per_volume=symbol_specification.margin_required_per_volume,
        execution_model_id=c.execution_model_id,cost_model_id=c.cost_model_id,evaluation_time=c.evaluation_time,
        approval_status="APPROVED",execution_ready=True,validation_reasons=("ALL_RISK_CONSTRUCTION_CHECKS_VALID",),
        policy_references=(f"{POLICY_ID}@{POLICY_VERSION}",decision.policy_references[0]),policy_version=POLICY_VERSION,schema_version=SCHEMA_VERSION)
    return ExecutionPlan(**values,replay_identity=identity("V28_EXECUTION_PLAN_REPLAY",values))
