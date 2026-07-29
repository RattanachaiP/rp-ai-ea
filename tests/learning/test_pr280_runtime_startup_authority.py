"""PR280 final pre-executor handoff, adversarial consumption, and CAS tests."""
from dataclasses import FrozenInstanceError, replace
import hashlib
import hmac
import json
import pytest

from learning.runtime_startup import (STARTUP_AUTHORIZED, STARTUP_GATES,
    RuntimeStartupAuthorizationConsumption, RuntimeStartupAuthority, RuntimeStartupContract,
    RuntimeStartupContractTemplate, RuntimeStartupError, RuntimeStartupGovernanceBundle,
    RuntimeStartupPolicy, RuntimeStartupRegistry, StartupGovernanceStatus)
from tests.learning.test_pr275_deployment_governance import promoted as promoted_fixture
from tests.learning.test_pr276_production_release_authority import context
from tests.learning.test_pr279_executor_acknowledgement_authority import (admitted,
    authority as acknowledgement_authority, bundle as acknowledgement_bundle)

NOW="2026-07-29T09:32:40Z"
AUTHORITY="runtime-startup-authority"
AUTHORITY_INSTANCE="runtime-startup-authority-01"
CONSUMPTION_NONCE="startup-consumption-nonce-0001"
CONSUMER_KEY=b"v27-runtime-startup-consumer-key"

@pytest.fixture
def acknowledged(admitted):
    authority=acknowledgement_authority(); result=authority.acknowledge(acknowledgement_bundle(admitted))
    return result,authority.registry

def authority(registry=None,**changes):
    values={"startup_authority_identity":AUTHORITY,
        "startup_authority_instance_identity":AUTHORITY_INSTANCE,
        "trusted_consumer_keys":{("V27_PRODUCTION_EXECUTOR","27.1","v27-production-instance-01"):CONSUMER_KEY},
        "registry":registry}
    values.update(changes); return RuntimeStartupAuthority(**values)

def inputs(acknowledged,registry=None,**changes):
    result,acks=acknowledged; a=result.acknowledgement_authorization; evidence=result.acknowledgement_evidence
    template=RuntimeStartupContractTemplate("1.0","COLD_START",True)
    policy=RuntimeStartupPolicy("1.0",("PRODUCTION",),(a.executor_identity,),(a.executor_version,),
        (evidence.runtime_contract_identity,),"executor-acknowledgement-authority",template.template_identity,
        30,20,0,(a.activation_generation,))
    contract=RuntimeStartupContract(template.template_identity,a.runtime_instance_identity,a.executor_identity,
        a.executor_version,a.executor_instance_identity,a.executor_session_identity,a.activation_generation,
        evidence.runtime_contract_identity,evidence.target_environment_identity,"PRODUCTION",
        evidence.artifact_identity,"startup-config-v1","v27-process",a.executor_identity,
        CONSUMPTION_NONCE,policy.policy_identity)
    startup=RuntimeStartupRegistry() if registry is None else registry
    values=dict(acknowledgement_authorization=a,acknowledgement_registry=acks,
        acknowledgement_registry_entry=result.registry_entry,startup_contract_template=template,
        startup_policy=policy,startup_contract=contract,startup_registry=startup,
        expected_acknowledgement_registry_identity=acks.registry_identity,
        expected_startup_registry_identity=startup.registry_identity,
        expected_predecessor_registry_identity=startup.previous_registry_identity,
        canonical_evaluation_timestamp=NOW,acknowledgement_authority_identity="executor-acknowledgement-authority",
        startup_authority_identity=AUTHORITY,startup_authority_instance_identity=AUTHORITY_INSTANCE)
    values.update(changes); return RuntimeStartupGovernanceBundle(**values)

def rejection(acknowledged,registry=None,**changes):
    owner=authority(registry); bundle=inputs(acknowledged,registry,**changes)
    with pytest.raises(RuntimeStartupError) as caught: owner.authorize(bundle)
    assert caught.value.result.decision=="STARTUP_REJECTED"
    return caught.value.result,owner

def consumption(authorization,**changes):
    values=dict(authorization_identity=authorization.authorization_identity,
        executor_identity=authorization.executor_identity,executor_version=authorization.executor_version,
        executor_instance_identity=authorization.executor_instance_identity,
        executor_session_identity=authorization.executor_session_identity,
        runtime_instance_identity=authorization.runtime_instance_identity,
        activation_generation=authorization.activation_generation,
        consumer_identity=authorization.authorized_consumer_identity,
        consumed_at="2026-07-29T09:32:50Z",nonce=authorization.expected_consumption_nonce,signature="pending")
    values.update(changes); unsigned=RuntimeStartupAuthorizationConsumption(**values)
    signature=hmac.new(CONSUMER_KEY,json.dumps(unsigned.signing_payload(),sort_keys=True,
        separators=(",",":"),ensure_ascii=True).encode(),hashlib.sha256).hexdigest()
    return replace(unsigned,signature=signature,consumption_identity="")

