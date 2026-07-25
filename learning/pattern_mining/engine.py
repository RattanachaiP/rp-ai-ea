"""PR175 offline-only pattern-mining orchestration."""
from __future__ import annotations

from hashlib import sha256
from uuid import UUID, uuid5

from learning.learning_policy import GovernedLearningPolicyReport

from .exceptions import PatternMiningError
from .feature_extractor import extract
from .models import PatternMiningReport
from .pattern_builder import build, canonical

_NAMESPACE = UUID("a1fa8bf9-f5d3-525e-91ca-fd1055108e99")


class PatternMiningEngine:
    """Discovers advisory candidates without promotion, registry, or runtime access."""

    engine_version = "PR175.1.0"

    def __init__(self, repository=None):
        self._repository = repository

    def mine(self, policy: GovernedLearningPolicyReport) -> PatternMiningReport:
        if not isinstance(policy, GovernedLearningPolicyReport):
            raise PatternMiningError("INVALID_POLICY_REPORT")
        if policy.eligibility_state != "ELIGIBLE_FOR_PATTERN_MINING":
            raise PatternMiningError("POLICY_NOT_ELIGIBLE")
        if policy.sample_count < 0:
            raise PatternMiningError("INVALID_STATISTICS")
        rows = extract(policy)
        if any(row["outcome_contract"] != rows[0]["outcome_contract"] for row in rows):
            raise PatternMiningError("MIXED_OUTCOME_CONTRACT")
        if sum(len(row["outcomes"]) for row in rows) != policy.sample_count:
            raise PatternMiningError("INVALID_STATISTICS")
        patterns = build(rows, policy.sample_count, policy.generated_at)
        summary = {"sample_count": sum(x.sample_count for x in patterns),
                   "win_count": sum(x.win_count for x in patterns), "loss_count": sum(x.loss_count for x in patterns),
                   "neutral_count": sum(x.neutral_count for x in patterns), "engine_version": self.engine_version}
        identity = {"engine_version": self.engine_version, "policy_uuid": policy.policy_uuid,
                    "candidate_patterns": [x.to_dict() for x in patterns], "statistics_summary": summary}
        report = PatternMiningReport(str(uuid5(_NAMESPACE, sha256(canonical(identity).encode()).hexdigest())),
                                     policy.policy_uuid, patterns, len(patterns), summary, policy.generated_at, True)
        if self._repository:
            self._repository.save(report)
        return report

    discover = mine
