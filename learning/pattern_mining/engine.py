"""PR175 offline-only pattern-mining orchestration."""
from __future__ import annotations

from hashlib import sha256
from typing import Any
from uuid import UUID, uuid5

from learning.learning_policy import GovernedLearningPolicyReport

from .exceptions import PatternMiningError
from .feature_extractor import extract
from .models import ApprovedPatternMiningEvidenceEnvelope, PatternMiningConfig, PatternMiningReport
from .pattern_builder import build, canonical

_NAMESPACE = UUID("a1fa8bf9-f5d3-525e-91ca-fd1055108e99")


def _uuid(value: Any) -> bool:
    try: UUID(str(value)); return True
    except (TypeError, ValueError, AttributeError): return False


def _digest(value: Any) -> bool:
    return isinstance(value, str) and len(value) == 64 and all(c in "0123456789abcdef" for c in value)


class PatternMiningEngine:
    """Consumes approved evidence; never creates evidence or owns runtime authority."""
    engine_version = "PR175.2.0"
    supported_policy_versions = ("PR174.2.0",)

    def __init__(self, config: PatternMiningConfig | None = None, repository=None):
        self.config = config or PatternMiningConfig(); self._repository = repository

    def mine(self, policy: GovernedLearningPolicyReport,
             evidence: ApprovedPatternMiningEvidenceEnvelope | None = None) -> PatternMiningReport:
        self._validate_policy(policy)
        if not isinstance(evidence, ApprovedPatternMiningEvidenceEnvelope):
            raise PatternMiningError("MISSING_APPROVED_PATTERN_EVIDENCE")
        summary = policy.validation_summary
        expected = (policy.policy_uuid, policy.policy_version, summary["source_attribution_uuid"], summary["source_digest"],
                    summary["replay_digest"], policy.knowledge_uuid, policy.knowledge_version)
        actual = (evidence.policy_uuid, evidence.policy_version, evidence.source_attribution_uuid, evidence.source_digest,
                  evidence.replay_digest, evidence.knowledge_uuid, evidence.knowledge_version)
        if actual != expected:
            labels = ("MIXED_POLICY_UUID", "UNSUPPORTED_POLICY_VERSION", "MIXED_SOURCE_ATTRIBUTION",
                      "MIXED_SOURCE_DIGEST", "MIXED_REPLAY_DIGEST", "MIXED_KNOWLEDGE_UUID", "MIXED_KNOWLEDGE_VERSION")
            raise PatternMiningError(labels[next(i for i, pair in enumerate(zip(actual, expected)) if pair[0] != pair[1])])
        if tuple(summary["outcome_contract"]) != evidence.outcome_contract:
            raise PatternMiningError("MIXED_OUTCOME_CONTRACT")
        if len(evidence.approved_samples) != policy.sample_count:
            raise PatternMiningError("INVALID_STATISTICS")
        patterns = build(extract(evidence, self.config), evidence, self.config, self.engine_version)
        statistics = {"sample_count": sum(x.sample_count for x in patterns), "win_count": sum(x.win_count for x in patterns),
                      "loss_count": sum(x.loss_count for x in patterns), "neutral_count": sum(x.neutral_count for x in patterns),
                      "engine_version": self.engine_version}
        identity = {"engine_version": self.engine_version, "policy_uuid": policy.policy_uuid,
                    "patterns": [x.to_dict() for x in patterns], "statistics_summary": statistics}
        report = PatternMiningReport(str(uuid5(_NAMESPACE, sha256(canonical(identity).encode()).hexdigest())), policy.policy_uuid,
                                     self.engine_version, patterns, len(patterns), statistics, evidence.generated_at, True)
        if self._repository: self._repository.save(report)
        return report

    discover = mine

    def _validate_policy(self, policy: Any) -> None:
        if not isinstance(policy, GovernedLearningPolicyReport): raise PatternMiningError("INVALID_POLICY_REPORT")
        summary = policy.validation_summary
        if policy.policy_version not in self.supported_policy_versions: raise PatternMiningError("UNSUPPORTED_POLICY_VERSION")
        if policy.eligibility_state != "ELIGIBLE_FOR_PATTERN_MINING": raise PatternMiningError("POLICY_NOT_ELIGIBLE")
        if (policy.advisory_only is not True or policy.blocking_reasons or not policy.hard_gates
                or not all(value is True for value in policy.hard_gates.values())
                or policy.sample_count < policy.minimum_required_samples or policy.additional_samples_required != 0):
            raise PatternMiningError("TAMPERED_POLICY_REPORT")
        required = ("source_attribution_uuid", "source_digest", "replay_digest", "outcome_contract", "eligibility_scope")
        if not summary or any(key not in summary for key in required): raise PatternMiningError("INVALID_POLICY_PROVENANCE")
        contract = summary["outcome_contract"]
        if (not _uuid(summary["source_attribution_uuid"]) or not _digest(summary["source_digest"])
                or not _digest(summary["replay_digest"]) or not isinstance(contract, (tuple, list)) or len(contract) != 2
                or not all(isinstance(value, str) and value for value in contract)
                or summary["eligibility_scope"] != "OFFLINE_PATTERN_MINING_EVALUATION_ONLY"):
            raise PatternMiningError("INVALID_POLICY_PROVENANCE")
