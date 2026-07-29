"""PR277 Runtime Activation Authority acceptance and fail-closed tests."""
from dataclasses import replace

import pytest

from learning.release import ActivationRevocation, ProductionReleaseAuthority
from learning.runtime_activation import (ACTIVATION_CHECKS, ACTIVATION_LIFECYCLE,
    ActivationRegistry, RuntimeActivationAuthority, RuntimeActivationError)
from tests.learning.test_pr275_deployment_governance import promoted as promoted_fixture
from tests.learning.test_pr276_production_release_authority import bundle, context


@pytest.fixture
def release(context):
    return ProductionReleaseAuthority().assess(bundle(context))


def test_one_authorization_produces_one_record_and_handoff(release):
    authorization, certificate = (release.runtime_activation_authorization,
                                  release.certificate)
    authority = RuntimeActivationAuthority()
    result = authority.activate(authorization, certificate,
        authorization.runtime_instance_identity, authorization.executor_identity,
        "2026-07-29T09:31:00Z")

    assert tuple(v.check for v in result.evidence.validations) == ACTIVATION_CHECKS
    assert result.evidence.lifecycle == ACTIVATION_LIFECYCLE
    assert result.executor_handoff is result.event
    assert len(authority.registry.entries) == 1
    assert authority.registry.entries[0] == result.registry_entry
    assert not result.event.broker_access_authorized
    assert not result.event.trade_execution_authorized


def test_replay_fails_without_an_extra_record_or_handoff(release):
    authorization, certificate = (release.runtime_activation_authorization,
                                  release.certificate)
    authority = RuntimeActivationAuthority()
    arguments = (authorization, certificate, authorization.runtime_instance_identity,
                 authorization.executor_identity, "2026-07-29T09:31:00Z")
    authority.activate(*arguments)
    with pytest.raises(RuntimeActivationError, match="SINGLE_USE_STATUS"):
        authority.activate(*arguments)
    assert len(authority.registry.entries) == 1


@pytest.mark.parametrize(("field", "value", "failure"), (
    ("runtime", "wrong-runtime", "RUNTIME_INSTANCE_IDENTITY"),
    ("executor", "wrong-executor", "EXECUTOR_IDENTITY"),
    ("time", "2026-07-29T10:00:00Z", "VALIDITY_WINDOW"),
))
def test_identity_and_expiry_fail_closed(release, field, value, failure):
    authorization, certificate = (release.runtime_activation_authorization,
                                  release.certificate)
    runtime = value if field == "runtime" else authorization.runtime_instance_identity
    executor = value if field == "executor" else authorization.executor_identity
    at = value if field == "time" else "2026-07-29T09:31:00Z"
    authority = RuntimeActivationAuthority()
    with pytest.raises(RuntimeActivationError, match=failure):
        authority.activate(authorization, certificate, runtime, executor, at)
    assert not authority.registry.entries


def test_certificate_generation_mismatch_and_revocation_fail_closed(release):
    authorization, certificate = (release.runtime_activation_authorization,
                                  release.certificate)
    mismatched = replace(certificate,
        activation_generation=certificate.activation_generation + 1,
        certificate_identity="")
    with pytest.raises(RuntimeActivationError, match="CERTIFICATE_IDENTITY"):
        RuntimeActivationAuthority().activate(authorization, mismatched,
            authorization.runtime_instance_identity, authorization.executor_identity,
            "2026-07-29T09:31:00Z")

    revocation = ActivationRevocation(authorization.authorization_identity,
        "release-authority", "incident", "2026-07-29T09:30:30Z")
    registry = ActivationRegistry().revoke(revocation)
    authority = RuntimeActivationAuthority(registry)
    with pytest.raises(RuntimeActivationError, match="REVOCATION_STATUS"):
        authority.activate(authorization, certificate,
            authorization.runtime_instance_identity, authorization.executor_identity,
            "2026-07-29T09:31:00Z")
    assert not authority.registry.entries


def test_forged_authorization_and_wrong_input_types_fail_closed(release):
    authorization, certificate = (release.runtime_activation_authorization,
                                  release.certificate)
    object.__setattr__(authorization, "authorization_identity", "forged")
    with pytest.raises(RuntimeActivationError, match="ACTIVATION_INPUT_INVALID"):
        RuntimeActivationAuthority().activate(authorization, certificate,
            authorization.runtime_instance_identity, authorization.executor_identity,
            "2026-07-29T09:31:00Z")
    assert not RuntimeActivationAuthority().registry.entries
