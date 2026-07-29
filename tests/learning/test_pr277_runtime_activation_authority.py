"""PR277 authoritative-chain, atomicity, and adversarial tests."""
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
import pytest
from learning.release import (ActivationRevocation,EmergencyRollbackAuthorization,
    ProductionReleaseAuthority,ReleaseCertificateRevocation,ReleaseRegistry)
from learning.runtime_activation import (ActivationRegistry,ActivationResult,
    RuntimeActivationAuthority,RuntimeActivationError,RuntimeActivationGovernanceBundle)
from tests.learning.test_pr275_deployment_governance import promoted as promoted_fixture
from tests.learning.test_pr276_production_release_authority import bundle as release_bundle,context

@pytest.fixture
def chain(context):
    decision=ProductionReleaseAuthority().assess(release_bundle(context))
    releases=ReleaseRegistry().append(decision)
    return decision,releases,releases.entries[0],context["target_runtime_instance"]

def activation_bundle(chain,activation_registry=None,release_registry=None,**changes):
    decision,releases,entry,runtime=chain
    registry=activation_registry or ActivationRegistry()
    values=dict(release_decision=decision,release_certificate=decision.certificate,
        release_manifest=decision.release_manifest,authorization=decision.runtime_activation_authorization,
        release_registry=release_registry or releases,release_registry_entry=entry,
        target_runtime=runtime,activation_registry=registry,
        expected_registry_identity=registry.registry_identity,activated_at="2026-07-29T09:31:00Z")
    values.update(changes);return RuntimeActivationGovernanceBundle(**values)

def test_authoritative_chain_emits_one_bound_data_only_handoff(chain):
    authority=RuntimeActivationAuthority(); result=authority.activate(activation_bundle(chain))
    handoff=result.executor_handoff; authorization=result.consumed_authorization.authorization
    assert handoff.authorization_identity==authorization.authorization_identity
    assert handoff.release_registry_entry_identity==chain[2].entry_identity
    assert result.event.handoff_identity==handoff.handoff_identity
    assert [x.to_state for x in result.registry_entry.transitions]==["VALIDATED","CONSUMED","RECORDED","HANDOFF","EXECUTOR"]
    assert not handoff.broker_access_authorized and not handoff.trade_execution_authorized

def test_unregistered_release_and_all_pr276_revocations_fail_closed(chain):
    decision,releases,entry,_=chain
    variants=[ReleaseRegistry(),
      releases.revoke_certificate(ReleaseCertificateRevocation(decision.certificate.certificate_identity,"authority","incident","2026-07-29T09:30:00Z")),
      releases.revoke_activation(ActivationRevocation(decision.runtime_activation_authorization.authorization_identity,"authority","incident","2026-07-29T09:30:00Z")),
      releases.authorize_rollback(EmergencyRollbackAuthorization(decision.certificate.certificate_identity,decision.certificate.rollback_manifest_identity,decision.certificate.runtime_instance_identity,"authority","incident","2026-07-29T09:30:00Z"))]
    for registry in variants:
        authority=RuntimeActivationAuthority()
        with pytest.raises(RuntimeActivationError) as error:
            authority.activate(activation_bundle(chain,release_registry=registry))
        assert error.value.evidence is not None and len(authority.registry.rejections)==1
        assert not authority.registry.entries

@pytest.mark.parametrize(("field","value","check"),(
 ("executor_version","wrong","EXECUTOR_VERSION"),("runtime_contract_identity","wrong","RUNTIME_CONTRACT_IDENTITY"),
 ("target_environment_identity","wrong","TARGET_ENVIRONMENT_IDENTITY"),("runtime_instance_reference","wrong","RUNTIME_INSTANCE_IDENTITY"),
 ("activation_generation",99,"ACTIVATION_GENERATION")))
def test_actual_runtime_consumer_identity_is_fully_validated(chain,field,value,check):
    runtime=replace(chain[3],**{field:value},instance_identity="")
    authority=RuntimeActivationAuthority()
    with pytest.raises(RuntimeActivationError) as error: authority.activate(activation_bundle(chain,target_runtime=runtime))
    assert not next(x for x in error.value.evidence.validations if x.check==check.lower()).passed
    assert len(authority.registry.rejections)==1

def test_wrong_artifact_expiry_and_release_manifest_fail_closed(chain):
    decision=chain[0]
    cases=[{"authorization":replace(decision.runtime_activation_authorization,artifact_identity="wrong",authorization_identity="")},
           {"activated_at":"2026-07-29T10:00:00Z"},
           {"release_manifest":replace(decision.release_manifest,artifact_identity="wrong",manifest_identity="")}]
    for change in cases:
        authority=RuntimeActivationAuthority()
        with pytest.raises(RuntimeActivationError): authority.activate(activation_bundle(chain,**change))
        assert authority.registry.rejections and not authority.registry.entries

def test_concurrent_double_activation_has_one_transactional_commit(chain):
    authority=RuntimeActivationAuthority(); value=activation_bundle(chain)
    def activate():
        try:return authority.activate(value)
        except RuntimeActivationError as exc:return exc
    with ThreadPoolExecutor(max_workers=2) as pool: outcomes=list(pool.map(lambda _:activate(),range(2)))
    assert sum(isinstance(x,ActivationResult) for x in outcomes)==1
    assert len(authority.registry.entries)==1

def test_stale_snapshot_and_expected_identity_conflicts_do_not_mutate(chain):
    authority=RuntimeActivationAuthority(); stale=activation_bundle(chain)
    authority.activate(stale)
    with pytest.raises(RuntimeActivationError,match="REGISTRY_CONFLICT"): authority.activate(stale)
    current=authority.registry
    conflict=activation_bundle(chain,activation_registry=current,expected_registry_identity="stale")
    with pytest.raises(RuntimeActivationError,match="REGISTRY_CONFLICT"): authority.activate(conflict)
    assert authority.registry.registry_identity==current.registry_identity

def test_failed_attempt_evidence_is_deterministic_and_does_not_consume(chain):
    a1=RuntimeActivationAuthority(); bad=activation_bundle(chain,activated_at="2026-07-29T10:00:00Z")
    with pytest.raises(RuntimeActivationError) as e1:a1.activate(bad)
    a2=RuntimeActivationAuthority()
    with pytest.raises(RuntimeActivationError) as e2:a2.activate(bad)
    assert e1.value.evidence.evidence_identity==e2.value.evidence.evidence_identity
    assert not a1.registry.entries and len(a1.registry.rejections)==1

def test_revocation_requires_known_authorization_and_handoff_uses_identity_binding(chain):
    registry=ActivationRegistry(); unknown=ActivationRevocation("unknown","authority","incident","2026-07-29T09:30:00Z")
    with pytest.raises(ValueError,match="UNKNOWN"): registry.revoke(unknown,chain[1],registry.registry_identity)
    result=RuntimeActivationAuthority().activate(activation_bundle(chain))
    serialized=type(result.executor_handoff)(**{x:getattr(result.executor_handoff,x) for x in result.executor_handoff.__dataclass_fields__})
    assert serialized is not result.executor_handoff and serialized.handoff_identity==result.event.handoff_identity
    forged=replace(serialized,executor_identity="wrong",handoff_identity="")
    with pytest.raises(ValueError,match="BINDING"): replace(result,executor_handoff=forged)
