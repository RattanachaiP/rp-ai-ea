"""Deterministic readiness evaluation over one supplied Control Plane snapshot only."""
from __future__ import annotations
from datetime import datetime
from hashlib import sha256
import json
from typing import Any, Mapping
from uuid import NAMESPACE_URL, uuid5
from .models import QualificationConfig, QualificationReport

_SEVERITY = {"NONE": 0, "LOW": 1, "MEDIUM": 2, "HIGH": 3, "CRITICAL": 4}


def _canonical(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False, default=str)


def _timestamp(value: Any) -> datetime | None:
    if not isinstance(value, str): return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        return parsed if parsed.tzinfo else None
    except ValueError: return None


class KnowledgeQualificationEngine:
    """Evaluates readiness only; it accepts no providers other than a snapshot argument."""
    def __init__(self, config: QualificationConfig | None = None): self.config = config or QualificationConfig()

    def _invalid(self, snapshot: Any, reason: str) -> QualificationReport:
        digest = sha256(_canonical(snapshot).encode()).hexdigest()
        knowledge_uuid = "UNKNOWN"
        if isinstance(snapshot, Mapping):
            entries = snapshot.get("knowledge")
            if isinstance(entries, list) and len(entries) == 1 and isinstance(entries[0], Mapping):
                knowledge_uuid = str(entries[0].get("knowledge_uuid", "UNKNOWN"))
        identity = str(uuid5(NAMESPACE_URL, sha256(_canonical([digest, self.config.canonical_dict(), reason]).encode()).hexdigest()))
        return QualificationReport(identity, knowledge_uuid, False, 0, "INVALID_SNAPSHOT", (), (), ({"category": "snapshot", "outcome": "FAIL", "reason": reason},), digest, self.config.version, "")

    def _validate(self, snapshot: Any) -> str | None:
        if not isinstance(snapshot, Mapping): return "Snapshot must be a mapping."
        provided = snapshot.get("snapshot_digest")
        if not isinstance(provided, str) or not provided: return "Snapshot digest is missing."
        body = dict(snapshot); body.pop("snapshot_digest", None)
        if sha256(_canonical(body).encode()).hexdigest() != provided: return "Snapshot digest does not match its contents."
        entries = snapshot.get("knowledge")
        if not isinstance(entries, list) or len(entries) != 1 or not isinstance(entries[0], Mapping): return "Snapshot must contain exactly one knowledge entry."
        if not isinstance(entries[0].get("knowledge_uuid"), str) or not entries[0]["knowledge_uuid"]: return "Knowledge UUID is missing."
        return None

    def evaluate(self, control_plane_snapshot: Mapping[str, Any]) -> QualificationReport:
        """Evaluate a supplied immutable snapshot; no repository or subsystem is accessed."""
        invalid = self._validate(control_plane_snapshot)
        if invalid: return self._invalid(control_plane_snapshot, invalid)
        snapshot = control_plane_snapshot
        digest = snapshot["snapshot_digest"]
        entry = snapshot["knowledge"][0]
        knowledge_uuid = entry["knowledge_uuid"]
        observations = entry.get("observations") if isinstance(entry.get("observations"), Mapping) else {}
        analytics_observation = snapshot.get("analytics_summary") if isinstance(snapshot.get("analytics_summary"), Mapping) else {}
        analytics = analytics_observation.get("value") if analytics_observation.get("status") == "READY" else None
        created_at = analytics.get("timestamp", analytics.get("analytics_timestamp", "")) if isinstance(analytics, Mapping) else ""
        checks: list[dict[str, str]] = []
        warnings: list[dict[str, str]] = []
        incomplete = False
        def check(category: str, ok: bool | None, passed: str, failed: str) -> None:
            nonlocal incomplete
            if ok is None:
                incomplete = True; checks.append({"category": category, "outcome": "FAIL", "reason": failed})
            elif ok: checks.append({"category": category, "outcome": "PASS", "reason": passed})
            else: checks.append({"category": category, "outcome": "FAIL", "reason": failed})
        def value(name: str):
            observation = observations.get(name)
            return observation.get("value") if isinstance(observation, Mapping) and observation.get("status") == "READY" else None
        policy, governance, lifecycle, lineage, knowledge = value("policy"), value("governance"), value("lifecycle"), value("lineage"), value("knowledge")
        check("snapshot", snapshot.get("complete") is True and entry.get("status") == "COMPLETE", "Control Plane snapshot is complete.", "Control Plane snapshot is incomplete.")
        health = snapshot.get("health")
        check("health", health.get("status") == "READY" if isinstance(health, Mapping) else None, "Control Plane health is READY.", "Control Plane health is not READY.")
        check("policy", policy.get("eligible") is True if isinstance(policy, Mapping) else None, "Policy requirements satisfied.", "Policy eligibility is missing or failed.")
        check("governance", governance.get("production_eligible") is True if isinstance(governance, Mapping) else None, "Governance is production eligible.", "Governance validity is missing or failed.")
        state = lifecycle[-1].get("new_state") if isinstance(lifecycle, list) and lifecycle and isinstance(lifecycle[-1], Mapping) else None
        check("lifecycle", state == "VERIFIED" if state is not None else None, "Lifecycle is VERIFIED.", "Lifecycle is missing or not VERIFIED.")
        check("lineage", isinstance(lineage, Mapping) and all(lineage.get(key) for key in ("pattern_uuid", "validation_uuid", "analytics_uuid", "lineage_reference", "source_baseline_commit")), "Lineage integrity verified.", "Lineage integrity is missing or invalid.")
        stability = analytics.get("stability_classification", analytics.get("stability")) if isinstance(analytics, Mapping) else None
        conflict = analytics.get("conflict_severity") if isinstance(analytics, Mapping) else None
        analytics_ok = isinstance(stability, str) and stability in self.config.allowed_stability and isinstance(conflict, str) and conflict.upper() in _SEVERITY and _SEVERITY[conflict.upper()] <= _SEVERITY[self.config.maximum_conflict_severity]
        check("analytics", analytics_ok if isinstance(analytics, Mapping) else None, "Analytics completeness, stability, and conflict severity accepted.", "Analytics is missing, unstable, or has excessive conflict severity.")
        observed = _timestamp(created_at)
        age_seconds = analytics.get("age_seconds") if isinstance(analytics, Mapping) else None
        if isinstance(age_seconds, (int, float)) and not isinstance(age_seconds, bool) and age_seconds > self.config.maximum_analytics_age_seconds:
            warnings.append({"category": "analytics", "outcome": "WARNING", "reason": "Analytics snapshot is older than the configured freshness threshold."})
        elif isinstance(analytics, Mapping) and created_at and observed is None:
            warnings.append({"category": "analytics", "outcome": "WARNING", "reason": "Analytics snapshot freshness could not be verified."})
        schema_versions = snapshot.get("schema_versions")
        check("schema", isinstance(knowledge, Mapping) and bool(knowledge.get("schema_version")) and isinstance(schema_versions, Mapping) and all(schema_versions.get(k) for k in ("analytics", "governance", "knowledge", "lifecycle")), "Schema versions are complete.", "Schema version evidence is missing.")
        versions = snapshot.get("configuration_versions")
        check("configuration", isinstance(versions, Mapping) and bool(versions.get("analytics")), "Configuration versions are complete.", "Configuration version evidence is missing.")
        failed = [item for item in checks if item["outcome"] == "FAIL"]
        score = max(0, 100 - sum(self.config.check_weights[item["category"]] for item in failed))
        status = "INSUFFICIENT_INFORMATION" if incomplete else ("NOT_QUALIFIED" if failed else ("CONDITIONALLY_QUALIFIED" if warnings else "QUALIFIED"))
        qualified = status == "QUALIFIED"
        identity = str(uuid5(NAMESPACE_URL, sha256(_canonical({"knowledge_uuid": knowledge_uuid, "digest": digest, "config": self.config.canonical_dict(), "status": status, "checks": checks, "warnings": warnings}).encode()).hexdigest()))
        return QualificationReport(identity, knowledge_uuid, qualified, score, status, tuple(item for item in checks if item["outcome"] == "PASS"), tuple(warnings), tuple(failed), digest, self.config.version, created_at if isinstance(created_at, str) else "")

    def qualify(self, control_plane_snapshot: Mapping[str, Any]) -> QualificationReport: return self.evaluate(control_plane_snapshot)
    def explain(self, control_plane_snapshot: Mapping[str, Any]) -> tuple[str, ...]:
        report = self.evaluate(control_plane_snapshot)
        return tuple(f"{item['outcome']}: {item['reason']}" for item in (*report.reasons, *report.warnings, *report.failed_checks))
    def summary(self, control_plane_snapshot: Mapping[str, Any]) -> dict[str, Any]:
        report = self.evaluate(control_plane_snapshot)
        return {"knowledge_uuid": report.knowledge_uuid, "qualified": report.qualified, "qualification_score": report.qualification_score, "status": report.status}
