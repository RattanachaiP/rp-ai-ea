"""PR276 Production Release Authority governance and fail-closed tests."""
from dataclasses import replace
import hashlib

import pytest

from learning.deployment import DeploymentGovernanceAuthority
from learning.release import (ProductionReleaseAuthority, ProductionReleaseBundle,
                              RELEASE_GATES, ReleasePolicy, ReleaseRegistry)
from tests.learning.test_pr275_deployment_governance import bundle as deployment_bundle
from tests.learning.test_pr275_deployment_governance import promoted as promoted_fixture

_APPROVAL = None


@pytest.fixture(scope="module")
def deployment(promoted_fixture):
    global _APPROVAL
    source = deployment_bundle(promoted_fixture)
    result = DeploymentGovernanceAuthority().assess(source)
    _APPROVAL = source.human_approval_record
    return result


def components(deployment, **changes):
    report = deployment.report
    policy = changes.pop("policy", ReleasePolicy(
        "production-release-v1", deployment.release_request.release_authority_identity,
        (report.deployment_policy_identity,), (report.runtime_contract_identity,),
        "LIVE_PRODUCTION", "MODEL_RELEASE_REVIEWER", "rollback-plan-276",
        hashlib.sha256(b"immutable-rollback-package").hexdigest(),
        "final-governance-certifier-v1"))
    values = {
        "readiness_report": report,
        "deployment_manifest": deployment.manifest,
        "release_request": deployment.release_request,
        "human_approval_record": _APPROVAL,
        "release_policy": policy,
        "assessed_at": "2026-07-29T09:30:00Z",
    }
    values["human_approval_record"] = changes.pop(
        "human_approval_record", values["human_approval_record"])
    values.update(changes)
    return values


def release_bundle(deployment, **changes):
    return ProductionReleaseBundle(**components(deployment, **changes))


def test_exactly_eight_gates_and_only_runtime_activation_is_authorized(deployment):
    bundle = release_bundle(deployment)
    authority = ProductionReleaseAuthority()
    decision = authority.authorize(bundle)
    assert decision.decision == "PRODUCTION_RELEASE_AUTHORIZED"
    assert tuple(gate.gate for gate in decision.evidence.gates) == RELEASE_GATES
    assert authority.replay(decision, bundle)
    assert decision.certificate and decision.release_manifest
    authorization = decision.runtime_activation_authorization
    assert authorization.runtime_activation_authorized is True
    assert not authorization.broker_access_authorized
    assert not authorization.trade_execution_authorized
    assert not any((decision.certificate.broker_access_authorized,
                    decision.certificate.trade_execution_authorized,
                    decision.certificate.deployment_performed,
                    decision.certificate.training_performed,
                    decision.certificate.evaluation_performed,
                    decision.certificate.qualification_performed,
                    decision.certificate.promotion_performed))


def test_manifest_request_and_authority_forgery_fail_closed(deployment):
    manifest = replace(deployment.manifest, runtime_contract_identity="forged-runtime",
                       manifest_identity="")
    rejected = ProductionReleaseAuthority().assess(release_bundle(
        deployment, deployment_manifest=manifest))
    assert rejected.decision == "PRODUCTION_RELEASE_REJECTED"
    policy = components(deployment)["release_policy"]
    wrong = replace(policy, release_authority_identity="attacker", policy_identity="")
    rejected = ProductionReleaseAuthority().assess(release_bundle(deployment, policy=wrong))
    assert rejected.decision == "PRODUCTION_RELEASE_REJECTED"


def test_missing_expired_or_wrong_role_human_approval_fails_closed(deployment):
    with pytest.raises((TypeError, AttributeError, ValueError)):
        release_bundle(deployment, human_approval_record=None)
    approval = components(deployment)["human_approval_record"]
    expired = replace(approval, expires_at="2026-07-29T09:15:00Z", record_identity="")
    rejected = ProductionReleaseAuthority().assess(release_bundle(
        deployment, human_approval_record=expired))
    assert rejected.decision == "PRODUCTION_RELEASE_REJECTED"
    policy = components(deployment)["release_policy"]
    wrong_role = replace(policy, required_approver_role="OTHER_ROLE", policy_identity="")
    rejected = ProductionReleaseAuthority().assess(release_bundle(deployment, policy=wrong_role))
    assert rejected.decision == "PRODUCTION_RELEASE_REJECTED"


def test_runtime_rollback_and_registry_integrity_fail_closed(deployment):
    policy = components(deployment)["release_policy"]
    incompatible = replace(policy, accepted_runtime_contract_identities=("other-runtime",),
                           policy_identity="")
    rejected = ProductionReleaseAuthority().assess(release_bundle(deployment, policy=incompatible))
    assert rejected.decision == "PRODUCTION_RELEASE_REJECTED"
    with pytest.raises(ValueError, match="RELEASE_POLICY_INVALID"):
        replace(policy, rollback_artifact_hash="missing", policy_identity="")
    evidence = deployment.report.deployment_evidence
    registry_gate = next(gate for gate in evidence.gates if gate.gate == "registry_lineage_validation")
    forged_gate = replace(registry_gate, passed=False, reason="GATE_FAILED")
    forged_evidence = replace(evidence, gates=tuple(
        forged_gate if gate.gate == forged_gate.gate else gate for gate in evidence.gates),
        evidence_identity="")
    forged_report = replace(deployment.report, deployment_evidence=forged_evidence,
                            decision="DEPLOYMENT REJECTED", governance_certified=False,
                            release_governance_eligible=False, report_identity="")
    rejected = ProductionReleaseAuthority().assess(release_bundle(
        deployment, readiness_report=forged_report))
    assert rejected.decision == "PRODUCTION_RELEASE_REJECTED"


def test_registry_allows_exactly_one_certificate_per_activation(deployment):
    authority = ProductionReleaseAuthority()
    decision = authority.assess(release_bundle(deployment))
    registry = ReleaseRegistry().append(decision)
    assert registry.append(decision) is registry
    second = authority.assess(release_bundle(deployment, assessed_at="2026-07-29T09:31:00Z"))
    with pytest.raises(ValueError, match="MULTIPLE_RELEASE_CERTIFICATES"):
        registry.append(second)
    rejected = authority.assess(release_bundle(deployment, assessed_at="2026-07-29T10:00:00Z"))
    with pytest.raises(ValueError, match="NOT_REGISTRABLE"):
        ReleaseRegistry().append(rejected)
