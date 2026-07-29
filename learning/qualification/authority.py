"""Offline policy authority; never trains, evaluates, promotes, deploys, or accesses runtime/broker."""
from .candidate import GATES, QualificationEvidence, QualificationGate, QualificationPolicy, QualificationReport

def _validate(value): type(value)(**value.__dict__)
class CandidateQualificationAuthority:
    def __init__(self, policy: QualificationPolicy): _validate(policy); self.policy = policy
    def qualify(self, candidate_registry, evaluation_registry, candidate, candidate_evidence,
                evaluation_report, evidence_registry, evidence: QualificationEvidence) -> QualificationReport:
        for value in (candidate_registry, evaluation_registry, candidate, candidate_evidence, evaluation_report, evidence_registry, evidence): _validate(value)
        candidates = tuple(x for x in candidate_registry.entries if x.candidate.model_identity == candidate.model_identity)
        if (len(candidates) != 1 or candidates[0].candidate != candidate or candidates[0].evidence != candidate_evidence
                or candidate_evidence.evidence_identity != candidates[0].evidence.evidence_identity):
            raise ValueError("QUALIFICATION_CANDIDATE_REGISTRY_BINDING_INVALID")
        evaluations = tuple(x for x in evaluation_registry.entries if x.report.report_identity == evaluation_report.report_identity)
        if len(evaluations) != 1 or evaluations[0].report != evaluation_report or evaluation_report.candidate_identity != candidate.model_identity:
            raise ValueError("QUALIFICATION_EVALUATION_REGISTRY_BINDING_INVALID")
        if (evidence.evidence_registry_identity != evidence_registry.registry_identity
                or evidence.candidate_identity != candidate.model_identity or evidence.evaluation_report_identity != evaluation_report.report_identity
                or evidence.qualification_policy_identity != self.policy.policy_identity): raise ValueError("QUALIFICATION_EVIDENCE_BINDING_INVALID")
        attestations = tuple(x for x in evidence_registry.attestations if x.attestation_identity in evidence.attestation_identities)
        if (len(attestations) != len(evidence.attestation_identities) or tuple(x.attestation_identity for x in attestations) != evidence.attestation_identities
                or any(x.candidate_identity != candidate.model_identity or x.evaluation_report_identity != evaluation_report.report_identity
                       or x.qualification_policy_identity != self.policy.policy_identity for x in attestations)):
            raise ValueError("QUALIFICATION_AUTHORITATIVE_EVIDENCE_BINDING_INVALID")
        dimensions = {x.dimension: x for x in evaluation_report.dimensions}; stats = evaluation_report.statistical_validation
        attested = {x.domain: x for x in attestations}
        if set(attested) != {"governance_compliance", "policy_compliance", "architecture_compatibility"}:
            raise ValueError("QUALIFICATION_AUTHORITATIVE_EVIDENCE_INCOMPLETE")
        if tuple(attested[domain].issuer_identity for domain in ("governance_compliance", "policy_compliance", "architecture_compatibility")) != self.policy.trusted_evidence_issuer_identities:
            raise ValueError("QUALIFICATION_EVIDENCE_ISSUER_UNTRUSTED")
        accepted = evaluation_report.policy.policy_identity in self.policy.accepted_evaluation_policy_identities
        regime_minimum = min(stats.regime_counts.values())
        facts = {
          "replay_integrity": (evaluation_report.replay_validation.consistent and dimensions["replay_consistency"].passed,
            {"replay_digest": evaluation_report.replay_validation.first_computation_digest}),
          "performance_threshold": (evaluation_report.candidate_score >= self.policy.minimum_candidate_score,
            {"observed": evaluation_report.candidate_score, "required": self.policy.minimum_candidate_score}),
          "statistical_confidence": (stats.record_count >= self.policy.minimum_records and regime_minimum >= self.policy.minimum_regime_records
            and stats.error_stddev <= self.policy.maximum_error_stddev and stats.mean_squared_error <= self.policy.maximum_mean_squared_error
            and stats.confidence_brier_score <= self.policy.maximum_confidence_brier_score,
            {"record_count": stats.record_count, "minimum_records": self.policy.minimum_records, "minimum_observed_regime_records": regime_minimum,
             "minimum_regime_records": self.policy.minimum_regime_records, "error_stddev": stats.error_stddev,
             "maximum_error_stddev": self.policy.maximum_error_stddev, "mean_squared_error": stats.mean_squared_error,
             "maximum_mean_squared_error": self.policy.maximum_mean_squared_error, "confidence_brier_score": stats.confidence_brier_score,
             "maximum_confidence_brier_score": self.policy.maximum_confidence_brier_score}),
          "risk_acceptance": (dimensions["risk_characteristics"].score >= self.policy.minimum_risk_score,
            {"observed": dimensions["risk_characteristics"].score, "required": self.policy.minimum_risk_score}),
          "calibration_quality": (min(dimensions["calibration"].score, dimensions["confidence_reliability"].score) >= self.policy.minimum_calibration_score,
            {"calibration": dimensions["calibration"].score, "confidence_reliability": dimensions["confidence_reliability"].score,
             "required": self.policy.minimum_calibration_score}),
          "governance_compliance": (attested["governance_compliance"].compliant, {"attestation_identity": attested["governance_compliance"].attestation_identity}),
          "policy_compliance": (attested["policy_compliance"].compliant and accepted,
            {"attestation_identity": attested["policy_compliance"].attestation_identity, "evaluation_policy_accepted": accepted}),
          "architecture_compatibility": (attested["architecture_compatibility"].compliant,
            {"attestation_identity": attested["architecture_compatibility"].attestation_identity})}
        gates = tuple(QualificationGate(x, facts[x][0], "GATE_PASSED" if facts[x][0] else "GATE_FAILED", facts[x][1]) for x in GATES)
        failed = {x.gate for x in gates if not x.passed}; prerequisite = not self.policy.require_evaluation_qualified or evaluation_report.qualified
        decision = "REJECTED" if not prerequisite else "PASS" if not failed else "CONDITIONAL" if failed <= set(self.policy.conditional_gates) else "FAIL"
        return QualificationReport(candidate.model_identity, candidate_evidence.evidence_identity, candidate_registry.registry_identity,
            evaluation_report.report_identity, evaluation_registry.registry_identity, self.policy, evidence, gates,
            evaluation_report.qualified, decision, decision == "PASS")
    def replay(self, expected, *inputs):
        try: _validate(expected); return self.qualify(*inputs) == expected
        except (TypeError, ValueError, AttributeError, KeyError): return False
