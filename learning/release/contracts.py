"""Immutable contracts for the Production Release Authority boundary."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping

from learning.common.immutable import freeze, thaw
from learning.deployment import (DeploymentManifest, DeploymentReadinessReport,
                                 HumanApprovalRecord, ReleaseRequest)
from learning.deployment.contracts import _hash, _revalidate, _text, _utc
from learning.promotion.identity import identity_for

RELEASE_SCHEMA_VERSION = "PR276.RELEASE.1.0"
RELEASE_GATES = (
    "deployment_readiness", "human_approval", "release_policy",
    "release_manifest_integrity", "artifact_integrity", "runtime_compatibility",
    "rollback_readiness", "final_governance_certification",
)


@dataclass(frozen=True)
class ReleasePolicy:
    policy_reference: str
    release_authority_identity: str
    accepted_deployment_policy_identities: tuple[str, ...]
    accepted_runtime_contract_identities: tuple[str, ...]
    required_environment_class: str
    required_approver_role: str
    rollback_plan_identity: str
    rollback_artifact_hash: str
    final_governance_authority_identity: str
    policy_identity: str = ""
    schema_version: str = RELEASE_SCHEMA_VERSION

    def __post_init__(self):
        deployment = tuple(self.accepted_deployment_policy_identities)
        runtimes = tuple(self.accepted_runtime_contract_identities)
        if (not all(_text(getattr(self, name)) for name in (
                "policy_reference", "release_authority_identity", "required_approver_role",
                "rollback_plan_identity", "final_governance_authority_identity"))
                or self.required_environment_class != "LIVE_PRODUCTION"
                or not deployment or len(set(deployment)) != len(deployment)
                or not runtimes or len(set(runtimes)) != len(runtimes)
                or not all(_text(value) for value in deployment + runtimes)
                or not _hash(self.rollback_artifact_hash)
                or self.schema_version != RELEASE_SCHEMA_VERSION):
            raise ValueError("RELEASE_POLICY_INVALID")
        object.__setattr__(self, "accepted_deployment_policy_identities", deployment)
        object.__setattr__(self, "accepted_runtime_contract_identities", runtimes)
        expected = identity_for("RELEASE_POLICY", self.canonical_payload())
        if self.policy_identity and self.policy_identity != expected:
            raise ValueError("RELEASE_POLICY_IDENTITY_INVALID")
        object.__setattr__(self, "policy_identity", expected)

    def canonical_payload(self):
        return {name: getattr(self, name) for name in self.__dataclass_fields__
                if name != "policy_identity"}


@dataclass(frozen=True)
class ProductionReleaseBundle:
    """The complete and exclusive set of release-governance inputs."""
    readiness_report: DeploymentReadinessReport
    deployment_manifest: DeploymentManifest
    release_request: ReleaseRequest
    human_approval_record: HumanApprovalRecord
    release_policy: ReleasePolicy
    assessed_at: str
    bundle_identity: str = ""

    def __post_init__(self):
        for value in (self.readiness_report, self.deployment_manifest, self.release_request,
                      self.human_approval_record, self.release_policy):
            _revalidate(value)
        _utc(self.assessed_at)
        expected = identity_for("PRODUCTION_RELEASE_BUNDLE", self.canonical_payload())
        if self.bundle_identity and self.bundle_identity != expected:
            raise ValueError("PRODUCTION_RELEASE_BUNDLE_IDENTITY_INVALID")
        object.__setattr__(self, "bundle_identity", expected)

    def canonical_payload(self):
        return {
            "readiness_report_identity": self.readiness_report.report_identity,
            "deployment_manifest_identity": self.deployment_manifest.manifest_identity,
            "release_request_identity": self.release_request.request_identity,
            "human_approval_record_identity": self.human_approval_record.record_identity,
            "release_policy_identity": self.release_policy.policy_identity,
            "assessed_at": self.assessed_at,
        }


@dataclass(frozen=True)
class ReleaseGate:
    gate: str
    passed: bool
    reason: str
    evidence: Mapping[str, object]

    def __post_init__(self):
        if (self.gate not in RELEASE_GATES or type(self.passed) is not bool
                or self.reason != ("GATE_PASSED" if self.passed else "GATE_FAILED")
                or not isinstance(self.evidence, Mapping) or not self.evidence):
            raise ValueError("RELEASE_GATE_INVALID")
        object.__setattr__(self, "evidence", freeze(dict(self.evidence)))


@dataclass(frozen=True)
class ReleaseEvidence:
    bundle_identity: str
    gates: tuple[ReleaseGate, ...]
    evidence_identity: str = ""

    def __post_init__(self):
        gates = tuple(self.gates)
        if not _text(self.bundle_identity) or tuple(gate.gate for gate in gates) != RELEASE_GATES:
            raise ValueError("RELEASE_EVIDENCE_INVALID")
        for gate in gates:
            ReleaseGate(gate.gate, gate.passed, gate.reason, thaw(gate.evidence))
        object.__setattr__(self, "gates", gates)
        expected = identity_for("RELEASE_EVIDENCE", self.canonical_payload())
        if self.evidence_identity and self.evidence_identity != expected:
            raise ValueError("RELEASE_EVIDENCE_IDENTITY_INVALID")
        object.__setattr__(self, "evidence_identity", expected)

    def canonical_payload(self):
        return {"bundle_identity": self.bundle_identity, "gates": tuple({
            "gate": gate.gate, "passed": gate.passed, "reason": gate.reason,
            "evidence": thaw(gate.evidence)} for gate in self.gates)}


@dataclass(frozen=True)
class ReleaseCertificate:
    release_request_identity: str
    deployment_manifest_identity: str
    readiness_report_identity: str
    artifact_identity: str
    target_environment_identity: str
    runtime_contract_identity: str
    release_policy_identity: str
    human_approval_record_identity: str
    release_evidence: ReleaseEvidence
    issued_at: str
    decision: str = "PRODUCTION_RELEASE_AUTHORIZED"
    runtime_activation_authorized: bool = True
    certificate_identity: str = ""
    broker_access_authorized: bool = False
    trade_execution_authorized: bool = False
    deployment_performed: bool = False
    training_performed: bool = False
    evaluation_performed: bool = False
    qualification_performed: bool = False
    promotion_performed: bool = False

    def __post_init__(self):
        _revalidate(self.release_evidence)
        _utc(self.issued_at)
        excluded = {"release_evidence", "runtime_activation_authorized", "certificate_identity",
                    "broker_access_authorized", "trade_execution_authorized", "deployment_performed",
                    "training_performed", "evaluation_performed", "qualification_performed",
                    "promotion_performed"}
        if (not all(_text(getattr(self, name)) for name in self.__dataclass_fields__ if name not in excluded)
                or self.decision != "PRODUCTION_RELEASE_AUTHORIZED"
                or self.runtime_activation_authorized is not True
                or not all(gate.passed for gate in self.release_evidence.gates)
                or any((self.broker_access_authorized, self.trade_execution_authorized,
                        self.deployment_performed, self.training_performed,
                        self.evaluation_performed, self.qualification_performed,
                        self.promotion_performed))):
            raise ValueError("RELEASE_CERTIFICATE_INVALID")
        expected = identity_for("RELEASE_CERTIFICATE", self.canonical_payload())
        if self.certificate_identity and self.certificate_identity != expected:
            raise ValueError("RELEASE_CERTIFICATE_IDENTITY_INVALID")
        object.__setattr__(self, "certificate_identity", expected)

    def canonical_payload(self):
        return {name: (self.release_evidence.evidence_identity if name == "release_evidence"
                       else getattr(self, name)) for name in self.__dataclass_fields__
                if name != "certificate_identity"}


@dataclass(frozen=True)
class ReleaseManifest:
    certificate_identity: str
    release_request_identity: str
    deployment_manifest_identity: str
    artifact_identity: str
    target_environment_identity: str
    runtime_contract_identity: str
    release_policy_identity: str
    rollback_plan_identity: str
    rollback_artifact_hash: str
    manifest_identity: str = ""

    def __post_init__(self):
        if (not all(_text(getattr(self, name)) for name in self.__dataclass_fields__
                    if name not in ("manifest_identity", "rollback_artifact_hash"))
                or not _hash(self.rollback_artifact_hash)):
            raise ValueError("RELEASE_MANIFEST_INVALID")
        expected = identity_for("RELEASE_MANIFEST", self.canonical_payload())
        if self.manifest_identity and self.manifest_identity != expected:
            raise ValueError("RELEASE_MANIFEST_IDENTITY_INVALID")
        object.__setattr__(self, "manifest_identity", expected)

    def canonical_payload(self):
        return {name: getattr(self, name) for name in self.__dataclass_fields__
                if name != "manifest_identity"}


@dataclass(frozen=True)
class RuntimeActivationAuthorization:
    certificate_identity: str
    release_manifest_identity: str
    runtime_contract_identity: str
    target_environment_identity: str
    runtime_activation_authorized: bool = True
    authorization_identity: str = ""
    broker_access_authorized: bool = False
    trade_execution_authorized: bool = False

    def __post_init__(self):
        if (not all(_text(getattr(self, name)) for name in (
                "certificate_identity", "release_manifest_identity", "runtime_contract_identity",
                "target_environment_identity")) or self.runtime_activation_authorized is not True
                or self.broker_access_authorized is not False
                or self.trade_execution_authorized is not False):
            raise ValueError("RUNTIME_ACTIVATION_AUTHORIZATION_INVALID")
        expected = identity_for("RUNTIME_ACTIVATION_AUTHORIZATION", self.canonical_payload())
        if self.authorization_identity and self.authorization_identity != expected:
            raise ValueError("RUNTIME_ACTIVATION_AUTHORIZATION_IDENTITY_INVALID")
        object.__setattr__(self, "authorization_identity", expected)

    def canonical_payload(self):
        return {name: getattr(self, name) for name in self.__dataclass_fields__
                if name != "authorization_identity"}


@dataclass(frozen=True)
class ReleaseDecision:
    evidence: ReleaseEvidence
    decision: str
    certificate: ReleaseCertificate | None = None
    release_manifest: ReleaseManifest | None = None
    runtime_activation_authorization: RuntimeActivationAuthorization | None = None
    decision_identity: str = ""

    def __post_init__(self):
        _revalidate(self.evidence)
        approved = all(gate.passed for gate in self.evidence.gates)
        outputs = (self.certificate, self.release_manifest, self.runtime_activation_authorization)
        if self.decision != ("PRODUCTION_RELEASE_AUTHORIZED" if approved else "PRODUCTION_RELEASE_REJECTED"):
            raise ValueError("RELEASE_DECISION_INVALID")
        if approved != all(value is not None for value in outputs) or (not approved and any(value is not None for value in outputs)):
            raise ValueError("RELEASE_DECISION_OUTPUT_INVALID")
        if approved:
            for value in outputs:
                _revalidate(value)
            certificate, manifest, authorization = outputs
            if (manifest.certificate_identity != certificate.certificate_identity
                    or authorization.certificate_identity != certificate.certificate_identity
                    or authorization.release_manifest_identity != manifest.manifest_identity):
                raise ValueError("RELEASE_DECISION_BINDING_INVALID")
        expected = identity_for("RELEASE_DECISION", self.canonical_payload())
        if self.decision_identity and self.decision_identity != expected:
            raise ValueError("RELEASE_DECISION_IDENTITY_INVALID")
        object.__setattr__(self, "decision_identity", expected)

    def canonical_payload(self):
        return {"evidence_identity": self.evidence.evidence_identity, "decision": self.decision,
                "certificate_identity": None if self.certificate is None else self.certificate.certificate_identity,
                "release_manifest_identity": None if self.release_manifest is None else self.release_manifest.manifest_identity,
                "authorization_identity": None if self.runtime_activation_authorization is None else self.runtime_activation_authorization.authorization_identity}
