"""Pure promotion authority consuming only qualification artifacts and policy."""
from __future__ import annotations

from .contracts import (PROMOTION_GATES, GovernanceQueueEntry, PromotionApprovalRequest,
                        PromotionEvidence, PromotionGate, PromotionPolicy, PromotionReport,
                        PromotionResult)


class PromotionValidationError(ValueError):
    """A malformed input crossed the promotion trust boundary."""


def _validate(value: object) -> None:
    try:
        type(value)(**value.__dict__)
    except (AttributeError, TypeError, ValueError) as exc:
        raise PromotionValidationError("PROMOTION_INPUT_INVALID") from exc


class PromotionAuthority:
    """Authorize governance eligibility; never deploy, approve, or modify runtime."""

    def __init__(self, policy: PromotionPolicy) -> None:
        _validate(policy)
        self.policy = policy

    def assess(self, qualification_registry, qualification_report,
               qualification_evidence) -> PromotionResult:
        for value in (qualification_registry, qualification_report, qualification_evidence):
            _validate(value)

        entries = tuple(x for x in qualification_registry.entries
                        if x.report.report_identity == qualification_report.report_identity)
        unique_entry = len(entries) == 1 and entries[0].report == qualification_report
        evidence_bound = (qualification_report.qualification_evidence == qualification_evidence
                          and qualification_evidence.evidence_identity ==
                          qualification_report.qualification_evidence.evidence_identity)
        policy_accepted = qualification_report.policy.policy_identity in self.policy.accepted_qualification_policy_identities
        qualification_valid = (qualification_report.decision == "PASS"
            if self.policy.require_qualification_pass else qualification_report.decision in ("PASS", "CONDITIONAL"))
        governance_ready = (qualification_report.governance_eligible
                            if self.policy.require_governance_eligible else True)
        candidate_integrity = (qualification_report.candidate_identity == qualification_evidence.candidate_identity
            and qualification_report.evaluation_report_identity == qualification_evidence.evaluation_report_identity
            and qualification_report.policy.policy_identity == qualification_evidence.qualification_policy_identity)
        lineage_valid = (unique_entry and qualification_report.candidate_registry_identity
                         and qualification_report.evaluation_registry_identity
                         and qualification_registry.registry_identity != "")
        facts = {
            "qualification_validity": (qualification_valid,
                {"qualification_decision": qualification_report.decision,
                 "qualification_report_identity": qualification_report.report_identity}),
            "promotion_policy_compliance": (policy_accepted,
                {"qualification_policy_identity": qualification_report.policy.policy_identity,
                 "promotion_policy_identity": self.policy.policy_identity}),
            "evidence_completeness": (evidence_bound,
                {"qualification_evidence_identity": qualification_evidence.evidence_identity,
                 "report_evidence_identity": qualification_report.qualification_evidence.evidence_identity}),
            "candidate_integrity": (candidate_integrity,
                {"candidate_identity": qualification_report.candidate_identity,
                 "evidence_candidate_identity": qualification_evidence.candidate_identity}),
            "registry_lineage_validation": (bool(lineage_valid),
                {"qualification_registry_identity": qualification_registry.registry_identity,
                 "matching_entries": len(entries)}),
            "governance_readiness": (governance_ready,
                {"qualification_governance_eligible": qualification_report.governance_eligible}),
            "human_review_requirement": (self.policy.require_human_review,
                {"required": self.policy.require_human_review, "approval_status": "PENDING"}),
            # This gate authorizes only the promotion authority's eligibility
            # decision. A policy-owned, non-critical readiness condition may
            # therefore remain CONDITIONAL; this is never deployment authority.
            "promotion_authorization": (qualification_valid and policy_accepted and evidence_bound
                and candidate_integrity and bool(lineage_valid),
                {"scope": "DEPLOYMENT_GOVERNANCE_ELIGIBILITY_ONLY",
                 "deployment_authorized": False, "production_authorized": False}),
        }
        gates = tuple(PromotionGate(name, bool(facts[name][0]),
            "GATE_PASSED" if facts[name][0] else "GATE_FAILED", facts[name][1])
            for name in PROMOTION_GATES)
        failed = {x.gate for x in gates if not x.passed}
        decision = ("ELIGIBLE" if not failed else "CONDITIONAL"
                    if failed <= set(self.policy.conditional_gates) else "REJECTED")
        evidence = PromotionEvidence(qualification_report.candidate_identity,
            qualification_report.report_identity, qualification_evidence.evidence_identity,
            qualification_registry.registry_identity, self.policy.policy_identity, gates)
        report = PromotionReport(qualification_report.candidate_identity,
            qualification_report.report_identity, qualification_registry.registry_identity,
            self.policy, evidence, decision, decision in ("ELIGIBLE", "CONDITIONAL"))
        if not report.governance_queue_eligible:
            return PromotionResult(report, None, None)
        request = PromotionApprovalRequest(report.report_identity, report.candidate_identity,
                                           self.policy.policy_identity)
        queue = GovernanceQueueEntry(report.report_identity, request.request_identity,
                                     report.candidate_identity, report.decision)
        return PromotionResult(report, request, queue)

    promote = assess

    def replay(self, expected: PromotionResult, qualification_registry,
               qualification_report, qualification_evidence) -> bool:
        try:
            _validate(expected)
            return self.assess(qualification_registry, qualification_report,
                               qualification_evidence) == expected
        except (PromotionValidationError, TypeError, ValueError, AttributeError, KeyError):
            return False
