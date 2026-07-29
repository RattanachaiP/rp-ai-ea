"""Immutable, fail-closed contracts for candidate qualification (PR273)."""
from __future__ import annotations
from dataclasses import dataclass
from math import isfinite
from typing import Mapping
from learning.common.immutable import freeze, thaw
from .identity import identity_for

QUALIFICATION_SCHEMA_VERSION = "PR273.QUALIFICATION.2.0"
GATES = ("replay_integrity", "performance_threshold", "statistical_confidence", "risk_acceptance",
         "calibration_quality", "governance_compliance", "policy_compliance", "architecture_compatibility")
CRITICAL_GATES = ("replay_integrity", "governance_compliance", "policy_compliance", "architecture_compatibility")
DECISIONS = ("PASS", "FAIL", "CONDITIONAL", "REJECTED")
DOMAINS = ("governance_compliance", "policy_compliance", "architecture_compatibility")
def _text(v): return isinstance(v, str) and bool(v.strip())
def _number(v): return type(v) in (int, float) and isfinite(v)

@dataclass(frozen=True)
class QualificationPolicy:
    policy_reference: str; accepted_evaluation_policy_identities: tuple[str, ...]
    trusted_evidence_issuer_identities: tuple[str, ...]
    require_evaluation_qualified: bool = True; minimum_candidate_score: float = .5
    minimum_records: int = 30; minimum_regime_records: int = 5
    maximum_error_stddev: float = 1.; maximum_mean_squared_error: float = 1.
    maximum_confidence_brier_score: float = .25; minimum_risk_score: float = .5
    minimum_calibration_score: float = .5; conditional_gates: tuple[str, ...] = ()
    schema_version: str = QUALIFICATION_SCHEMA_VERSION; policy_identity: str = ""
    def __post_init__(self):
        accepted, trusted, conditional = (tuple(self.accepted_evaluation_policy_identities),
                                           tuple(self.trusted_evidence_issuer_identities), tuple(self.conditional_gates))
        numbers = (self.minimum_candidate_score, self.maximum_error_stddev, self.maximum_mean_squared_error,
                   self.maximum_confidence_brier_score, self.minimum_risk_score, self.minimum_calibration_score)
        if (not _text(self.policy_reference) or not accepted or len(set(accepted)) != len(accepted) or not all(_text(x) for x in accepted)
                or len(trusted) != len(DOMAINS) or len(set(trusted)) != len(trusted) or not all(_text(x) for x in trusted)
                or type(self.require_evaluation_qualified) is not bool or type(self.minimum_records) is not int or self.minimum_records < 30
                or type(self.minimum_regime_records) is not int or not 2 <= self.minimum_regime_records <= self.minimum_records
                or not all(_number(x) for x in numbers) or not 0 <= self.minimum_candidate_score <= 1
                or self.maximum_error_stddev < 0 or self.maximum_mean_squared_error <= 0
                or not 0 < self.maximum_confidence_brier_score <= 1 or not 0 <= self.minimum_risk_score <= 1
                or not 0 <= self.minimum_calibration_score <= 1 or len(set(conditional)) != len(conditional)
                or any(x not in GATES or x in CRITICAL_GATES for x in conditional) or self.schema_version != QUALIFICATION_SCHEMA_VERSION):
            raise ValueError("QUALIFICATION_POLICY_INVALID")
        object.__setattr__(self, "accepted_evaluation_policy_identities", accepted)
        object.__setattr__(self, "trusted_evidence_issuer_identities", trusted); object.__setattr__(self, "conditional_gates", conditional)
        expected = identity_for("QUALIFICATION_POLICY", self.canonical_payload())
        if self.policy_identity and self.policy_identity != expected: raise ValueError("QUALIFICATION_POLICY_IDENTITY_INVALID")
        object.__setattr__(self, "policy_identity", expected)
    def canonical_payload(self): return {k: getattr(self, k) for k in self.__dataclass_fields__ if k != "policy_identity"}

@dataclass(frozen=True)
class QualificationAttestation:
    domain: str; candidate_identity: str; evaluation_report_identity: str; qualification_policy_identity: str
    compliant: bool; issuer_identity: str; authority_reference: str; attestation_identity: str = ""
    def __post_init__(self):
        if (self.domain not in DOMAINS or not all(_text(getattr(self, x)) for x in ("candidate_identity", "evaluation_report_identity",
                "qualification_policy_identity", "issuer_identity", "authority_reference")) or type(self.compliant) is not bool):
            raise ValueError("QUALIFICATION_ATTESTATION_INVALID")
        expected = identity_for("QUALIFICATION_ATTESTATION", self.canonical_payload())
        if self.attestation_identity and self.attestation_identity != expected: raise ValueError("QUALIFICATION_ATTESTATION_IDENTITY_INVALID")
        object.__setattr__(self, "attestation_identity", expected)
    def canonical_payload(self): return {k: getattr(self, k) for k in self.__dataclass_fields__ if k != "attestation_identity"}

