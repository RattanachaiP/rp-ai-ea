"""PR280 startup authorization, adversarial, replay and immutability tests."""
from dataclasses import FrozenInstanceError, replace
import pytest

from learning.runtime_startup import (STARTUP_AUTHORIZED, STARTUP_GATES, RuntimeStartupAuthority,
    RuntimeStartupContract, RuntimeStartupError, RuntimeStartupGovernanceBundle,
    RuntimeStartupPolicy, RuntimeStartupRegistry, StartupGovernanceStatus)
from tests.learning.test_pr279_executor_acknowledgement_authority import (admitted,
    authority as acknowledgement_authority, bundle as acknowledgement_bundle)
from tests.learning.test_pr276_production_release_authority import context
from tests.learning.test_pr275_deployment_governance import promoted as promoted_fixture

NOW="2026-07-29T09:32:40Z"
CONFIG="startup-config-v1"

@pytest.fixture
def acknowledged(admitted):
    authority=acknowledgement_authority(); result=authority.acknowledge(acknowledgement_bundle(admitted))
    return result,authority.registry

def inputs(acknowledged,registry=None,**changes):
    result,acks=acknowledged; a=result.acknowledgement_authorization; evidence=result.acknowledgement_evidence
    policy=RuntimeStartupPolicy("1.0",("PRODUCTION",),(a.executor_identity,),(a.executor_version,),
        (evidence.runtime_contract_identity,),"executor-acknowledgement-authority",CONFIG,30,20,0,
        (a.activation_generation,))
    contract=RuntimeStartupContract(a.runtime_instance_identity,a.executor_identity,a.executor_version,
        a.executor_instance_identity,a.executor_session_identity,a.activation_generation,
        evidence.runtime_contract_identity,evidence.target_environment_identity,"PRODUCTION",
        evidence.artifact_identity,"COLD_START",CONFIG,"v27-process",policy.policy_identity)
    startup=registry or RuntimeStartupRegistry()
    values=dict(acknowledgement_authorization=a,acknowledgement_registry=acks,
        acknowledgement_registry_entry=result.registry_entry,startup_policy=policy,startup_contract=contract,
        startup_registry=startup,expected_acknowledgement_registry_identity=acks.registry_identity,
        expected_startup_registry_identity=startup.registry_identity,
        expected_predecessor_registry_identity=startup.previous_registry_identity,
        canonical_evaluation_timestamp=NOW,acknowledgement_authority_identity="executor-acknowledgement-authority")
    values.update(changes); return RuntimeStartupGovernanceBundle(**values)

def rejection(acknowledged,**changes):
    authority=RuntimeStartupAuthority()
    with pytest.raises(RuntimeStartupError) as caught: authority.authorize(inputs(acknowledged,**changes))
    assert caught.value.result.decision=="STARTUP_REJECTED"
    return caught.value.result

def test_valid_startup_authorization_is_governance_only(acknowledged):
    result=RuntimeStartupAuthority().authorize(inputs(acknowledged)); authorization=result.authorization
    assert result.decision==STARTUP_AUTHORIZED
    assert tuple(x.gate for x in result.evidence.gate_results)==STARTUP_GATES
    assert authorization.runtime_startup_authorized and authorization.single_use
    assert not any((authorization.runtime_started,authorization.executor_invoked,
        authorization.broker_access_authorized,authorization.broker_connected,
        authorization.order_submission_authorized,authorization.trade_execution_authorized))
    assert [x.to_state for x in result.registry_entry.lifecycle]==["VALIDATED","STARTUP_AUTHORIZED","REGISTERED","STARTUP_PENDING"]

@pytest.mark.parametrize("field,value,gate",[
    ("executor_identity","wrong","executor_identity"),("executor_version","wrong","executor_version"),
    ("executor_instance_identity","wrong","executor_instance_identity"),("executor_session_identity","wrong","executor_session_identity"),
    ("runtime_instance_identity","wrong","runtime_instance_identity"),("activation_generation",999,"activation_generation"),
    ("artifact_identity","wrong","artifact_identity"),("runtime_contract_identity","wrong","runtime_contract_identity"),
    ("target_environment_identity","wrong","target_environment_identity")])
def test_contract_lineage_mismatches_reject(acknowledged,field,value,gate):
    original=inputs(acknowledged); contract=replace(original.startup_contract,**{field:value},contract_identity="")
    result=rejection(acknowledged,startup_contract=contract)
    assert not next(x for x in result.evidence.gate_results if x.gate==gate).passed

def test_invalid_acknowledgement_authorization_rejects(acknowledged):
    bundle=inputs(acknowledged)
    other=replace(bundle.acknowledgement_authorization,executor_session_identity="other",authorization_identity="")
    assert not next(x for x in rejection(acknowledged,acknowledgement_authorization=other).evidence.gate_results if x.gate=="acknowledgement_registry_membership").passed

@pytest.mark.parametrize("timestamp",["2026-07-29T09:33:01Z","2026-07-29T09:32:29Z"])
def test_expired_and_future_acknowledgement_reject(timestamp,acknowledged):
    rejection(acknowledged,canonical_evaluation_timestamp=timestamp)

def test_registry_identity_membership_and_ancestry_reject(acknowledged):
    rejection(acknowledged,expected_acknowledgement_registry_identity="wrong")
    empty=type(acknowledged[1])()
    rejection(acknowledged,acknowledgement_registry=empty,
        expected_acknowledgement_registry_identity=empty.registry_identity)
    rejection(acknowledged,expected_predecessor_registry_identity="wrong")

