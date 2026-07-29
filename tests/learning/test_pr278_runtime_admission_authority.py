"""PR278 current-governance, atomicity, lifecycle, and adversarial tests."""
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
import pytest

from learning.release import (ActivationRevocation,EmergencyRollbackAuthorization,
    ProductionReleaseAuthority,ReleaseCertificateRevocation,ReleaseRegistry)
from learning.runtime_activation import ActivationRegistry,RuntimeActivationAuthority
from learning.runtime_admission import (ExecutorAdmissionPolicy,ExecutorDescriptor,
    RuntimeAdmissionAuthority,RuntimeAdmissionError,RuntimeAdmissionGovernanceBundle,
    RuntimeAdmissionRegistry,RuntimeAdmissionResult)
from tests.learning.test_pr275_deployment_governance import promoted as promoted_fixture
from tests.learning.test_pr276_production_release_authority import bundle as release_bundle,context
from tests.learning.test_pr277_runtime_activation_authority import activation_bundle

@pytest.fixture
def activated(context):
    decision=ProductionReleaseAuthority().assess(release_bundle(context));releases=ReleaseRegistry().append(decision)
    chain=decision,releases,releases.entries[0],context["target_runtime_instance"]
    authority=RuntimeActivationAuthority();result=authority.activate(activation_bundle(chain))
    return result,authority.registry,releases,releases.entries[0]

def policy(version="27.1",age=120):
    return ExecutorAdmissionPolicy("production-executor-policy","admission-authority",
        (ExecutorDescriptor("V27_PRODUCTION_EXECUTOR",version),),age,60)

def bundle(activated,admission_registry=None,**changes):
    result,activations,releases,release_entry=activated;registry=admission_registry or RuntimeAdmissionRegistry()
    values=dict(release_registry=releases,release_registry_entry=release_entry,
        activation_registry=activations,activation_registry_entry=result.registry_entry,
        executor_handoff=result.executor_handoff,executor_admission_policy=policy(),
        admission_registry=registry,expected_release_registry_identity=releases.registry_identity,
        expected_activation_registry_identity=activations.registry_identity,
        expected_admission_registry_identity=registry.registry_identity,admitted_at="2026-07-29T09:32:00Z")
    values.update(changes);return RuntimeAdmissionGovernanceBundle(**values)

def test_authorizes_exactly_one_admission_without_executor_acknowledgement(activated):
    result=RuntimeAdmissionAuthority().authorize(bundle(activated));a=result.admission_authorization;x=result.executor_admission_authorization
    assert a.runtime_admission_authorized and x.executor_admission_authorized
    assert not x.executor_acknowledged and not x.broker_connection_performed and not x.trade_execution_performed
    assert not a.broker_access_authorized and not a.trade_execution_authorized
    assert [t.to_state for t in result.registry_entry.transitions]==["VALIDATED","ADMISSION_AUTHORIZED","RECORDED"]
    assert _roundtrip(result.executor_admission_authorization).authorization_identity==x.authorization_identity

def _roundtrip(value):return type(value)(**{x:getattr(value,x) for x in value.__dataclass_fields__})

def test_current_release_revocation_rollback_and_local_revocation_fail(activated):
    result,activations,releases,entry=activated;d=entry.decision;at="2026-07-29T09:31:30Z"
    variants=[releases.revoke_certificate(ReleaseCertificateRevocation(d.certificate.certificate_identity,"authority","incident",at)),
      releases.revoke_activation(ActivationRevocation(d.runtime_activation_authorization.authorization_identity,"authority","incident",at)),
      releases.authorize_rollback(EmergencyRollbackAuthorization(d.certificate.certificate_identity,d.certificate.rollback_manifest_identity,d.certificate.runtime_instance_identity,"authority","incident",at))]
    for current in variants:
        authority=RuntimeAdmissionAuthority()
        with pytest.raises(RuntimeAdmissionError,match="RELEASE_EFFECTIVENESS"):
            authority.authorize(bundle(activated,release_registry=current,expected_release_registry_identity=current.registry_identity))
        assert len(authority.registry.rejections)==1
    revoked=activations.revoke(ActivationRevocation(d.runtime_activation_authorization.authorization_identity,"authority","incident",at),releases,activations.registry_identity)
    with pytest.raises(RuntimeAdmissionError,match="ACTIVATION_EFFECTIVENESS"):
        RuntimeAdmissionAuthority().authorize(bundle(activated,activation_registry=revoked,expected_activation_registry_identity=revoked.registry_identity))

