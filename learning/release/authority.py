"""Fail-closed Production Release Authority.

This module certifies governance and emits activation authorization data.  It has
no runtime, broker, strategy, learning, training, or deployment integration.
"""
from learning.deployment.contracts import _revalidate, _utc
from .contracts import (RELEASE_GATES, ProductionReleaseBundle, ReleaseCertificate,
                        ReleaseDecision, ReleaseEvidence, ReleaseGate, ReleaseManifest,
                        RuntimeActivationAuthorization)


class ReleaseValidationError(ValueError):
    pass


class ProductionReleaseAuthority:
    """Issue the sole production runtime activation authorization, or reject."""

    def assess(self, bundle: ProductionReleaseBundle) -> ReleaseDecision:
        try:
            _revalidate(bundle)
        except (AttributeError, TypeError, ValueError) as exc:
            raise ReleaseValidationError("PRODUCTION_RELEASE_INPUT_INVALID") from exc

        report = bundle.readiness_report
        manifest = bundle.deployment_manifest
        request = bundle.release_request
        approval = bundle.human_approval_record
        policy = bundle.release_policy

        readiness_ok = (
            report.decision == "DEPLOYMENT GOVERNANCE ELIGIBLE"
            and report.governance_certified
            and report.release_governance_eligible
            and all(gate.passed for gate in report.deployment_evidence.gates)
            and not any((report.deployment_performed, report.production_released,
                         report.runtime_activated, report.broker_access_authorized,
                         report.trades_executed))
        )
        approval_ok = (
            approval.record_identity == report.approval_record_identity
            and approval.record_identity == request.human_approval_record_identity
            and approval.decision == "APPROVED"
            and approval.candidate_identity == report.candidate_identity
            and approval.required_reviewer_role == policy.required_approver_role
            and _utc(approval.issued_at) <= _utc(bundle.assessed_at) < _utc(approval.expires_at)
        )
        policy_ok = (
            policy.release_authority_identity == manifest.release_authority_identity
            and policy.release_authority_identity == request.release_authority_identity
            and report.deployment_policy_identity in policy.accepted_deployment_policy_identities
        )
        common = ("candidate_identity", "artifact_identity", "promotion_report_identity",
                  "deployment_policy_identity", "target_environment_identity",
                  "runtime_contract_identity")
        manifest_ok = (
            manifest.readiness_report_identity == report.report_identity
            and request.readiness_report_identity == report.report_identity
            and request.manifest_identity == manifest.manifest_identity
            and manifest.approval_record_identity == approval.record_identity
            and all(getattr(manifest, name) == getattr(report, name) for name in common)
            and all(getattr(request, name) == getattr(report, name) for name in common)
            and not manifest.activation_permitted
            and request.status == "PENDING_PRODUCTION_RELEASE_AUTHORITY"
            and not any((request.production_release_authorized,
                         request.runtime_activation_authorized,
                         request.broker_access_authorized,
                         request.trade_execution_authorized))
        )
        artifact_gate = next((gate for gate in report.deployment_evidence.gates
                              if gate.gate == "artifact_integrity"), None)
        artifact_ok = bool(
            artifact_gate and artifact_gate.passed
            and report.artifact_identity == manifest.artifact_identity == request.artifact_identity
            and artifact_gate.evidence.get("artifact_identity") == report.artifact_identity
            and all(artifact_gate.evidence.get(name) for name in (
                "content_hash", "model_hash", "build_provenance_identity"))
        )
        runtime_ok = (
            report.runtime_contract_identity in policy.accepted_runtime_contract_identities
            and report.runtime_contract_identity == manifest.runtime_contract_identity
            and report.runtime_contract_identity == request.runtime_contract_identity
            and report.target_environment_identity == manifest.target_environment_identity
            and report.target_environment_identity == request.target_environment_identity
        )
        rollback_ok = bool(policy.rollback_plan_identity and policy.rollback_artifact_hash)
        registry_gate = next((gate for gate in report.deployment_evidence.gates
                              if gate.gate == "registry_lineage_validation"), None)
        governance_ok = bool(
            readiness_ok and approval_ok and policy_ok and manifest_ok and artifact_ok
            and runtime_ok and rollback_ok and registry_gate and registry_gate.passed
            and registry_gate.evidence.get("promotion_registry_identity")
            and registry_gate.evidence.get("governance_queue_registry_identity")
            and policy.final_governance_authority_identity
        )
        facts = {
            "deployment_readiness": (readiness_ok, {
                "readiness_report_identity": report.report_identity}),
            "human_approval": (approval_ok, {
                "human_approval_record_identity": approval.record_identity,
                "assessed_at": bundle.assessed_at}),
            "release_policy": (policy_ok, {
                "release_policy_identity": policy.policy_identity,
                "release_authority_identity": policy.release_authority_identity}),
            "release_manifest_integrity": (manifest_ok, {
                "deployment_manifest_identity": manifest.manifest_identity,
                "release_request_identity": request.request_identity}),
            "artifact_integrity": (artifact_ok, {
                "artifact_identity": report.artifact_identity,
                "deployment_evidence_identity": report.deployment_evidence.evidence_identity}),
            "runtime_compatibility": (runtime_ok, {
                "runtime_contract_identity": report.runtime_contract_identity,
                "target_environment_identity": report.target_environment_identity}),
            "rollback_readiness": (rollback_ok, {
                "rollback_plan_identity": policy.rollback_plan_identity,
                "rollback_artifact_hash": policy.rollback_artifact_hash}),
            "final_governance_certification": (governance_ok, {
                "final_governance_authority_identity": policy.final_governance_authority_identity,
                "registry_lineage_evidence_present": bool(registry_gate and registry_gate.passed)}),
        }
        gates = tuple(ReleaseGate(name, bool(facts[name][0]),
                                  "GATE_PASSED" if facts[name][0] else "GATE_FAILED",
                                  facts[name][1]) for name in RELEASE_GATES)
        evidence = ReleaseEvidence(bundle.bundle_identity, gates)
        if not all(gate.passed for gate in gates):
            return ReleaseDecision(evidence, "PRODUCTION_RELEASE_REJECTED")

        certificate = ReleaseCertificate(
            request.request_identity, manifest.manifest_identity, report.report_identity,
            report.artifact_identity, report.target_environment_identity,
            report.runtime_contract_identity, policy.policy_identity, approval.record_identity,
            evidence, bundle.assessed_at)
        release_manifest = ReleaseManifest(
            certificate.certificate_identity, request.request_identity, manifest.manifest_identity,
            report.artifact_identity, report.target_environment_identity,
            report.runtime_contract_identity, policy.policy_identity,
            policy.rollback_plan_identity, policy.rollback_artifact_hash)
        authorization = RuntimeActivationAuthorization(
            certificate.certificate_identity, release_manifest.manifest_identity,
            report.runtime_contract_identity, report.target_environment_identity)
        return ReleaseDecision(evidence, "PRODUCTION_RELEASE_AUTHORIZED", certificate,
                               release_manifest, authorization)

    authorize = assess
    certify = assess

    def replay(self, expected, bundle):
        try:
            _revalidate(expected)
            return self.assess(bundle) == expected
        except (ReleaseValidationError, AttributeError, KeyError, TypeError, ValueError):
            return False
