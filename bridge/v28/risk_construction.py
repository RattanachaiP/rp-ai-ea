"""Orchestrate risk-owned checks using only approved boundary contracts."""
from .account_risk_context import assess_account_risk
from .broker_constraint_adapter import validate_broker_constraints
from .decision_contract import decision_replay_identity
from .execution_plan import ExecutionPlan, POLICY_ID, POLICY_VERSION, SCHEMA_VERSION, plan_identity
from .portfolio_exposure import assess_portfolio
from .position_budget import construct_position_budget
from .reward_risk_validator import validate_reward_risk
from .stop_feasibility import validate_stop
from .takeprofit_feasibility import validate_take_profit

def construct_execution_plan(*, decision, runtime, account, execution_constraints, broker_constraints,
                             account_policy, portfolio_exposure, portfolio_policy):
    """Determine safety, never decision merit and never broker execution."""
    reasons=[]; deferred=False
    if decision.replay_identity != decision_replay_identity(decision.canonical_payload()):
        reasons.append("DECISION_REPLAY_IDENTITY_INVALID")
    if decision.decision not in {"BUY", "SELL"}:
        reasons.append("DECISION_NOT_AUTHORIZED")
    if execution_constraints.execution_model_id != decision.candidate.execution_model_id:
        reasons.append("EXECUTION_MODEL_MISMATCH")
    if runtime.heartbeat_age_seconds > execution_constraints.maximum_runtime_age_seconds:
        reasons.append("RUNTIME_CONTEXT_STALE")
    required=(execution_constraints.entry_price, execution_constraints.protective_stop,
              execution_constraints.target, execution_constraints.requested_volume,
              execution_constraints.volatility_distance)
    if any(v is None for v in required):
        deferred=True; reasons.append("EXECUTION_REQUIREMENT_MISSING")
    direction=decision.direction if decision.decision in {"BUY", "SELL"} else "NONE"
    entry=execution_constraints.entry_price or 0
    volume=execution_constraints.requested_volume or 0
    account_check=assess_account_risk(account, account_policy)
    reasons.extend(() if account_check.status == "VALID" else account_check.reasons)
    rr=validate_reward_risk(entry_price=entry, stop=execution_constraints.protective_stop,
                            target=execution_constraints.target, minimum_ratio=execution_constraints.minimum_reward_risk)
    stop=validate_stop(entry_price=entry, stop=execution_constraints.protective_stop, direction=direction,
        minimum_distance=broker_constraints.stop_level, volatility_distance=execution_constraints.volatility_distance or 0)
    target=validate_take_profit(entry_price=entry, target=execution_constraints.target, direction=direction,
                                minimum_distance=broker_constraints.stop_level)
    for check in (rr, stop, target):
        if getattr(check, "execution_viability", getattr(check, "status", None)) != "VALID":
            reasons.extend(check.reasons); deferred |= getattr(check, "status", "") == "DEFERRED"
    budget=construct_position_budget(account, account_policy, account_check, risk_per_volume=rr.expected_risk)
    if budget.status != "VALID" or volume > budget.maximum_position_size: reasons.append("POSITION_BUDGET_EXCEEDED")
    portfolio_status, portfolio_reasons=assess_portfolio(portfolio_exposure, portfolio_policy, volume)
    if portfolio_status != "VALID": reasons.extend(portfolio_reasons)
    broker=validate_broker_constraints(broker_constraints, volume=volume, stop_distance=rr.expected_risk,
        target_distance=rr.expected_reward, free_margin=account.free_margin)
    if broker.status != "VALID": reasons.extend(broker.reasons)
    reasons=tuple(dict.fromkeys(reasons)) or ("ALL_RISK_CONSTRUCTION_CHECKS_VALID",)
    ready=reasons == ("ALL_RISK_CONSTRUCTION_CHECKS_VALID",)
    status="APPROVED" if ready else ("DEFERRED" if deferred else "REJECTED")
    values=dict(decision_replay_identity=decision.replay_identity,
        runtime_sequence_id=int(runtime.market.get("sequence_id", -1)), symbol=decision.candidate.symbol,
        direction=direction, volume=volume, protective_stop=execution_constraints.protective_stop,
        target=execution_constraints.target, execution_constraints=execution_constraints,
        approval_status=status, execution_ready=ready, validation_reasons=reasons,
        policy_references=(f"{POLICY_ID}@{POLICY_VERSION}", decision.policy_references[0]),
        policy_version=POLICY_VERSION, schema_version=SCHEMA_VERSION)
    return ExecutionPlan(**values, replay_identity=plan_identity(values))