def test_release_supersession_fails(context,activated):
    newer_runtime=replace(context["target_runtime_instance"],activation_generation=8,instance_identity="")
    newer=ProductionReleaseAuthority().assess(release_bundle(context,target_runtime_instance=newer_runtime,assessed_at="2026-07-29T09:31:00Z"))
    current=activated[2].append(newer)
    with pytest.raises(RuntimeAdmissionError,match="RELEASE_EFFECTIVENESS"):
        RuntimeAdmissionAuthority().authorize(bundle(activated,release_registry=current,expected_release_registry_identity=current.registry_identity))

def test_policy_mismatch_upgrade_and_handoff_expiry_fail(activated):
    cases=[{"executor_admission_policy":policy("26.9")},{"executor_admission_policy":policy("27.2")},
           {"executor_admission_policy":policy(age=30),"admitted_at":"2026-07-29T09:32:01Z"}]
    expected=("EXECUTOR_POLICY","EXECUTOR_POLICY","HANDOFF_FRESHNESS")
    for change,reason in zip(cases,expected):
        authority=RuntimeAdmissionAuthority()
        with pytest.raises(RuntimeAdmissionError,match=reason):authority.authorize(bundle(activated,**change))

def test_stale_activation_registry_rejected_without_mutation(activated):
    authority=RuntimeAdmissionAuthority();value=bundle(activated,expected_activation_registry_identity="stale")
    with pytest.raises(RuntimeAdmissionError,match="ACTIVATION_REGISTRY_CONFLICT"):authority.authorize(value)
    assert not authority.registry.entries and not authority.registry.rejections

def test_concurrent_success_and_rejection_each_commit_once(activated):
    for value,success in ((bundle(activated),True),(bundle(activated,executor_admission_policy=policy("wrong")),False)):
        authority=RuntimeAdmissionAuthority()
        def run():
            try:return authority.authorize(value)
            except RuntimeAdmissionError as exc:return exc
        with ThreadPoolExecutor(max_workers=2) as pool:out=list(pool.map(lambda _:run(),range(2)))
        assert sum(isinstance(x,RuntimeAdmissionResult) for x in out)==int(success)
        assert len(authority.registry.entries)==int(success)
        assert len(authority.registry.rejections)==int(not success)

def test_generation_aware_registry_allows_readmission_but_rejects_same_generation(activated):
    first=RuntimeAdmissionAuthority().authorize(bundle(activated));registry=RuntimeAdmissionRegistry().append(first.registry_entry,RuntimeAdmissionRegistry().registry_identity)
    a=first.admission_authorization
    # Registry uniqueness is (runtime instance, generation), not global runtime identity.
    changed=replace(a,handoff_identity="new-handoff",activation_generation=a.activation_generation+1,authorization_identity="")
    changed_executor=replace(first.executor_admission_authorization,
        admission_authorization_identity=changed.authorization_identity,handoff_identity="new-handoff",
        activation_generation=changed.activation_generation,authorization_identity="")
    transitions=[]
    for i,x in enumerate(first.registry_entry.transitions):
        transitions.append(replace(x,handoff_identity="new-handoff",
            previous_transition_identity=None if i==0 else transitions[-1].transition_identity,
            transition_identity=""))
    transitions=tuple(transitions)
    changed_entry=replace(first.registry_entry,admission_authorization=changed,
        executor_admission_authorization=changed_executor,transitions=transitions,sequence=2,
        previous_entry_identity=first.registry_entry.entry_identity,entry_identity="")
    assert len(registry.append(changed_entry,registry.registry_identity).entries)==2
    same_generation=replace(changed,runtime_instance_identity=a.runtime_instance_identity,
        activation_generation=a.activation_generation,authorization_identity="")
    same_executor=replace(changed_executor,admission_authorization_identity=same_generation.authorization_identity,
        activation_generation=a.activation_generation,authorization_identity="")
    replay=replace(changed_entry,admission_authorization=same_generation,
        executor_admission_authorization=same_executor,entry_identity="")
    with pytest.raises(ValueError,match="REPLAY"):registry.append(replay,registry.registry_identity)

def test_serialized_bundle_replay_and_lifecycle_tampering_fail(activated):
    authority=RuntimeAdmissionAuthority();value=bundle(activated);authority.authorize(_roundtrip(value))
    with pytest.raises(RuntimeAdmissionError,match="REGISTRY_CONFLICT"):authority.authorize(_roundtrip(value))
    result=RuntimeAdmissionAuthority().authorize(bundle(activated));transition=result.registry_entry.transitions[1]
    with pytest.raises(ValueError,match="LIFECYCLE"):
        replace(transition,from_state="EXECUTOR_ACKNOWLEDGED",transition_identity="")

def test_prohibited_capabilities_remain_false(activated):
    a=RuntimeAdmissionAuthority().authorize(bundle(activated)).admission_authorization
    assert not any((a.runtime_modification_authorized,a.strategy_generation_authorized,
        a.ai_training_authorized,a.ai_evaluation_authorized))
