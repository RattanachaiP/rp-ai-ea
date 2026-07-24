"""Deterministic, read-only eligibility policy evaluation."""
from __future__ import annotations

from datetime import datetime
import hashlib
import json
import re
from typing import Any, Mapping
from uuid import UUID, uuid5, NAMESPACE_URL

from .models import PolicyConfig, PolicyEvaluationReport, RuleResult

SEVERITY = {"NONE": 0, "LOW": 1, "MEDIUM": 2, "HIGH": 3, "CRITICAL": 4}
RULES = (
    "SamplePolicy", "PerformancePolicy", "StabilityPolicy", "ConflictPolicy",
    "LifecyclePolicy", "GovernancePolicy", "SchemaPolicy",
)
BASELINE_RE = re.compile(r"^(?:[0-9a-fA-F]{7,64}|[A-Za-z0-9._/-]+@[0-9a-fA-F]{7,64})$")


def _get(value: Any, name: str, default=None):
    return value.get(name, default) if isinstance(value, Mapping) else getattr(value, name, default)


def _canonical(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), default=str, allow_nan=False)


def _time(value: str, error: str) -> datetime:
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except (AttributeError, ValueError) as exc:
        raise ValueError(error) from exc
    if parsed.tzinfo is None:
        raise ValueError(error)
    return parsed


