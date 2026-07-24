"""Deterministic, read-only eligibility policy evaluation."""
from __future__ import annotations
from datetime import datetime, timezone
import hashlib, json
from typing import Any, Mapping
from .models import PolicyConfig, PolicyEvaluationReport, RuleResult

SEVERITY = {"NONE": 0, "LOW": 1, "MEDIUM": 2, "HIGH": 3, "CRITICAL": 4}
RULES = ("SamplePolicy", "PerformancePolicy", "StabilityPolicy", "ConflictPolicy", "LifecyclePolicy", "GovernancePolicy", "SchemaPolicy")
def _get(value: Any, name: str, default=None): return value.get(name, default) if isinstance(value, Mapping) else getattr(value, name, default)
def _digest(value): return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"), default=str).encode()).hexdigest()
def _time(value: str): return datetime.fromisoformat(value.replace("Z", "+00:00"))

class KnowledgePolicyEngine:
    """Evaluates supplied snapshots only; it never writes or changes their state."""
    def __init__(self, config: PolicyConfig | None = None, *, source_baseline: str = "UNKNOWN"):
        self.config, self.source_baseline = config or PolicyConfig(), source_baseline
        if not source_baseline: raise ValueError("SOURCE_BASELINE_REQUIRED")

    def evaluate_rule(self, category: str, knowledge: Any, *, governance: Any = None, lifecycle_state: str | None = None, analytics: Mapping[str, Any] | None = None, evaluation_timestamp: str | None = None) -> RuleResult:
        if category not in RULES: raise ValueError("UNKNOWN_POLICY_RULE")
        analytics, lifecycle = analytics or {}, lifecycle_state or _get(governance, "current_lifecycle_state")
        if category == "SamplePolicy":
            ok = _get(knowledge, "sample_count", 0) >= self.config.minimum_sample_count
            return RuleResult(category, "PASS" if ok else "FAIL", "Minimum sample requirement satisfied." if ok else "Sample count below production threshold.", int(ok))
        if category == "PerformancePolicy":
            metrics = (("significance", _get(analytics, "significance", _get(knowledge, "significance")), self.config.minimum_significance, "Statistical significance"), ("verified_win_rate", _get(knowledge, "verified_win_rate"), self.config.minimum_win_rate, "Win rate"), ("average_rr", _get(knowledge, "average_rr"), self.config.minimum_average_rr, "Average RR"))
            failed = [label for _, value, minimum, label in metrics if value is None or value < minimum]
            return RuleResult(category, "PASS" if not failed else "FAIL", "Performance requirements satisfied." if not failed else f"{failed[0]} below production threshold.", int(not failed))
        if category == "StabilityPolicy":
            value = _get(analytics, "stability_classification", _get(analytics, "stability"))
            ok = value in self.config.allowed_stability
            return RuleResult(category, "PASS" if ok else "FAIL", "Stability classification accepted." if ok else "Stability classification is not accepted.", int(ok))
        if category == "ConflictPolicy":
            value = str(_get(analytics, "conflict_severity", "NONE")).upper(); ok = SEVERITY.get(value, 99) <= SEVERITY.get(self.config.maximum_conflict_severity, -1)
            return RuleResult(category, "PASS" if ok else "FAIL", "Conflict severity accepted." if ok else "Conflict severity exceeds configured limit.", int(ok))
        if category == "LifecyclePolicy":
            ok = lifecycle == self.config.required_lifecycle_state
            return RuleResult(category, "PASS" if ok else "FAIL", "Lifecycle requirement satisfied." if ok else "Lifecycle state is not production eligible.", int(ok))
        if category == "GovernancePolicy":
            value = _get(governance, "production_eligible")
            ok = value is self.config.required_governance_status
            return RuleResult(category, "PASS" if ok else "FAIL", "Governance requirement satisfied." if ok else "Governance status is not production eligible.", int(ok))
        schema = _get(knowledge, "schema_version")
        ok = schema in self.config.supported_schema_versions
        if not ok: return RuleResult(category, "FAIL", "Knowledge schema is incompatible.", 0)
        timestamp = _get(analytics, "timestamp", _get(analytics, "analytics_timestamp"))
        if timestamp and evaluation_timestamp:
            age = (_time(evaluation_timestamp) - _time(timestamp)).total_seconds()
            if age > self.config.maximum_analytics_age_seconds: return RuleResult(category, "WARNING", "Analytics snapshot older than configured freshness limit.", 0)
        return RuleResult(category, "PASS", "Schema compatibility and analytics freshness satisfied.", 1)

    def evaluate_all(self, knowledge: Any, **kwargs) -> tuple[RuleResult, ...]:
        return tuple(self.evaluate_rule(rule, knowledge, **kwargs) for rule in RULES)

    def evaluate(self, knowledge: Any, *, governance: Any = None, lifecycle_state: str | None = None, analytics: Mapping[str, Any] | None = None, evaluation_timestamp: str | None = None) -> PolicyEvaluationReport:
        timestamp = evaluation_timestamp or _get(analytics or {}, "timestamp") or _get(knowledge, "created_timestamp")
        if not timestamp: raise ValueError("EVALUATION_TIMESTAMP_REQUIRED")
        results = self.evaluate_all(knowledge, governance=governance, lifecycle_state=lifecycle_state, analytics=analytics, evaluation_timestamp=timestamp)
        failed = tuple(result.to_dict() for result in results if result.outcome == "FAIL"); passed = tuple(result.to_dict() for result in results if result.outcome == "PASS"); warnings = tuple(result.to_dict() for result in results if result.outcome == "WARNING")
        identity = _digest({"knowledge_uuid": _get(knowledge, "knowledge_uuid"), "policy": self.config.canonical_dict(), "results": [r.to_dict() for r in results], "timestamp": timestamp, "source_baseline": self.source_baseline})[:32]
        return PolicyEvaluationReport(_get(knowledge, "knowledge_uuid"), self.config.version, not failed, sum(r.score for r in results), failed, passed, warnings, timestamp, self.source_baseline, identity)
    def eligible(self, knowledge: Any, **kwargs) -> bool: return self.evaluate(knowledge, **kwargs).eligible
    def explain(self, knowledge: Any, **kwargs) -> tuple[str, ...]: return tuple(f"{item.outcome}: {item.reason}" for item in self.evaluate_all(knowledge, **kwargs))
