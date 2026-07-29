"""PR279 executor acknowledgement authority tests."""
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
import pytest

from learning.executor_acknowledgement import (ACKNOWLEDGEMENT_CHECKS,
    AdmissionAuthorizationRevocation,ExecutorAcknowledgementAuthority,
    ExecutorAcknowledgementError,ExecutorAcknowledgementGovernanceBundle,
    ExecutorAcknowledgementRegistry,ExecutorAcknowledgementResult)
from learning.release import ProductionReleaseAuthority,ReleaseRegistry
from learning.runtime_activation import RuntimeActivationAuthority
from learning.runtime_admission import RuntimeAdmissionAuthority,RuntimeAdmissionRegistry
from tests.learning.test_pr275_deployment_governance import promoted as promoted_fixture
from tests.learning.test_pr276_production_release_authority import bundle as release_bundle,context
from tests.learning.test_pr277_runtime_activation_authority import activation_bundle
from tests.learning.test_pr278_runtime_admission_authority import bundle as admission_bundle

@pytest.fixture
def admitted(context):
    decision=ProductionReleaseAuthority().assess(release_bundle(context)); releases=ReleaseRegistry().append(decision)
    chain=decision,releases,releases.entries[0],context["target_runtime_instance"]
    activation_authority=RuntimeActivationAuthority()
    activation=activation_authority.activate(activation_bundle(chain))
    activated=(activation,activation_authority.registry,releases,releases.entries[0])
    admission=RuntimeAdmissionAuthority().authorize(admission_bundle(activated))
    registry=RuntimeAdmissionRegistry().append(admission.registry_entry,RuntimeAdmissionRegistry().registry_identity)
    return admission,registry

def bundle(admitted,registry=None,**changes):
    result,admissions=admitted; acknowledgements=registry or ExecutorAcknowledgementRegistry()
    values=dict(admission_authorization=result.admission_authorization,
        runtime_admission_evidence=result.evidence,
        runtime_instance_identity=result.admission_authorization.runtime_instance_identity,
        executor_identity=result.admission_authorization.executor_identity,
        executor_version=result.admission_authorization.executor_version,
        admission_registry=admissions,acknowledgement_registry=acknowledgements,
        expected_admission_registry_identity=admissions.registry_identity,
        expected_acknowledgement_registry_identity=acknowledgements.registry_identity,
        acknowledged_at="2026-07-29T09:32:30Z")
    values.update(changes); return ExecutorAcknowledgementGovernanceBundle(**values)

def test_acknowledges_once_and_never_executes(admitted):
    result=ExecutorAcknowledgementAuthority().acknowledge(bundle(admitted))
    assert result.acknowledgement.executor_acknowledged and result.readiness_authorization.execution_ready
    assert not any((result.acknowledgement.runtime_started,result.acknowledgement.broker_connected,
        result.acknowledgement.orders_submitted,result.acknowledgement.trades_executed,
        result.readiness_authorization.runtime_modification_authorized,
        result.readiness_authorization.ai_training_authorized))
    assert tuple(x.check for x in result.readiness_evidence.validations)==ACKNOWLEDGEMENT_CHECKS
    assert [x.to_state for x in result.registry_entry.lifecycle]==["ACKNOWLEDGED","RECORDED","READY"]

@pytest.mark.parametrize("change,reason",[
    ({"executor_identity":"wrong"},"EXECUTOR_IDENTITY"),
    ({"executor_version":"wrong"},"EXECUTOR_VERSION"),
    ({"runtime_instance_identity":"wrong"},"RUNTIME_INSTANCE_IDENTITY"),
    ({"acknowledged_at":"2026-07-29T09:34:00Z"},"AUTHORIZATION_VALIDITY_WINDOW")])
def test_mismatch_and_expiry_fail_closed(admitted,change,reason):
    authority=ExecutorAcknowledgementAuthority()
    with pytest.raises(ExecutorAcknowledgementError,match=reason): authority.acknowledge(bundle(admitted,**change))
    assert len(authority.registry.rejections)==1 and not authority.registry.entries

def test_replay_revocation_and_registry_conflict_fail(admitted):
    authority=ExecutorAcknowledgementAuthority(); value=bundle(admitted); authority.acknowledge(value)
    with pytest.raises(ExecutorAcknowledgementError,match="REGISTRY_CONFLICT"): authority.acknowledge(value)
    a=admitted[0].admission_authorization; base=ExecutorAcknowledgementRegistry()
    revoked=base.revoke(AdmissionAuthorizationRevocation(a.authorization_identity,"governance","incident","2026-07-29T09:32:20Z"),base.registry_identity)
    authority=ExecutorAcknowledgementAuthority(revoked)
    with pytest.raises(ExecutorAcknowledgementError,match="REVOCATION_STATUS"):
        authority.acknowledge(bundle(admitted,revoked))

def test_concurrent_acknowledgement_commits_exactly_once(admitted):
    authority=ExecutorAcknowledgementAuthority(); value=bundle(admitted)
    def run():
        try:return authority.acknowledge(value)
        except ExecutorAcknowledgementError as exc:return exc
    with ThreadPoolExecutor(max_workers=2) as pool: results=list(pool.map(lambda _:run(),range(2)))
    assert sum(isinstance(x,ExecutorAcknowledgementResult) for x in results)==1
    assert len(authority.registry.entries)==1

def test_lifecycle_and_generation_tampering_are_rejected(admitted):
    result=ExecutorAcknowledgementAuthority().acknowledge(bundle(admitted))
    with pytest.raises(ValueError,match="EXECUTOR_LIFECYCLE"):
        replace(result.registry_entry.lifecycle[0],from_state="READY",record_identity="")
    evidence=replace(admitted[0].evidence,activation_generation=99,evidence_identity="")
    with pytest.raises(ExecutorAcknowledgementError,match="ACTIVATION_GENERATION"):
        ExecutorAcknowledgementAuthority().acknowledge(bundle(admitted,runtime_admission_evidence=evidence))