@pytest.mark.parametrize("kind,subject",[("REVOCATION","ack"),("SUPERSESSION","ack"),
    ("REVOCATION","artifact"),("REVOCATION","runtime"),("EMERGENCY_ROLLBACK","GLOBAL")])
def test_revocation_supersession_and_emergency_rollback_reject(acknowledged,kind,subject):
    bundle=inputs(acknowledged)
    identities={"ack":bundle.acknowledgement_authorization.authorization_identity,
        "artifact":bundle.startup_contract.artifact_identity,"runtime":bundle.startup_contract.runtime_instance_identity,"GLOBAL":"GLOBAL"}
    status=StartupGovernanceStatus(kind,identities[subject],"2026-07-29T09:32:35Z","governance","incident")
    rejection(acknowledged,governance_statuses=(status,))

def test_policy_contract_and_environment_compliance_reject(acknowledged):
    bundle=inputs(acknowledged)
    policy=replace(bundle.startup_policy,allowed_environment_classes=("DEMO",),policy_identity="")
    contract=replace(bundle.startup_contract,startup_policy_identity=policy.policy_identity,contract_identity="")
    rejection(acknowledged,startup_policy=policy,startup_contract=contract)
    rejection(acknowledged,acknowledgement_authority_identity="wrong")
    contract=replace(bundle.startup_contract,expected_configuration_identity="wrong",contract_identity="")
    rejection(acknowledged,startup_contract=contract)

def test_duplicate_authorization_and_cas_conflict(acknowledged):
    authority=RuntimeStartupAuthority(); first=authority.authorize(inputs(acknowledged))
    with pytest.raises(RuntimeStartupError): authority.authorize(inputs(acknowledged,registry=authority.registry))
    stale=RuntimeStartupAuthority(registry=authority.registry)
    with pytest.raises(RuntimeStartupError,match="REGISTRY_CONFLICT"):
        stale.authorize(inputs(acknowledged,registry=authority.registry,expected_startup_registry_identity=RuntimeStartupRegistry().registry_identity))
    assert first.authorization is not None

def test_single_use_consumption_expiry_and_duplicate_consumption(acknowledged):
    authority=RuntimeStartupAuthority(); result=authority.authorize(inputs(acknowledged))
    before=authority.registry.registry_identity
    authority.consume(result.authorization.authorization_identity,"2026-07-29T09:32:50Z",before)
    with pytest.raises(ValueError,match="REPLAY"):
        authority.consume(result.authorization.authorization_identity,"2026-07-29T09:32:51Z",authority.registry.registry_identity)
    another=RuntimeStartupAuthority(); result=another.authorize(inputs(acknowledged))
    with pytest.raises(ValueError,match="EXPIRED"):
        another.consume(result.authorization.authorization_identity,"2026-07-29T09:33:01Z",another.registry.registry_identity)

def test_stale_generation_and_cross_session_replay(acknowledged):
    base=inputs(acknowledged); authority=RuntimeStartupAuthority(); authority.authorize(base)
    # The exact scope is already authorized, so both same-generation and attempts to
    # relabel the executor session fail closed rather than creating a second grant.
    with pytest.raises(RuntimeStartupError): authority.authorize(inputs(acknowledged,registry=authority.registry))
    changed=replace(base.startup_contract,executor_session_identity="another",contract_identity="")
    with pytest.raises(RuntimeStartupError): authority.authorize(inputs(acknowledged,registry=authority.registry,startup_contract=changed))

def test_deterministic_success_and_rejection_replay(acknowledged):
    left=RuntimeStartupAuthority().authorize(inputs(acknowledged)); right=RuntimeStartupAuthority().authorize(inputs(acknowledged))
    assert left==right
    bad=inputs(acknowledged,expected_acknowledgement_registry_identity="wrong")
    evidence=[]
    for _ in range(2):
        try: RuntimeStartupAuthority().authorize(bad)
        except RuntimeStartupError as exc: evidence.append(exc.result)
    assert evidence[0]==evidence[1]

def test_authorization_revocation_and_supersession_status_are_enforced_before_issue(acknowledged):
    bundle=inputs(acknowledged)
    for kind in ("REVOCATION","SUPERSESSION"):
        status=StartupGovernanceStatus(kind,bundle.startup_contract.runtime_instance_identity,
            "2026-07-29T09:32:40Z","startup-authority","operator action")
        rejection(acknowledged,governance_statuses=(status,))

@pytest.mark.parametrize("kind",["REVOCATION","SUPERSESSION"])
def test_issued_authorization_is_immediately_invalidated_before_consumption(acknowledged,kind):
    authority=RuntimeStartupAuthority(); result=authority.authorize(inputs(acknowledged))
    status=StartupGovernanceStatus(kind,result.authorization.authorization_identity,
        "2026-07-29T09:32:45Z","startup-authority","operator action")
    authority.record_status(status,authority.registry.registry_identity)
    with pytest.raises(ValueError,match="INVALIDATED"):
        authority.consume(result.authorization.authorization_identity,"2026-07-29T09:32:50Z",authority.registry.registry_identity)

def test_contract_policy_authorization_and_registry_are_immutable(acknowledged):
    authority=RuntimeStartupAuthority(); bundle=inputs(acknowledged); result=authority.authorize(bundle)
    for target,name in ((bundle.startup_contract,"executor_identity"),(bundle.startup_policy,"version"),
            (result.authorization,"runtime_started"),(authority.registry,"entries")):
        with pytest.raises(FrozenInstanceError): setattr(target,name,"tampered")

def test_noncanonical_timestamp_rejected(acknowledged):
    with pytest.raises(ValueError): inputs(acknowledged,canonical_evaluation_timestamp="not-a-timestamp")
