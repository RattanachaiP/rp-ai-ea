"""PR265 deterministic, fail-closed end-to-end certification tests."""
from dataclasses import replace

from bridge.v28.certification_report import build_certification_report
from bridge.v28.delivery_pipeline_validator import validate_delivery
from bridge.v28.execution_bridge import DeliveryReceipt
from bridge.v28.execution_plan import identity
from bridge.v28.operational_readiness import assess_operational_readiness
from bridge.v28.pipeline_validator import validate_pipeline
from bridge.v28.replay_consistency_checker import check_replay
from bridge.v28.runtime_certifier import certify_runtime
from bridge.v28.shadow_validation_runner import ShadowCase, run_shadow_validation
from tests.test_v28_risk_construction import EVAL, inputs, integration_boundary
from bridge.v28.risk_construction import construct_execution_plan


def test_complete_pipeline_certifies_and_is_deterministic():
    plan, contract, _, health, broker, publication, _, _ = integration_boundary()
    architecture = validate_pipeline(inputs()["decision"], plan, contract, health, broker,
                                     publication, evaluation_time=EVAL)
    assert architecture.status == "PASS"
    assert {item.boundary for item in architecture.boundaries} == {
        "MARKET_TO_DECISION", "DECISION_TO_RISK", "RISK_TO_EXECUTION", "EXECUTION_TO_PUBLICATION"}
    replay = check_replay(lambda: construct_execution_plan(**inputs()), run_count=3)
    runtime = certify_runtime(architecture)
    assert replay.status == runtime.status == "PASS"
    assert all(component.status == "PASS" for component in runtime.components)


def test_shadow_buy_sell_hold_is_reproducible_and_broker_free():
    buy = integration_boundary(construct_execution_plan(**inputs("BUY")))
    sell = integration_boundary(construct_execution_plan(**inputs("SELL")))
    held_inputs = inputs(); held_inputs["execution_constraints"] = replace(
        held_inputs["execution_constraints"], runtime_health_valid=False)
    hold_plan = construct_execution_plan(**held_inputs)
    report = run_shadow_validation((ShadowCase("BUY", buy[0], buy[5]),
                                    ShadowCase("SELL", sell[0], sell[5]),
                                    ShadowCase("HOLD", hold_plan, None)), recorded_at=EVAL)
    assert report.status == "PASS" and report.broker_submissions == 0
    assert set(report.actions) == {"BUY", "SELL", "HOLD"}


def test_delivery_and_aggregate_certification_preserve_v27_authority():
    plan, contract, _, health, broker, publication, _, _ = integration_boundary()
    receipt_values = dict(status="DELIVERED", reason="DELIVERED_TO_V27_EXECUTOR",
        execution_plan_replay_identity=plan.replay_identity,
        executor_contract_replay_identity=contract.replay_identity,
        publication_replay_identity=publication.publication_replay_identity,
        environment_identity="environment", executor_instance_identity="executor",
        runtime_sequence_id=plan.runtime_sequence_id, delivered_at=EVAL,
        downstream_result_identity="v27-result")
    receipt = DeliveryReceipt(**receipt_values,
        replay_identity=identity("V28_DELIVERY_RECEIPT_REPLAY", receipt_values))
    delivery = validate_delivery(plan, contract, publication, receipt)
    architecture = validate_pipeline(inputs()["decision"], plan, contract, health, broker,
                                     publication, evaluation_time=EVAL)
    replay = check_replay(lambda: construct_execution_plan(**inputs()))
    shadow = run_shadow_validation((ShadowCase("BUY", plan, publication),
        ShadowCase("SELL", integration_boundary(construct_execution_plan(**inputs("SELL")))[0],
                   integration_boundary(construct_execution_plan(**inputs("SELL")))[5]),
        ShadowCase("HOLD", construct_execution_plan(**{**inputs(), "execution_constraints": replace(inputs()["execution_constraints"], runtime_health_valid=False)}), None)), recorded_at=EVAL)
    runtime = certify_runtime(architecture)
    readiness = assess_operational_readiness(architecture, replay, shadow, runtime, delivery)
    certification = build_certification_report(architecture, replay, shadow, runtime, readiness)
    assert delivery.status == readiness.status == certification.status == "PASS"
    assert not readiness.production_authorized and not certification.production_authorized
    assert certification.to_json() == certification.to_json()


def test_any_boundary_mismatch_fails_closed():
    plan, contract, _, health, broker, publication, _, _ = integration_boundary()
    object.__setattr__(contract, "decision_replay_identity", "tampered")
    architecture = validate_pipeline(inputs()["decision"], plan, contract, health, broker,
                                     publication, evaluation_time=EVAL)
    runtime = certify_runtime(architecture)
    readiness = assess_operational_readiness(architecture, runtime)
    assert architecture.status == runtime.status == readiness.status == "FAIL"
    assert readiness.readiness == "READINESS_DENIED"