def test_valid_result_is_final_pre_executor_handoff_only(acknowledged):
    result=authority().authorize(inputs(acknowledged)); authorization=result.authorization
    assert result.decision==STARTUP_AUTHORIZED
    assert tuple(x.gate for x in result.evidence.gate_results)==STARTUP_GATES
    assert authorization.startup_handoff_authorized and authorization.single_use
    assert not hasattr(authorization,"runtime_startup_authorized")
    assert not any((authorization.runtime_started,authorization.executor_invoked,
        authorization.broker_access_authorized,authorization.broker_connected,
        authorization.order_submission_authorized,authorization.trade_execution_authorized))
    assert [x.to_state for x in result.registry_entry.lifecycle]==["VALIDATED","STARTUP_AUTHORIZED","REGISTERED"]

@pytest.mark.parametrize("field,value,gate",[
    ("executor_identity","wrong","executor_identity"),("executor_version","wrong","executor_version"),
    ("executor_instance_identity","wrong","executor_instance_identity"),("executor_session_identity","wrong","executor_session_identity"),
    ("runtime_instance_identity","wrong","runtime_instance_identity"),("activation_generation",999,"activation_generation"),
    ("artifact_identity","wrong","artifact_identity"),("runtime_contract_identity","wrong","runtime_contract_identity"),
    ("target_environment_identity","wrong","target_environment_identity")])
def test_contract_lineage_mismatches_reject(acknowledged,field,value,gate):
    original=inputs(acknowledged); contract=replace(original.startup_contract,**{field:value},contract_identity="")
    result,_=rejection(acknowledged,startup_contract=contract)
    assert not next(x for x in result.evidence.gate_results if x.gate==gate).passed

def test_acknowledgement_not_future_and_freshness_are_distinct(acknowledged):
    for timestamp,gate in (("2026-07-29T09:32:29Z","acknowledgement_not_future"),
            ("2026-07-29T09:33:01Z","acknowledgement_freshness")):
        result,_=rejection(acknowledged,canonical_evaluation_timestamp=timestamp)
        assert not next(x for x in result.evidence.gate_results if x.gate==gate).passed

def test_template_and_configuration_identities_are_separate(acknowledged):
    bundle=inputs(acknowledged)
    assert bundle.startup_contract_template.template_identity != bundle.startup_contract.expected_configuration_identity
    wrong=replace(bundle.startup_contract,startup_contract_template_identity="wrong",contract_identity="")
    rejection(acknowledged,startup_contract=wrong)
    changed=replace(bundle.startup_contract,expected_configuration_identity="another-config",contract_identity="")
    assert authority().authorize(inputs(acknowledged,startup_contract=changed)).authorization.startup_contract_template_identity == bundle.startup_contract_template.template_identity

def test_authority_and_instance_are_bound_and_authenticated(acknowledged):
    result=authority().authorize(inputs(acknowledged))
    assert result.evidence.startup_authority_identity==result.authorization.startup_authority_identity==AUTHORITY
    assert result.evidence.startup_authority_instance_identity==result.authorization.startup_authority_instance_identity==AUTHORITY_INSTANCE
    rejection(acknowledged,startup_authority_instance_identity="impostor")

def test_registry_membership_and_ancestry_reject(acknowledged):
    rejection(acknowledged,expected_acknowledgement_registry_identity="wrong")
    empty=type(acknowledged[1])()
    rejection(acknowledged,acknowledgement_registry=empty,expected_acknowledgement_registry_identity=empty.registry_identity)
    rejection(acknowledged,expected_predecessor_registry_identity="wrong")

@pytest.mark.parametrize("kind,subject_type,selector",[
    ("REVOCATION","ACKNOWLEDGEMENT_AUTHORIZATION","ack"),
    ("SUPERSESSION","ACKNOWLEDGEMENT_ENTRY","entry"),("REVOCATION","ARTIFACT","artifact"),
    ("REVOCATION","RUNTIME_INSTANCE","runtime"),("EMERGENCY_ROLLBACK","GLOBAL","global")])
def test_registry_is_only_status_source_and_typed_semantics_apply_before_issue(acknowledged,kind,subject_type,selector):
    bundle=inputs(acknowledged); values={"ack":bundle.acknowledgement_authorization.authorization_identity,
        "entry":bundle.acknowledgement_registry_entry.entry_identity,"artifact":bundle.startup_contract.artifact_identity,
        "runtime":bundle.startup_contract.runtime_instance_identity,"global":"GLOBAL"}
    status=StartupGovernanceStatus(kind,subject_type,values[selector],"2026-07-29T09:32:35Z","governance","incident")
    registry=RuntimeStartupRegistry().apply_status(status,RuntimeStartupRegistry().registry_identity)
    rejection(acknowledged,registry=registry)
    assert not hasattr(bundle,"governance_statuses")

