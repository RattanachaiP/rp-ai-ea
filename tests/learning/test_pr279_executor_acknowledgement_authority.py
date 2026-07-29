"""PR279 executor-origin attestation, adversarial, and CAS tests."""
from dataclasses import replace
import pytest

from learning.executor_acknowledgement import (ACKNOWLEDGEMENT_CHECKS,
    ExecutorAcknowledgementAuthority,ExecutorAcknowledgementError,
    ExecutorAcknowledgementGovernanceBundle,ExecutorAcknowledgementRegistry)
from learning.release import ProductionReleaseAuthority,ReleaseRegistry
from learning.runtime_activation import RuntimeActivationAuthority
from learning.runtime_admission import (AdmissionAuthorizationRevocation,
    RuntimeAdmissionAuthority,RuntimeAdmissionRegistry)
from runtime.executor_acceptance import _signature
from runtime.executor import Executor
from tests.learning.test_pr275_deployment_governance import promoted as promoted_fixture
from tests.learning.test_pr276_production_release_authority import bundle as release_bundle,context
from tests.learning.test_pr277_runtime_activation_authority import activation_bundle
from tests.learning.test_pr278_runtime_admission_authority import bundle as admission_bundle

KEY=b"v27-production-executor-attestation-key"
AUTHORITY="executor-acknowledgement-authority"
INSTANCE="v27-production-instance-01"
SESSION="boot-20260729-session-01"
KEY_ID=("V27_PRODUCTION_EXECUTOR","27.1",INSTANCE)

@pytest.fixture
def admitted(context):
    decision=ProductionReleaseAuthority().assess(release_bundle(context));releases=ReleaseRegistry().append(decision)
    activation_authority=RuntimeActivationAuthority()
    activation=activation_authority.activate(activation_bundle((decision,releases,releases.entries[0],context["target_runtime_instance"])))
    activated=(activation,activation_authority.registry,releases,releases.entries[0])
    admission=RuntimeAdmissionAuthority().authorize(admission_bundle(activated))
    registry=RuntimeAdmissionRegistry().append(admission.registry_entry,RuntimeAdmissionRegistry().registry_identity)
    return admission,registry

def authority(registry=None,**changes):
    values=dict(registry=registry,acknowledgement_authority_identity=AUTHORITY,
        trusted_executor_keys={KEY_ID:KEY},expected_executor_instances={KEY_ID:SESSION},
        maximum_attestation_age_seconds=30,maximum_future_skew_seconds=0)
    values.update(changes);return ExecutorAcknowledgementAuthority(**values)

def attestation(admitted,**changes):
    result,_=admitted
    values=dict(executor_admission_authorization=result.executor_admission_authorization,
        admission_registry_entry=result.registry_entry,executor_instance_identity=INSTANCE,
        executor_session_identity=SESSION,acknowledgement_authority_identity=AUTHORITY,
        accepted_at="2026-07-29T09:32:20Z",nonce="nonce-00000001",signing_key=KEY)
    values.update(changes)
    return Executor.attest_admission_acceptance(**values)

def bundle(admitted,acknowledgements=None,attestation_value=None,**changes):
    result,admissions=admitted;acks=acknowledgements or ExecutorAcknowledgementRegistry()
    values=dict(executor_admission_authorization=result.executor_admission_authorization,
        executor_acceptance_attestation=attestation_value or attestation(admitted),
        admission_registry=admissions,admission_registry_entry=result.registry_entry,
        acknowledgement_registry=acks,expected_admission_registry_identity=admissions.registry_identity,
        expected_acknowledgement_registry_identity=acks.registry_identity,
        acknowledged_at="2026-07-29T09:32:30Z")
    values.update(changes);return ExecutorAcknowledgementGovernanceBundle(**values)

def resign(admitted,value,**changes):
    # Simulate a validly signed but semantically false executor statement so PR279 must
    # reject lineage independently of signature verification.
    created=attestation(admitted,**{k:v for k,v in changes.items() if k in {"executor_instance_identity","executor_session_identity","accepted_at","nonce","acknowledgement_authority_identity","signing_key"}})
    remaining={k:v for k,v in changes.items() if k not in {"executor_instance_identity","executor_session_identity","accepted_at","nonce","acknowledgement_authority_identity","signing_key"}}
    changed=replace(created,**remaining,attestation_identity="") if remaining else created
    return replace(changed,signature=_signature(changed.signing_payload(),KEY),attestation_identity="")

