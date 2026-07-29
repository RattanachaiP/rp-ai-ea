"""Immutable and identity-bound contracts for governed promotion eligibility."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping

from learning.common.immutable import freeze, thaw
from .identity import identity_for

PROMOTION_SCHEMA_VERSION = "PR274.PROMOTION.1.0"
PROMOTION_GATES = (
    "qualification_validity", "promotion_policy_compliance", "evidence_completeness",
    "candidate_integrity", "registry_lineage_validation", "governance_readiness",
    "human_review_requirement", "promotion_authorization",
)
PROMOTION_DECISIONS = ("ELIGIBLE", "CONDITIONAL", "REJECTED")
CRITICAL_GATES = frozenset(PROMOTION_GATES[:5])


def _text(value: object) -> bool:
    return isinstance(value, str) and bool(value.strip())


@dataclass(frozen=True)
class PromotionPolicy:
    policy_reference: str
    accepted_qualification_policy_identities: tuple[str, ...]
    conditional_gates: tuple[str, ...] = ()
    require_qualification_pass: bool = True
    require_governance_eligible: bool = True
    require_human_review: bool = True
    schema_version: str = PROMOTION_SCHEMA_VERSION
    policy_identity: str = ""

    def __post_init__(self) -> None:
        accepted, conditional = (tuple(self.accepted_qualification_policy_identities),
                                 tuple(self.conditional_gates))
        if (not _text(self.policy_reference) or not accepted or len(set(accepted)) != len(accepted)
                or not all(_text(x) for x in accepted) or len(set(conditional)) != len(conditional)
                or any(x not in PROMOTION_GATES or x in CRITICAL_GATES for x in conditional)
                or any(type(x) is not bool for x in (self.require_qualification_pass,
                    self.require_governance_eligible, self.require_human_review))
                or self.require_human_review is not True or self.schema_version != PROMOTION_SCHEMA_VERSION):
            raise ValueError("PROMOTION_POLICY_INVALID")
        object.__setattr__(self, "accepted_qualification_policy_identities", accepted)
        object.__setattr__(self, "conditional_gates", conditional)
        expected = identity_for("PROMOTION_POLICY", self.canonical_payload())
        if self.policy_identity and self.policy_identity != expected:
            raise ValueError("PROMOTION_POLICY_IDENTITY_INVALID")
        object.__setattr__(self, "policy_identity", expected)

    def canonical_payload(self) -> dict[str, object]:
        return {x: getattr(self, x) for x in self.__dataclass_fields__ if x != "policy_identity"}


@dataclass(frozen=True)
class PromotionGate:
    gate: str
    passed: bool
    reason: str
    evidence: Mapping[str, object]

    def __post_init__(self) -> None:
        if (self.gate not in PROMOTION_GATES or type(self.passed) is not bool
                or self.reason != ("GATE_PASSED" if self.passed else "GATE_FAILED")
                or not isinstance(self.evidence, Mapping) or not self.evidence):
            raise ValueError("PROMOTION_GATE_INVALID")
        object.__setattr__(self, "evidence", freeze(dict(self.evidence)))


@dataclass(frozen=True)
class PromotionEvidence:
    candidate_identity: str
    qualification_report_identity: str
    qualification_evidence_identity: str
    qualification_registry_identity: str
    promotion_policy_identity: str
    gates: tuple[PromotionGate, ...]
    evidence_identity: str = ""

    def __post_init__(self) -> None:
        gates = tuple(self.gates)
        if (not all(_text(getattr(self, x)) for x in ("candidate_identity",
                "qualification_report_identity", "qualification_evidence_identity",
                "qualification_registry_identity", "promotion_policy_identity"))
                or tuple(x.gate for x in gates) != PROMOTION_GATES):
            raise ValueError("PROMOTION_EVIDENCE_INVALID")
        for gate in gates:
            PromotionGate(gate.gate, gate.passed, gate.reason, thaw(gate.evidence))
        object.__setattr__(self, "gates", gates)
        expected = identity_for("PROMOTION_EVIDENCE", self.canonical_payload())
        if self.evidence_identity and self.evidence_identity != expected:
            raise ValueError("PROMOTION_EVIDENCE_IDENTITY_INVALID")
        object.__setattr__(self, "evidence_identity", expected)

    def canonical_payload(self) -> dict[str, object]:
        return {"candidate_identity": self.candidate_identity,
                "qualification_report_identity": self.qualification_report_identity,
                "qualification_evidence_identity": self.qualification_evidence_identity,
                "qualification_registry_identity": self.qualification_registry_identity,
                "promotion_policy_identity": self.promotion_policy_identity,
                "gates": tuple({"gate": x.gate, "passed": x.passed, "reason": x.reason,
                                "evidence": thaw(x.evidence)} for x in self.gates)}


@dataclass(frozen=True)
class PromotionReport:
    candidate_identity: str
    qualification_report_identity: str
    qualification_registry_identity: str
    policy: PromotionPolicy
    promotion_evidence: PromotionEvidence
    decision: str
    governance_queue_eligible: bool
    report_identity: str = ""
    schema_version: str = PROMOTION_SCHEMA_VERSION
    advisory_only: bool = True
    human_approval_required: bool = True
    human_approved: bool = False
    deployment_authorized: bool = False
    production_authorized: bool = False
    runtime_authorized: bool = False
    broker_authorized: bool = False

    def __post_init__(self) -> None:
        PromotionPolicy(**self.policy.__dict__)
        PromotionEvidence(**self.promotion_evidence.__dict__)
        failed = {x.gate for x in self.promotion_evidence.gates if not x.passed}
        expected = ("ELIGIBLE" if not failed else "CONDITIONAL"
                    if failed <= set(self.policy.conditional_gates) else "REJECTED")
        if (not _text(self.candidate_identity) or not _text(self.qualification_report_identity)
                or not _text(self.qualification_registry_identity) or self.decision != expected
                or self.decision not in PROMOTION_DECISIONS
                or self.governance_queue_eligible != (self.decision in ("ELIGIBLE", "CONDITIONAL"))
                or self.schema_version != PROMOTION_SCHEMA_VERSION or self.advisory_only is not True
                or self.human_approval_required is not True or self.human_approved is not False
                or any((self.deployment_authorized, self.production_authorized,
                        self.runtime_authorized, self.broker_authorized))
                or self.promotion_evidence.candidate_identity != self.candidate_identity
                or self.promotion_evidence.qualification_report_identity != self.qualification_report_identity
                or self.promotion_evidence.qualification_registry_identity != self.qualification_registry_identity
                or self.promotion_evidence.promotion_policy_identity != self.policy.policy_identity):
            raise ValueError("PROMOTION_REPORT_INVALID")
        expected_identity = identity_for("PROMOTION_REPORT", self.canonical_payload())
        if self.report_identity and self.report_identity != expected_identity:
            raise ValueError("PROMOTION_REPORT_IDENTITY_INVALID")
        object.__setattr__(self, "report_identity", expected_identity)

    def canonical_payload(self) -> dict[str, object]:
        return {x: (self.policy.canonical_payload() | {"policy_identity": self.policy.policy_identity}
                    if x == "policy" else self.promotion_evidence.canonical_payload() |
                    {"evidence_identity": self.promotion_evidence.evidence_identity}
                    if x == "promotion_evidence" else getattr(self, x))
                for x in self.__dataclass_fields__ if x != "report_identity"}


@dataclass(frozen=True)
class PromotionApprovalRequest:
    report_identity: str
    candidate_identity: str
    promotion_policy_identity: str
    requested_action: str = "HUMAN_REVIEW_FOR_DEPLOYMENT_GOVERNANCE"
    status: str = "PENDING"
    request_identity: str = ""

    def __post_init__(self) -> None:
        if (not all(_text(getattr(self, x)) for x in ("report_identity", "candidate_identity",
                "promotion_policy_identity")) or self.requested_action != "HUMAN_REVIEW_FOR_DEPLOYMENT_GOVERNANCE"
                or self.status != "PENDING"):
            raise ValueError("PROMOTION_APPROVAL_REQUEST_INVALID")
        expected = identity_for("PROMOTION_APPROVAL_REQUEST", self.canonical_payload())
        if self.request_identity and self.request_identity != expected:
            raise ValueError("PROMOTION_APPROVAL_REQUEST_IDENTITY_INVALID")
        object.__setattr__(self, "request_identity", expected)

    def canonical_payload(self) -> dict[str, object]:
        return {x: getattr(self, x) for x in self.__dataclass_fields__ if x != "request_identity"}


@dataclass(frozen=True)
class GovernanceQueueEntry:
    report_identity: str
    approval_request_identity: str
    candidate_identity: str
    decision: str
    queue_status: str = "AWAITING_HUMAN_REVIEW"
    queue_identity: str = ""

    def __post_init__(self) -> None:
        if (not all(_text(getattr(self, x)) for x in ("report_identity",
                "approval_request_identity", "candidate_identity"))
                or self.decision not in ("ELIGIBLE", "CONDITIONAL")
                or self.queue_status != "AWAITING_HUMAN_REVIEW"):
            raise ValueError("PROMOTION_GOVERNANCE_QUEUE_ENTRY_INVALID")
        expected = identity_for("PROMOTION_GOVERNANCE_QUEUE_ENTRY", self.canonical_payload())
        if self.queue_identity and self.queue_identity != expected:
            raise ValueError("PROMOTION_GOVERNANCE_QUEUE_ENTRY_IDENTITY_INVALID")
        object.__setattr__(self, "queue_identity", expected)

    def canonical_payload(self) -> dict[str, object]:
        return {x: getattr(self, x) for x in self.__dataclass_fields__ if x != "queue_identity"}


@dataclass(frozen=True)
class PromotionResult:
    report: PromotionReport
    approval_request: PromotionApprovalRequest | None
    governance_queue_entry: GovernanceQueueEntry | None

    def __post_init__(self) -> None:
        PromotionReport(**self.report.__dict__)
        eligible = self.report.governance_queue_eligible
        if eligible != (self.approval_request is not None and self.governance_queue_entry is not None):
            raise ValueError("PROMOTION_RESULT_INVALID")
        if eligible:
            PromotionApprovalRequest(**self.approval_request.__dict__)
            GovernanceQueueEntry(**self.governance_queue_entry.__dict__)
            if (self.approval_request.report_identity != self.report.report_identity
                    or self.governance_queue_entry.report_identity != self.report.report_identity
                    or self.governance_queue_entry.approval_request_identity != self.approval_request.request_identity):
                raise ValueError("PROMOTION_RESULT_BINDING_INVALID")