def test_true_two_authority_cas_against_same_snapshot(acknowledged):
    snapshot=RuntimeStartupRegistry(); left=authority(snapshot); right=authority(snapshot)
    left_result=left.authorize(inputs(acknowledged,snapshot)); right_result=right.authorize(inputs(acknowledged,snapshot))
    assert left_result==right_result
    committed=snapshot.append(left_result.registry_entry,snapshot.registry_identity,snapshot.previous_registry_identity)
    with pytest.raises(ValueError,match="REGISTRY_CONFLICT"):
        committed.append(right_result.registry_entry,snapshot.registry_identity,snapshot.previous_registry_identity)

def test_duplicate_authorization_and_rejection_deduplication(acknowledged):
    owner=authority(); owner.authorize(inputs(acknowledged))
    with pytest.raises(RuntimeStartupError): owner.authorize(inputs(acknowledged,owner.registry))
    result,rejected=rejection(acknowledged,expected_acknowledgement_registry_identity="wrong")
    with pytest.raises(ValueError,match="REJECTION_REPLAY"):
        rejected.registry.append(result.registry_entry,rejected.registry.registry_identity,rejected.registry.previous_registry_identity)

def test_result_binding_validation_rejects_tampering(acknowledged):
    result=authority().authorize(inputs(acknowledged))
    with pytest.raises(ValueError,match="RESULT_INVALID"):
        replace(result,result_identity="wrong")
    with pytest.raises(ValueError,match="RESULT_INVALID"):
        replace(result,decision="STARTUP_REJECTED")

@pytest.mark.parametrize("field,value",[
    ("executor_identity","wrong"),("executor_version","wrong"),("executor_instance_identity","wrong"),
    ("executor_session_identity","wrong"),("runtime_instance_identity","wrong"),
    ("activation_generation",999),("consumer_identity","wrong"),("nonce","wrong")])
def test_adversarial_consumption_binding_rejects(acknowledged,field,value):
    owner=authority(); result=owner.authorize(inputs(acknowledged)); request=consumption(result.authorization,**{field:value})
    with pytest.raises(ValueError,match="CONSUMER_(AUTHENTICATION|BINDING)_INVALID"):
        owner.consume(request,owner.registry.registry_identity)

def test_forged_executor_consumption_signature_rejects(acknowledged):
    owner=authority(); result=owner.authorize(inputs(acknowledged)); request=consumption(result.authorization)
    forged=replace(request,signature="forged",consumption_identity="")
    with pytest.raises(ValueError,match="AUTHENTICATION_INVALID"):
        owner.consume(forged,owner.registry.registry_identity)

def test_consumption_is_immutable_single_use_and_nonce_replay_safe(acknowledged):
    owner=authority(); result=owner.authorize(inputs(acknowledged)); request=consumption(result.authorization)
    returned=owner.consume(request,owner.registry.registry_identity)
    assert returned==request and owner.registry.consumptions==(request,)
    with pytest.raises(ValueError,match="REPLAY"):
        owner.consume(request,owner.registry.registry_identity)
    with pytest.raises(FrozenInstanceError): request.nonce="tampered"

def test_identical_typed_status_semantics_invalidate_before_consumption(acknowledged):
    owner=authority(); result=owner.authorize(inputs(acknowledged))
    status=StartupGovernanceStatus("REVOCATION","STARTUP_AUTHORIZATION",
        result.authorization.authorization_identity,"2026-07-29T09:32:45Z",AUTHORITY,"operator action")
    owner.record_status(status,owner.registry.registry_identity)
    with pytest.raises(ValueError,match="INVALIDATED"):
        owner.consume(consumption(result.authorization),owner.registry.registry_identity)

def test_expiry_deterministic_replay_and_immutability(acknowledged):
    left=authority().authorize(inputs(acknowledged)); right=authority().authorize(inputs(acknowledged)); assert left==right
    owner=authority(); result=owner.authorize(inputs(acknowledged))
    with pytest.raises(ValueError,match="EXPIRED"):
        owner.consume(consumption(result.authorization,consumed_at="2026-07-29T09:33:01Z"),owner.registry.registry_identity)
    for target,name in ((inputs(acknowledged).startup_contract,"executor_identity"),(left.authorization,"runtime_started")):
        with pytest.raises(FrozenInstanceError): setattr(target,name,"tampered")
