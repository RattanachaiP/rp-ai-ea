"""PR265 direct-chain, campaign, integrity and fail-closed validation."""
from dataclasses import replace
import pytest
from bridge.v28.certification_report import build_certification_report
from bridge.v28.delivery_pipeline_validator import validate_delivery
from bridge.v28.execution_bridge import DeliveryReceipt
from bridge.v28.execution_plan import identity
from bridge.v28.market_snapshot import build_market_snapshot
from bridge.v28.operational_readiness import assess_operational_readiness
from bridge.v28.pipeline_validator import (MARKET_POLICY,RUNTIME_POLICY,MarketIntelligenceEvidence,
 MarketStateEvidence,NormalizedMarketEvidence,RuntimeFoundationEvidence,bind_evidence,create_campaign,
 validate_pipeline,certification_identity)
from bridge.v28.replay_consistency_checker import ReplayPair,check_replay
from bridge.v28.risk_construction import construct_execution_plan
from bridge.v28.runtime_certifier import certify_runtime
from bridge.v28.shadow_validation_runner import ShadowCase,run_shadow_validation
from tests.test_v28_risk_construction import EVAL,inputs,integration_boundary

def chain(side="BUY"):
    values=inputs(side); decision=values["decision"]; runtime_context=values["runtime"]
    plan,contract,_,health,broker,publication,environment,approval=integration_boundary(construct_execution_plan(**values))
    market=runtime_context.market
    ms=bind_evidence(MarketStateEvidence,"V28_MARKET_STATE_EVIDENCE",sequence_id=11,symbol="XAUUSD",heartbeat_unix=100,observed_at=EVAL,source_authority="MARKET_STATE_PRODUCER",policy_reference=RUNTIME_POLICY)
    rt=bind_evidence(RuntimeFoundationEvidence,"V28_RUNTIME_FOUNDATION_EVIDENCE",runtime_context=runtime_context,source_replay_identity=ms.replay_identity,normalized=True,source_authority="V28_RUNTIME",boundary_healthy=True,policy_reference=RUNTIME_POLICY)
    snapshot=build_market_snapshot(market)
    nm=bind_evidence(NormalizedMarketEvidence,"V28_NORMALIZED_MARKET_EVIDENCE",snapshot=snapshot,market_state_replay_identity=ms.replay_identity,evaluation_time=EVAL,source_authority="V28_MARKET_NORMALIZER",policy_reference=MARKET_POLICY)
    contexts=tuple(getattr(runtime_context,x) for x in ("structure","regime","trend","momentum","volatility","liquidity","opportunity"))
    mi=bind_evidence(MarketIntelligenceEvidence,"V28_MARKET_INTELLIGENCE_EVIDENCE",contexts=contexts,normalized_market_replay_identity=nm.replay_identity,sequence_id=11,symbol="XAUUSD",evaluation_time=EVAL,policy_reference=MARKET_POLICY)
    campaign=create_campaign(runtime_sequence_id=11,symbol="XAUUSD",evaluation_time=EVAL,decision_replay_identity=decision.replay_identity,plan_replay_identity=plan.replay_identity,publication_replay_identity=publication.publication_replay_identity,environment_identity=environment.replay_identity)
    return dict(campaign=campaign,market_state=ms,runtime=rt,normalized_market=nm,market_intelligence=mi,opportunity=runtime_context.opportunity,decision=decision,plan=plan,contract=contract,health=health,broker=broker,publication=publication),environment,approval

def pipeline(args=None):
    args=args or chain()[0];return validate_pipeline(**args)

def receipt_for(args,environment,status="DELIVERED"):
    v=dict(status=status,reason="DELIVERED_TO_V27_EXECUTOR" if status=="DELIVERED" else "REJECTED",execution_plan_replay_identity=args["plan"].replay_identity,executor_contract_replay_identity=args["contract"].replay_identity,publication_replay_identity=args["publication"].publication_replay_identity,environment_identity=environment.replay_identity,executor_instance_identity=environment.executor_instance_identity,runtime_sequence_id=11,delivered_at=EVAL,downstream_result_identity="v27-result" if status=="DELIVERED" else "NONE")
    return DeliveryReceipt(**v,replay_identity=identity("V28_DELIVERY_RECEIPT_REPLAY",v))

