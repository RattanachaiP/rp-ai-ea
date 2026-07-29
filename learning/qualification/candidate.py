"""Immutable contracts for the independent candidate qualification authority (PR273)."""
from __future__ import annotations

from dataclasses import dataclass
from math import isfinite
from typing import Mapping

from learning.common.immutable import freeze, thaw
from .identity import identity_for

QUALIFICATION_SCHEMA_VERSION = "PR273.QUALIFICATION.1.0"
GATES = ("replay_integrity", "performance_threshold", "statistical_confidence",
         "risk_acceptance", "calibration_quality", "governance_compliance",
         "policy_compliance", "architecture_compatibility")
DECISIONS = ("PASS", "FAIL", "CONDITIONAL", "REJECTED")


def _text(value): return isinstance(value, str) and bool(value.strip())
def _number(value): return type(value) in (int, float) and isfinite(value)


@dataclass(frozen=True)
class QualificationPolicy:
    policy_reference: str
    minimum_candidate_score: float = .5
    minimum_records: int = 30
    maximum_error_stddev: float = 1.0
    minimum_risk_score: float = .5
    minimum_calibration_score: float = .5
    accepted_evaluation_policy_identities: tuple[str, ...] = ()
    conditional_gates: tuple[str, ...] = ()
    schema_version: str = QUALIFICATION_SCHEMA_VERSION
    policy_identity: str = ""

    def __post_init__(self):
        accepted, conditional = tuple(self.accepted_evaluation_policy_identities), tuple(self.conditional_gates)
        if (not _text(self.policy_reference) or not all(_number(getattr(self, name)) for name in
                ("minimum_candidate_score", "maximum_error_stddev", "minimum_risk_score", "minimum_calibration_score"))
                or not 0 <= self.minimum_candidate_score <= 1 or self.maximum_error_stddev < 0
                or not 0 <= self.minimum_risk_score <= 1 or not 0 <= self.minimum_calibration_score <= 1
                or type(self.minimum_records) is not int or self.minimum_records < 1
                or len(set(accepted)) != len(accepted) or not all(_text(x) for x in accepted)
                or len(set(conditional)) != len(conditional) or any(x not in GATES for x in conditional)
                or self.schema_version != QUALIFICATION_SCHEMA_VERSION):
            raise ValueError("QUALIFICATION_POLICY_INVALID")
        object.__setattr__(self, "accepted_evaluation_policy_identities", accepted)
        object.__setattr__(self, "conditional_gates", conditional)
        expected = identity_for("QUALIFICATION_POLICY", self.canonical_payload())
        if self.policy_identity and self.policy_identity != expected: raise ValueError("QUALIFICATION_POLICY_IDENTITY_INVALID")
        object.__setattr__(self, "policy_identity", expected)

    def canonical_payload(self): return {k: getattr(self, k) for k in self.__dataclass_fields__ if k != "policy_identity"}


@dataclass(frozen=True)
class QualificationEvidence:
    candidate_identity: str
    evaluation_report_identity: str
    governance_compliant: bool
    policy_compliant: bool
    architecture_compatible: bool
    governance_reference: str
    policy_reference: str
    architecture_reference: str
    evidence_identity: str = ""

    def __post_init__(self):
        if (not all(_text(getattr(self, x)) for x in ("candidate_identity", "evaluation_report_identity",
                "governance_reference", "policy_reference", "architecture_reference"))
                or any(type(getattr(self, x)) is not bool for x in
                       ("governance_compliant", "policy_compliant", "architecture_compatible"))):
            raise ValueError("QUALIFICATION_EVIDENCE_INVALID")
        expected = identity_for("QUALIFICATION_EVIDENCE", self.canonical_payload())
        if self.evidence_identity and self.evidence_identity != expected: raise ValueError("QUALIFICATION_EVIDENCE_IDENTITY_INVALID")
        object.__setattr__(self, "evidence_identity", expected)

    def canonical_payload(self): return {k: getattr(self, k) for k in self.__dataclass_fields__ if k != "evidence_identity"}


@dataclass(frozen=True)
class QualificationGate:
    gate: str; passed: bool; reason: str; evidence: Mapping[str, object]
    def __post_init__(self):
        if self.gate not in GATES or type(self.passed) is not bool or not _text(self.reason):
            raise ValueError("QUALIFICATION_GATE_INVALID")
        object.__setattr__(self, "evidence", freeze(dict(self.evidence)))


@dataclass(frozen=True)
class QualificationReport:
    candidate_identity: str; candidate_registry_identity: str
    evaluation_report_identity: str; evaluation_registry_identity: str
    policy: QualificationPolicy; evidence_identity: str
    gates: tuple[QualificationGate, ...]; evaluation_qualified: bool; decision: str; governance_eligible: bool
    report_identity: str = ""; schema_version: str = QUALIFICATION_SCHEMA_VERSION
    runtime_authorized: bool = False; broker_authorized: bool = False
    deployment_authorized: bool = False; promotion_authorized: bool = False
    production_authorized: bool = False

    def __post_init__(self):
        gates = tuple(self.gates)
        QualificationPolicy(**self.policy.__dict__)
        if (not all(_text(getattr(self, x)) for x in ("candidate_identity", "candidate_registry_identity",
                "evaluation_report_identity", "evaluation_registry_identity", "evidence_identity"))
                or tuple(x.gate for x in gates) != GATES or type(self.evaluation_qualified) is not bool or self.decision not in DECISIONS
                or type(self.governance_eligible) is not bool or self.governance_eligible != (self.decision in ("PASS", "CONDITIONAL"))
                or self.schema_version != QUALIFICATION_SCHEMA_VERSION
                or any((self.runtime_authorized, self.broker_authorized, self.deployment_authorized,
                        self.promotion_authorized, self.production_authorized))):
            raise ValueError("QUALIFICATION_REPORT_INVALID")
        failed = tuple(x.gate for x in gates if not x.passed)
        expected_decision = ("REJECTED" if not self.evaluation_qualified else
                             "PASS" if not failed else
                             "CONDITIONAL" if set(failed) <= set(self.policy.conditional_gates) else "FAIL")
        if self.decision != expected_decision: raise ValueError("QUALIFICATION_DECISION_INVALID")
        for gate in gates: QualificationGate(gate.gate, gate.passed, gate.reason, thaw(gate.evidence))
        object.__setattr__(self, "gates", gates)
        expected = identity_for("QUALIFICATION_REPORT", self.canonical_payload())
        if self.report_identity and self.report_identity != expected: raise ValueError("QUALIFICATION_REPORT_IDENTITY_INVALID")
        object.__setattr__(self, "report_identity", expected)

    def canonical_payload(self):
        return {k: (v.canonical_payload() | {"policy_identity": v.policy_identity} if k == "policy" else
                    tuple({"gate": x.gate, "passed": x.passed, "reason": x.reason, "evidence": thaw(x.evidence)} for x in v)
                    if k == "gates" else v) for k, v in self.__dict__.items() if k != "report_identity"}