@dataclass(frozen=True)
class QualificationEvidence:
    candidate_identity: str; evaluation_report_identity: str; qualification_policy_identity: str
    attestation_identities: tuple[str, ...]; evidence_registry_identity: str; evidence_identity: str = ""
    def __post_init__(self):
        ids = tuple(self.attestation_identities)
        if (not all(_text(getattr(self, x)) for x in ("candidate_identity", "evaluation_report_identity", "qualification_policy_identity",
                "evidence_registry_identity")) or len(ids) != len(DOMAINS) or len(set(ids)) != len(ids) or not all(_text(x) for x in ids)):
            raise ValueError("QUALIFICATION_EVIDENCE_INVALID")
        object.__setattr__(self, "attestation_identities", ids)
        expected = identity_for("QUALIFICATION_EVIDENCE", self.canonical_payload())
        if self.evidence_identity and self.evidence_identity != expected: raise ValueError("QUALIFICATION_EVIDENCE_IDENTITY_INVALID")
        object.__setattr__(self, "evidence_identity", expected)
    def canonical_payload(self): return {k: getattr(self, k) for k in self.__dataclass_fields__ if k != "evidence_identity"}

@dataclass(frozen=True)
class QualificationGate:
    gate: str; passed: bool; reason: str; evidence: Mapping[str, object]
    def __post_init__(self):
        if (self.gate not in GATES or type(self.passed) is not bool or self.reason != ("GATE_PASSED" if self.passed else "GATE_FAILED")
                or not isinstance(self.evidence, Mapping) or not self.evidence): raise ValueError("QUALIFICATION_GATE_INVALID")
        object.__setattr__(self, "evidence", freeze(dict(self.evidence)))

@dataclass(frozen=True)
class QualificationReport:
    candidate_identity: str; candidate_evidence_identity: str; candidate_registry_identity: str
    evaluation_report_identity: str; evaluation_registry_identity: str; policy: QualificationPolicy
    qualification_evidence: QualificationEvidence; gates: tuple[QualificationGate, ...]
    evaluation_qualified: bool; decision: str; governance_eligible: bool; report_identity: str = ""
    schema_version: str = QUALIFICATION_SCHEMA_VERSION; advisory_only: bool = True
    runtime_authorized: bool = False; strategy_authorized: bool = False; risk_authorized: bool = False
    broker_authorized: bool = False; deployment_authorized: bool = False; promotion_authorized: bool = False; production_authorized: bool = False
    def __post_init__(self):
        gates = tuple(self.gates); QualificationPolicy(**self.policy.__dict__); QualificationEvidence(**self.qualification_evidence.__dict__)
        failed = {x.gate for x in gates if not x.passed}; prerequisite = not self.policy.require_evaluation_qualified or self.evaluation_qualified
        expected = "REJECTED" if not prerequisite else "PASS" if not failed else "CONDITIONAL" if failed <= set(self.policy.conditional_gates) else "FAIL"
        if (not all(_text(getattr(self, x)) for x in ("candidate_identity", "candidate_evidence_identity", "candidate_registry_identity",
                "evaluation_report_identity", "evaluation_registry_identity")) or tuple(x.gate for x in gates) != GATES
                or type(self.evaluation_qualified) is not bool or self.decision != expected or self.decision not in DECISIONS
                or self.governance_eligible != (self.decision == "PASS") or self.schema_version != QUALIFICATION_SCHEMA_VERSION
                or self.advisory_only is not True or any((self.runtime_authorized, self.strategy_authorized, self.risk_authorized,
                self.broker_authorized, self.deployment_authorized, self.promotion_authorized, self.production_authorized))
                or self.qualification_evidence.candidate_identity != self.candidate_identity
                or self.qualification_evidence.evaluation_report_identity != self.evaluation_report_identity
                or self.qualification_evidence.qualification_policy_identity != self.policy.policy_identity): raise ValueError("QUALIFICATION_REPORT_INVALID")
        for x in gates: QualificationGate(x.gate, x.passed, x.reason, thaw(x.evidence))
        object.__setattr__(self, "gates", gates)
        calculated = identity_for("QUALIFICATION_REPORT", self.canonical_payload())
        if self.report_identity and self.report_identity != calculated: raise ValueError("QUALIFICATION_REPORT_IDENTITY_INVALID")
        object.__setattr__(self, "report_identity", calculated)
    def canonical_payload(self):
        return {k: (v.canonical_payload() | {"policy_identity": v.policy_identity} if k == "policy" else
                    v.canonical_payload() | {"evidence_identity": v.evidence_identity} if k == "qualification_evidence" else
                    tuple({"gate": x.gate, "passed": x.passed, "reason": x.reason, "evidence": thaw(x.evidence)} for x in v) if k == "gates" else v)
                for k, v in self.__dict__.items() if k != "report_identity"}
