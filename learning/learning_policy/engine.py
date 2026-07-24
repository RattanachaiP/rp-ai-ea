"""PR174 deterministic, offline eligibility gate for PR173 attribution reports."""
from __future__ import annotations

from hashlib import sha256
import json
from math import isfinite
from typing import Any
from uuid import UUID, uuid5

from learning.outcome_attribution import KnowledgeOutcomeAttributionReport

from .exceptions import GovernedLearningPolicyError
from .models import GovernedLearningPolicyReport

_NAMESPACE = UUID("4b4c2052-2f11-59ac-8fd4-469495b8be2e")
_MINIMUM_PATTERN_SAMPLES = 30


def _canonical(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)


def _valid_uuid(value: object) -> bool:
    try:
        UUID(str(value))
        return True
    except (TypeError, ValueError, AttributeError):
        return False


def _valid_digest(value: object) -> bool:
    return isinstance(value, str) and len(value) == 64 and all(char in "0123456789abcdef" for char in value.lower())


def _finite(value: object) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool) and isfinite(value)


class GovernedLearningPolicyEngine:
    """Classifies immutable PR173 evidence; it never learns, mines, or mutates runtime."""

    policy_version = "PR174.1.0"

    def __init__(self, repository=None) -> None:
        self._repository = repository

    def evaluate(self, attribution: KnowledgeOutcomeAttributionReport) -> GovernedLearningPolicyReport:
        """Return an advisory eligibility report for one immutable attribution report."""
        facts = self._validate(attribution)
        sample_count = facts["sample_count"]
        sample_sufficiency = min(1.0, sample_count / _MINIMUM_PATTERN_SAMPLES)
        # PR173 intentionally supplies aggregate, non-causal evidence.  Stability is
        # therefore assessed only from sufficient observed outcome support.
        outcome_stability = min(1.0, sample_count / 5.0)
        historical_repeatability = facts["sample_support"]
        components = {
            "sample_sufficiency": sample_sufficiency,
            "evidence_consistency": 1.0,
            "outcome_stability": outcome_stability,
            "historical_repeatability": historical_repeatability,
            "data_quality": 1.0,
        }
        score = sum(components.values()) / len(components)
        state = (
            "ELIGIBLE_FOR_PATTERN_MINING" if sample_count >= _MINIMUM_PATTERN_SAMPLES and score >= 0.8
            else "REQUIRES_MORE_DATA" if score >= 0.5
            else "NOT_ELIGIBLE"
        )
        source = attribution.to_dict()
        policy_uuid = str(uuid5(_NAMESPACE, sha256(_canonical([self.policy_version, source]).encode()).hexdigest()))
        report = GovernedLearningPolicyReport(
            policy_uuid=policy_uuid,
            knowledge_uuid=facts["knowledge_uuid"],
            knowledge_version=facts["knowledge_version"],
            eligibility_score=score,
            eligibility_state=state,
            sample_quality={
                "sample_count": sample_count,
                "minimum_pattern_mining_samples": _MINIMUM_PATTERN_SAMPLES,
                "sample_sufficiency": sample_sufficiency,
            },
            validation_summary={
                "valid": True,
                "advisory_only": True,
                "outcome_metric": facts["outcome_metric"],
                "outcome_unit": facts["outcome_unit"],
                "replay_digest": facts["replay_digest"],
            },
            evaluation_summary={"components": components, "policy_version": self.policy_version},
            generated_at=attribution.created_at,
        )
        if self._repository is not None:
            self._repository.save(report)
        return report

    # A concise alias makes the boundary ergonomic while retaining one behavior.
    assess = evaluate

    def _validate(self, attribution: Any) -> dict[str, Any]:
        if not isinstance(attribution, KnowledgeOutcomeAttributionReport):
            raise GovernedLearningPolicyError("INVALID_OUTCOME_ATTRIBUTION_REPORT")
        try:
            data = attribution.to_dict()
            _canonical(data)  # Reject NaN, Infinity, and non-canonical payloads.
        except (TypeError, ValueError, OverflowError) as error:
            raise GovernedLearningPolicyError("INVALID_OUTCOME_ATTRIBUTION_REPORT") from error
        summary = attribution.summary
        pairs = attribution.knowledge_versions
        if (
            not attribution.advisory_only
            or not _valid_uuid(attribution.attribution_uuid)
            or not _valid_digest(attribution.replay_digest)
            or not _valid_digest(attribution.source_digest)
            or len(pairs) != 1
            or not isinstance(summary.outcome_metric, str) or not summary.outcome_metric
            or not isinstance(summary.outcome_unit, str) or not summary.outcome_unit
            or summary.replay_digest != attribution.replay_digest
        ):
            raise GovernedLearningPolicyError("INVALID_ATTRIBUTION_EVIDENCE")
        knowledge_uuid, knowledge_version = pairs[0]
        if not _valid_uuid(knowledge_uuid) or not isinstance(knowledge_version, str) or not knowledge_version:
            raise GovernedLearningPolicyError("INVALID_KNOWLEDGE_IDENTITY")
        numeric = (summary.total_outcome, summary.average_outcome)
        counts = (summary.trade_count, summary.winning_trade_count, summary.losing_trade_count, summary.neutral_count)
        if not all(_finite(value) for value in numeric) or not all(isinstance(value, int) and not isinstance(value, bool) and value >= 0 for value in counts) or sum(counts[1:]) != counts[0]:
            raise GovernedLearningPolicyError("INVALID_OUTCOME_EVIDENCE")
        profiles = attribution.performance_profiles
        confidences = attribution.confidence
        if len(profiles) != 1 or len(confidences) != 1:
            raise GovernedLearningPolicyError("MIXED_KNOWLEDGE_IDENTITIES")
        profile, confidence = profiles[0], confidences[0]
        if (profile.knowledge_uuid, profile.knowledge_version) != (knowledge_uuid, knowledge_version) or (confidence.knowledge_uuid, confidence.knowledge_version) != (knowledge_uuid, knowledge_version):
            raise GovernedLearningPolicyError("MIXED_KNOWLEDGE_IDENTITIES")
        if profile.sample_count != summary.trade_count or confidence.sample_count != summary.trade_count:
            raise GovernedLearningPolicyError("INCONSISTENT_SAMPLE_COUNT")
        if not _finite(confidence.sample_support) or not 0.0 <= confidence.sample_support <= 1.0:
            raise GovernedLearningPolicyError("INVALID_CONFIDENCE")
        return {"knowledge_uuid": knowledge_uuid, "knowledge_version": knowledge_version, "sample_count": summary.trade_count, "sample_support": float(confidence.sample_support), "outcome_metric": summary.outcome_metric, "outcome_unit": summary.outcome_unit, "replay_digest": attribution.replay_digest}