def reports():
    args,env,approval=chain(); p=pipeline(args)
    delivery=validate_delivery(campaign=args["campaign"],plan=args["plan"],contract=args["contract"],publication=args["publication"],environment=env,approval=approval,receipt=receipt_for(args,env))
    replay=check_replay(args["campaign"],[ReplayPair(args["plan"],construct_execution_plan(**inputs()))])
    buy=chain("BUY")[0];sell=chain("SELL")[0];held=inputs();held["execution_constraints"]=replace(held["execution_constraints"],runtime_health_valid=False);hold=construct_execution_plan(**held)
    shadow=run_shadow_validation(args["campaign"],[ShadowCase("BUY",buy["plan"],buy["publication"]),ShadowCase("SELL",sell["plan"],sell["publication"]),ShadowCase("HOLD",hold,None)],recorded_at=EVAL)
    runtime=certify_runtime(p,delivery); readiness=assess_operational_readiness(p,replay,shadow,delivery,runtime)
    return p,replay,shadow,delivery,runtime,readiness

def test_complete_direct_chain_and_campaign_pass():
    values=reports();assert all(x.status=="PASS" for x in values)
    cert=build_certification_report(*values[:5],values[5]);assert cert.status=="PASS" and not cert.production_authorized

@pytest.mark.parametrize(("field","reason"),[("decision","DECISION_CONTEXT_INVALID"),("market_state","MARKET_STATE_INVALID"),("market_intelligence","MARKET_INTELLIGENCE_INVALID")])
def test_missing_or_malformed_evidence_returns_fail_not_exception(field,reason):
    args=chain()[0];args[field]=None;r=pipeline(args);assert r.status=="FAIL" and any(reason in x.failures for x in r.boundaries)

@pytest.mark.parametrize(("mutation","reason"),[("sequence","MARKET_SEQUENCE_MISMATCH"),("symbol","MARKET_SYMBOL_MISMATCH"),("policy","MARKET_POLICY_MISMATCH")])
def test_market_field_and_policy_mismatch(mutation,reason):
    args=chain()[0];v=args["market_state"].canonical_payload()
    if mutation=="sequence":v["sequence_id"]=12
    elif mutation=="symbol":v["symbol"]="EURUSD"
    else:v["policy_reference"]="wrong"
    args["market_state"]=bind_evidence(MarketStateEvidence,"V28_MARKET_STATE_EVIDENCE",**v)
    assert any(reason in x.failures for x in pipeline(args).boundaries)

def test_readiness_rejects_forgery_duplicates_missing_and_campaign_mismatch():
    p,replay,shadow,delivery,runtime,_=reports()
    assert assess_operational_readiness(p,replay,shadow,delivery).status=="FAIL"
    assert assess_operational_readiness(p,p,replay,shadow,delivery,runtime).status=="FAIL"
    object.__setattr__(replay,"status","FAIL");assert assess_operational_readiness(p,replay,shadow,delivery,runtime).status=="FAIL"

def test_delivery_environment_executor_stale_future_and_downstream_rules():
    args,env,approval=chain(); receipt=receipt_for(args,env)
    object.__setattr__(receipt,"environment_identity","wrong")
    r=validate_delivery(campaign=args["campaign"],plan=args["plan"],contract=args["contract"],publication=args["publication"],environment=env,approval=approval,receipt=receipt);assert r.status=="FAIL"
    receipt=receipt_for(args,env);object.__setattr__(receipt,"executor_instance_identity","wrong")
    assert validate_delivery(campaign=args["campaign"],plan=args["plan"],contract=args["contract"],publication=args["publication"],environment=env,approval=approval,receipt=receipt).status=="FAIL"
    receipt=receipt_for(args,env);object.__setattr__(receipt,"delivered_at","1970-01-01T00:01:44Z")
    assert validate_delivery(campaign=args["campaign"],plan=args["plan"],contract=args["contract"],publication=args["publication"],environment=env,approval=approval,receipt=receipt).status=="FAIL"

def test_nested_tamper_campaign_mismatch_shadow_incomplete_and_callable_forbidden():
    p,replay,shadow,delivery,runtime,ready=reports();object.__setattr__(p,"status","FAIL")
    with pytest.raises(ValueError,match="INTEGRITY"):build_certification_report(p,replay,shadow,delivery,runtime,ready)
    args=chain()[0]; incomplete=run_shadow_validation(args["campaign"],[ShadowCase("BUY",args["plan"],args["publication"])],recorded_at=EVAL);assert incomplete.status=="FAIL"
    with pytest.raises(ValueError,match="FORBIDDEN"):ReplayPair(lambda:None,args["plan"])

def test_warning_removed_from_certification_ontology():
    from bridge.v28.pipeline_validator import BoundaryResult
    from bridge.v28.runtime_certifier import ComponentCertification
    with pytest.raises(ValueError):BoundaryResult("X","WARNING",("X",),())
    with pytest.raises(ValueError):ComponentCertification("DELIVERY","WARNING",("X",))
