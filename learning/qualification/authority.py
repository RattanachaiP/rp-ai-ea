"""Policy-only qualification authority; performs no training, evaluation, or runtime work."""
from learning.common.immutable import thaw
from .candidate import GATES, QualificationEvidence, QualificationGate, QualificationPolicy, QualificationReport


def _validate(value): type(value)(**value.__dict__)


class CandidateQualificationAuthority:
    def __init__(self, policy: QualificationPolicy): _validate(policy); self.policy = policy

    def qualify(self, candidate_registry, evaluation_registry, candidate, evaluation_report,
                evidence: QualificationEvidence) -> QualificationReport:
        for value in (candidate_registry, evaluation_registry, candidate, evaluation_report, evidence): _validate(value)
        candidates = tuple(x for x in candidate_registry.entries if x.candidate.model_identity == candidate.model_identity)
        evaluations = tuple(x for x in evaluation_registry.entries if x.report.report_identity == evaluation_report.report_identity)
        if len(candidates) != 1: raise ValueError("QUALIFICATION_CANDIDATE_NOT_REGISTERED")
        if len(evaluations) != 1 or evaluation_report.candidate_identity != candidate.model_identity:
            raise ValueError("QUALIFICATION_EVALUATION_NOT_REGISTERED")
        if evidence.candidate_identity != candidate.model_identity or evidence.evaluation_report_identity != evaluation_report.report_identity:
            raise ValueError("QUALIFICATION_EVIDENCE_BINDING_INVALID")
        dimensions = {x.dimension: x for x in evaluation_report.dimensions}
        stats, replay = evaluation_report.statistical_validation, evaluation_report.replay_validation
        accepted = (not self.policy.accepted_evaluation_policy_identities or
                    evaluation_report.policy.policy_identity in self.policy.accepted_evaluation_policy_identities)
        facts = {
            "replay_integrity": (replay.consistent and dimensions["replay_consistency"].passed,
                                 {"first_digest": replay.first_computation_digest, "second_digest": replay.second_computation_digest}),
            "performance_threshold": (evaluation_report.candidate_score >= self.policy.minimum_candidate_score,
                                      {"score": evaluation_report.candidate_score, "threshold": self.policy.minimum_candidate_score}),
            "statistical_confidence": (stats.record_count >= self.policy.minimum_records and stats.error_stddev <= self.policy.maximum_error_stddev,
                                       {"record_count": stats.record_count, "minimum_records": self.policy.minimum_records,
                                        "error_stddev": stats.error_stddev, "maximum_error_stddev": self.policy.maximum_error_stddev}),
            "risk_acceptance": (dimensions["risk_characteristics"].score >= self.policy.minimum_risk_score,
                                {"score": dimensions["risk_characteristics"].score, "threshold": self.policy.minimum_risk_score}),
            "calibration_quality": (min(dimensions["calibration"].score, dimensions["confidence_reliability"].score) >= self.policy.minimum_calibration_score,
                                    {"calibration_score": dimensions["calibration"].score,
                                     "confidence_score": dimensions["confidence_reliability"].score,
                                     "threshold": self.policy.minimum_calibration_score}),
            "governance_compliance": (evidence.governance_compliant, {"reference": evidence.governance_reference}),
            "policy_compliance": (evidence.policy_compliant and accepted,
                                  {"reference": evidence.policy_reference, "evaluation_policy_accepted": accepted}),
            "architecture_compatibility": (evidence.architecture_compatible, {"reference": evidence.architecture_reference}),
        }
        gates = tuple(QualificationGate(name, facts[name][0], "GATE_PASSED" if facts[name][0] else "GATE_FAILED", facts[name][1]) for name in GATES)
        failed = {x.gate for x in gates if not x.passed}
        decision = ("REJECTED" if not evaluation_report.qualified else "PASS" if not failed else
                    "CONDITIONAL" if failed <= set(self.policy.conditional_gates) else "FAIL")
        return QualificationReport(candidate.model_identity, candidate_registry.registry_identity,
            evaluation_report.report_identity, evaluation_registry.registry_identity, self.policy,
            evidence.evidence_identity, gates, evaluation_report.qualified, decision, decision in ("PASS", "CONDITIONAL"))

    def replay(self, expected, *inputs):
        try: _validate(expected); return self.qualify(*inputs) == expected
        except (TypeError, ValueError, AttributeError, KeyError): return False