class KnowledgePolicyEngine:
    """Evaluates supplied snapshots only; it never writes or changes their state."""

    def __init__(self, config: PolicyConfig | None = None, *, source_baseline: str | None = None):
        if not isinstance(source_baseline, str) or not BASELINE_RE.fullmatch(source_baseline):
            raise ValueError("INVALID_SOURCE_BASELINE")
        self.config = config or PolicyConfig()
        self.source_baseline = source_baseline

    def evaluate_rule(self, category: str, knowledge: Any, *, governance: Any = None,
                      lifecycle_state: str | None = None,
                      analytics: Mapping[str, Any] | None = None,
                      evaluation_timestamp: str | None = None) -> RuleResult:
        if category not in RULES:
            raise ValueError("UNKNOWN_POLICY_RULE")
        analytics = analytics or {}
        governance_lifecycle = _get(governance, "current_lifecycle_state")
        if lifecycle_state and governance_lifecycle and lifecycle_state != governance_lifecycle:
            return RuleResult(category, "FAIL", "Lifecycle evidence sources conflict.", 0)
        lifecycle = lifecycle_state or governance_lifecycle

        if category == "SamplePolicy":
            value = _get(knowledge, "sample_count")
            ok = isinstance(value, int) and not isinstance(value, bool) and value >= self.config.minimum_sample_count
            return RuleResult(category, "PASS" if ok else "FAIL", "Minimum sample requirement satisfied." if ok else "Sample count missing or below production threshold.", int(ok))
        if category == "PerformancePolicy":
            metrics = (
                (_get(analytics, "significance", _get(knowledge, "significance")), self.config.minimum_significance, "Statistical significance"),
                (_get(knowledge, "verified_win_rate"), self.config.minimum_win_rate, "Win rate"),
                (_get(knowledge, "average_rr"), self.config.minimum_average_rr, "Average RR"),
            )
            failed = [label for value, minimum, label in metrics if not isinstance(value, (int, float)) or isinstance(value, bool) or value < minimum]
            return RuleResult(category, "PASS" if not failed else "FAIL", "Performance requirements satisfied." if not failed else f"{failed[0]} missing or below production threshold.", int(not failed))
        if category == "StabilityPolicy":
            value = _get(analytics, "stability_classification", _get(analytics, "stability"))
            ok = isinstance(value, str) and value in self.config.allowed_stability
            return RuleResult(category, "PASS" if ok else "FAIL", "Stability classification accepted." if ok else "Stability evidence missing or not accepted.", int(ok))
        if category == "ConflictPolicy":
            raw = _get(analytics, "conflict_severity")
            if not isinstance(raw, str):
                return RuleResult(category, "FAIL", "Conflict severity evidence is missing.", 0)
            value = raw.upper()
            ok = value in SEVERITY and SEVERITY[value] <= SEVERITY[self.config.maximum_conflict_severity]
            return RuleResult(category, "PASS" if ok else "FAIL", "Conflict severity accepted." if ok else "Conflict severity exceeds configured limit or is invalid.", int(ok))
        if category == "LifecyclePolicy":
            ok = lifecycle == self.config.required_lifecycle_state
            return RuleResult(category, "PASS" if ok else "FAIL", "Lifecycle requirement satisfied." if ok else "Lifecycle evidence missing, conflicting, or not production eligible.", int(ok))
        if category == "GovernancePolicy":
            value = _get(governance, "production_eligible")
            ok = isinstance(value, bool) and value == self.config.required_governance_status
            return RuleResult(category, "PASS" if ok else "FAIL", "Governance requirement satisfied." if ok else "Governance eligibility evidence missing or invalid.", int(ok))

        schema = _get(knowledge, "schema_version")
        if schema not in self.config.supported_schema_versions:
            return RuleResult(category, "FAIL", "Knowledge schema is incompatible.", 0)
        analytics_timestamp = _get(analytics, "timestamp", _get(analytics, "analytics_timestamp"))
        if not analytics_timestamp or not evaluation_timestamp:
            return RuleResult(category, "FAIL", "Analytics freshness evidence is missing.", 0)
        evaluated = _time(evaluation_timestamp, "INVALID_EVALUATION_TIMESTAMP")
        observed = _time(analytics_timestamp, "INVALID_ANALYTICS_TIMESTAMP")
        age = (evaluated - observed).total_seconds()
        if age < 0:
            return RuleResult(category, "FAIL", "Analytics snapshot is future-dated.", 0)
        if age > self.config.maximum_analytics_age_seconds:
            return RuleResult(category, "FAIL", "Analytics snapshot exceeds configured freshness limit.", 0)
        return RuleResult(category, "PASS", "Schema compatibility and analytics freshness satisfied.", 1)

    def evaluate_all(self, knowledge: Any, **kwargs) -> tuple[RuleResult, ...]:
        return tuple(self.evaluate_rule(rule, knowledge, **kwargs) for rule in RULES)

    def evaluate(self, knowledge: Any, *, governance: Any = None,
                 lifecycle_state: str | None = None,
                 analytics: Mapping[str, Any] | None = None,
                 evaluation_timestamp: str | None = None) -> PolicyEvaluationReport:
        timestamp = evaluation_timestamp or _get(analytics or {}, "timestamp") or _get(knowledge, "created_timestamp")
        if not timestamp:
            raise ValueError("EVALUATION_TIMESTAMP_REQUIRED")
        _time(timestamp, "INVALID_EVALUATION_TIMESTAMP")
        knowledge_uuid = _get(knowledge, "knowledge_uuid")
        if not isinstance(knowledge_uuid, str) or not knowledge_uuid:
            raise ValueError("KNOWLEDGE_UUID_REQUIRED")
        results = self.evaluate_all(knowledge, governance=governance, lifecycle_state=lifecycle_state, analytics=analytics, evaluation_timestamp=timestamp)
        failed = tuple(result.to_dict() for result in results if result.outcome == "FAIL")
        passed = tuple(result.to_dict() for result in results if result.outcome == "PASS")
        warnings = tuple(result.to_dict() for result in results if result.outcome == "WARNING")
        identity_source = _canonical({"knowledge_uuid": knowledge_uuid, "policy": self.config.canonical_dict(), "results": [r.to_dict() for r in results], "timestamp": timestamp, "source_baseline": self.source_baseline})
        identity = str(uuid5(NAMESPACE_URL, hashlib.sha256(identity_source.encode("utf-8")).hexdigest()))
        return PolicyEvaluationReport(knowledge_uuid, self.config.version, not failed, sum(r.score for r in results), failed, passed, warnings, timestamp, self.source_baseline, identity)

    def eligible(self, knowledge: Any, **kwargs) -> bool:
        return self.evaluate(knowledge, **kwargs).eligible

    def explain(self, knowledge: Any, **kwargs) -> tuple[str, ...]:
        return tuple(f"{item.outcome}: {item.reason}" for item in self.evaluate_all(knowledge, **kwargs))