def test_authenticates_executor_attestation_and_records_acknowledgement_only(admitted):
    result=authority().acknowledge(bundle(admitted))
    assert result.acknowledgement.executor_admission_acknowledged
    assert result.acknowledgement_authorization.executor_admission_acknowledged
    assert not result.acknowledgement_authorization.operational_execution_ready
    assert not any((result.acknowledgement.runtime_started,result.acknowledgement.broker_connected,
        result.acknowledgement.orders_submitted,result.acknowledgement.trades_executed,
        result.acknowledgement_authorization.runtime_start_authorized,
        result.acknowledgement_authorization.trade_execution_authorized))
    assert tuple(v.check for v in result.acknowledgement_evidence.validations)==ACKNOWLEDGEMENT_CHECKS
    assert [v.to_state for v in result.registry_entry.lifecycle]==["ACKNOWLEDGED","RECORDED","ACKNOWLEDGEMENT_COMPLETE"]

def test_missing_and_forged_attestations_fail(admitted):
    with pytest.raises((AttributeError,TypeError,ValueError)):bundle(admitted,attestation_value=None,executor_acceptance_attestation=None)
    forged=replace(attestation(admitted),artifact_identity="forged-artifact",attestation_identity="")
    with pytest.raises(ExecutorAcknowledgementError,match="ATTESTATION_AUTHENTICITY"):
        authority().acknowledge(bundle(admitted,attestation_value=forged))

@pytest.mark.parametrize("change,reason",[
    ({"executor_instance_identity":"wrong-instance"},"ATTESTATION_AUTHENTICITY"),
    ({"executor_session_identity":"wrong-session"},"EXECUTOR_SESSION_IDENTITY"),
    ({"artifact_identity":"wrong-artifact"},"ARTIFACT_LINEAGE"),
    ({"runtime_contract_identity":"wrong-contract"},"RUNTIME_CONTRACT_LINEAGE"),
    ({"target_environment_identity":"wrong-environment"},"TARGET_ENVIRONMENT_LINEAGE"),
    ({"executor_policy_identity":"wrong-policy"},"EXECUTOR_POLICY_IDENTITY"),
    ({"admission_authorization_identity":"wrong-admission"},"ADMISSION_REGISTRY_MEMBERSHIP"),
    ({"executor_admission_authorization_identity":"wrong-executor-admission"},"ADMISSION_REGISTRY_MEMBERSHIP"),
    ({"acknowledgement_authority_identity":"wrong-authority"},"ACKNOWLEDGEMENT_AUTHORITY_IDENTITY")])
def test_signed_but_wrong_executor_and_lineage_fail(admitted,change,reason):
    value=resign(admitted,attestation(admitted),**change)
    with pytest.raises(ExecutorAcknowledgementError,match=reason):authority().acknowledge(bundle(admitted,attestation_value=value))

@pytest.mark.parametrize("accepted,acknowledged",[
    ("2026-07-29T09:31:59Z","2026-07-29T09:32:30Z"),
    ("2026-07-29T09:32:31Z","2026-07-29T09:32:30Z"),
    ("2026-07-29T09:34:00Z","2026-07-29T09:34:00Z")])
def test_stale_future_and_expired_attestations_fail(admitted,accepted,acknowledged):
    value=attestation(admitted,accepted_at=accepted)
    with pytest.raises(ExecutorAcknowledgementError):authority().acknowledge(bundle(admitted,attestation_value=value,acknowledged_at=acknowledged))

def test_detached_entry_and_upstream_revocation_fail(admitted):
    detached=replace(admitted[0].registry_entry,sequence=2,previous_entry_identity="detached",entry_identity="")
    with pytest.raises(ExecutorAcknowledgementError,match="ADMISSION_REGISTRY_MEMBERSHIP"):
        authority().acknowledge(bundle(admitted,admission_registry_entry=detached))
    admission=admitted[0].admission_authorization;registry=admitted[1]
    revoked=registry.revoke(AdmissionAuthorizationRevocation(admission.authorization_identity,
        "admission-authority","incident","2026-07-29T09:32:25Z"),registry.registry_identity)
    changed=(admitted[0],revoked)
    with pytest.raises(ExecutorAcknowledgementError,match="ADMISSION_EFFECTIVENESS"):
        authority().acknowledge(bundle(changed))

def test_serialized_replay_nonce_replay_and_multi_authority_cas(admitted):
    value=bundle(admitted);first=authority();result=first.acknowledge(value)
    serialized=type(value)(**{k:getattr(value,k) for k in value.__dataclass_fields__})
    second=authority(registry=first.registry)
    with pytest.raises(ExecutorAcknowledgementError,match="ACKNOWLEDGEMENT_REGISTRY_CONFLICT"):
        second.acknowledge(serialized)
    current=bundle(admitted,acknowledgements=first.registry,
        attestation_value=attestation(admitted,nonce="nonce-00000001"))
    with pytest.raises(ExecutorAcknowledgementError,match="ATTESTATION_REPLAY_PROTECTION"):
        second.acknowledge(current)
    assert len(first.registry.entries)==len(second.registry.entries)==1
