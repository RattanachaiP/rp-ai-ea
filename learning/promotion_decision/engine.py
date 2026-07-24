"""Pure evaluation over supplied qualification and Control Plane artifacts only."""
from __future__ import annotations

from datetime import datetime
from hashlib import sha256
import json
from typing import Any, Mapping
from uuid import NAMESPACE_URL, UUID, uuid5

from .models import PromotionDecisionReport, PromotionPolicyConfig

_SEVERITY = {"NONE": 0, "LOW": 1, "MEDIUM": 2, "HIGH": 3, "CRITICAL": 4}


def _canonical(value: Any) -> str:
    if hasattr(value, "to_dict"):
        value = value.to_dict()
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False, default=str)


def _digest(value: Any) -> str:
    return sha256(_canonical(value).encode("utf-8")).hexdigest()


def _timestamp(value: Any) -> datetime | None:
    if not isinstance(value, str) or not value:
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    return parsed if parsed.tzinfo is not None else None


class PromotionDecisionEngine:
    """Read-only advisory decision maker; it never opens repositories or promotes knowledge."""

    def __init__(self, config: PromotionPolicyConfig | None = None) -> None:
        self.config = config if config is not None else PromotionPolicyConfig()

    @staticmethod
    def _report_value(report: Any) -> Mapping[str, Any] | None:
        value = report.to_dict() if hasattr(report, "to_dict") else report
        return value if isinstance(value, Mapping) else None

    @staticmethod
    def _snapshot_digest(snapshot: Mapping[str, Any]) -> tuple[str, bool]:
        provided = snapshot.get("snapshot_digest")
        if not isinstance(provided, str) or not provided:
            return _digest(snapshot), False
        body = dict(snapshot)
        body.pop("snapshot_digest", None)
        computed = _digest(body)
        return computed, provided == computed

    @staticmethod
    def _candidate(snapshot: Mapping[str, Any], knowledge_uuid: str) -> Mapping[str, Any] | None:
        entries = snapshot.get("knowledge")
        if not isinstance(entries, (list, tuple)):
            return None
        matches = [item for item in entries if isinstance(item, Mapping) and item.get("knowledge_uuid") == knowledge_uuid]
        return matches[0] if len(matches) == 1 else None

    @staticmethod
    def _semantic_key(item: Mapping[str, Any] | None) -> str | None:
        if not isinstance(item, Mapping):
            return None
        for key in ("promotion_key", "semantic_key", "pattern_uuid", "lineage_reference"):
            value = item.get(key)
            if isinstance(value, str) and value:
                return f"{key}:{value}"
        observations = item.get("observations")
        if isinstance(observations, Mapping):
            for observation_name in ("lineage", "knowledge"):
                observation = observations.get(observation_name)
                value = observation.get("value") if isinstance(observation, Mapping) else None
                if isinstance(value, Mapping):
                    for key in ("promotion_key", "semantic_key", "pattern_uuid", "lineage_reference"):
                        found = value.get(key)
                        if isinstance(found, str) and found:
                            return f"{key}:{found}"
        return None

    @classmethod
    def _active_duplicate(cls, snapshot: Mapping[str, Any], candidate: Mapping[str, Any] | None) -> bool | None:
        candidate_key = cls._semantic_key(candidate)
        if candidate_key is None:
            return None
        entries = snapshot.get("active_knowledge", ())
        if not isinstance(entries, (list, tuple)):
            return None
        candidate_uuid = candidate.get("knowledge_uuid") if isinstance(candidate, Mapping) else None
        for item in entries:
            if not isinstance(item, Mapping) or item.get("knowledge_uuid") == candidate_uuid:
                continue
            status = item.get("knowledge_status", item.get("status"))
            if status == "ACTIVE" and cls._semantic_key(item) == candidate_key:
                return True
        return False

    @staticmethod
    def _active_lock(snapshot: Mapping[str, Any], knowledge_uuid: str) -> bool | None:
        locks = snapshot.get("promotion_locks", ())
        if not isinstance(locks, (list, tuple)):
            return None
        relevant = [item for item in locks if isinstance(item, Mapping) and item.get("knowledge_uuid") == knowledge_uuid]
        if any(item.get("active") is True for item in relevant):
            return True
        if any("active" not in item for item in relevant):
            return None
        return False

    @staticmethod
    def _conflict_severity(snapshot: Mapping[str, Any]) -> str | None:
        analytics = snapshot.get("analytics_summary")
        if isinstance(analytics, Mapping) and analytics.get("status") == "READY":
            value = analytics.get("value")
            severity = value.get("conflict_severity") if isinstance(value, Mapping) else None
            return severity.upper() if isinstance(severity, str) and severity.upper() in _SEVERITY else None
        severity = snapshot.get("conflict_severity")
        return severity.upper() if isinstance(severity, str) and severity.upper() in _SEVERITY else None

    def evaluate(self, qualification_report: Any, control_plane_snapshot: Mapping[str, Any],
                 policy_config: PromotionPolicyConfig | None = None) -> PromotionDecisionReport:
        """Return a deterministic advisory decision without external reads or mutations."""
        config = policy_config if policy_config is not None else self.config
        if not isinstance(config, PromotionPolicyConfig):
            raise TypeError("PROMOTION_POLICY_CONFIG_REQUIRED")

        qualification = self._report_value(qualification_report)
        snapshot = control_plane_snapshot if isinstance(control_plane_snapshot, Mapping) else {}
        qualification_digest = _digest(qualification_report)
        snapshot_digest, snapshot_integrity_ok = self._snapshot_digest(snapshot)
        knowledge_uuid = qualification.get("knowledge_uuid", "UNKNOWN") if qualification else "UNKNOWN"
        reasons: list[dict[str, Any]] = []
        blocks: list[dict[str, Any]] = []
        priorities: set[str] = set()

        def block(code: str, detail: str, priority: str) -> None:
            blocks.append({"code": code, "detail": detail, "priority": priority})
            priorities.add(priority)

        required_report_fields = {
            "qualification_uuid", "knowledge_uuid", "qualified", "qualification_score", "status",
            "control_plane_digest", "configuration_version", "failed_checks", "unknown_checks",
        }
        valid_report = qualification is not None and required_report_fields.issubset(qualification)
        if valid_report:
            try:
                UUID(str(qualification["qualification_uuid"]))
            except (ValueError, TypeError, AttributeError):
                valid_report = False
        if not valid_report or not isinstance(knowledge_uuid, str) or not knowledge_uuid:
            block("INVALID_QUALIFICATION_REPORT", "Qualification report contract is missing or invalid.", "MANUAL")
        else:
            score = qualification.get("qualification_score")
            consistent = (
                qualification.get("status") == "QUALIFIED"
                and qualification.get("qualified") is True
                and isinstance(score, int) and not isinstance(score, bool) and 0 <= score <= 100
                and not qualification.get("failed_checks")
                and not qualification.get("unknown_checks")
            )
            if not consistent:
                block("QUALIFICATION_NOT_QUALIFIED", "Qualification report is not internally consistent and QUALIFIED.", "REJECT")
            elif score < config.minimum_qualification_score:
                block("QUALIFICATION_SCORE_BELOW_THRESHOLD", "Qualification score is below the configured threshold.", "REJECT")
            else:
                reasons.append({"code": "QUALIFICATION_ACCEPTED", "detail": "Qualification status, boolean, score, and checks satisfy policy."})

        if not snapshot_integrity_ok:
            block("INVALID_CONTROL_PLANE_SNAPSHOT", "Snapshot digest is missing or does not match its contents.", "MANUAL")

        candidate = self._candidate(snapshot, knowledge_uuid)
        if candidate is None:
            block("KNOWLEDGE_SNAPSHOT_BINDING_MISSING", "Snapshot must contain exactly one entry matching the qualification knowledge UUID.", "MANUAL")
        if valid_report and qualification.get("control_plane_digest") != snapshot_digest:
            block("QUALIFICATION_SNAPSHOT_DIGEST_MISMATCH", "Qualification report is not bound to this Control Plane snapshot.", "MANUAL")

        health = snapshot.get("health") if isinstance(snapshot.get("health"), Mapping) else {}
        if config.require_control_plane_healthy and health.get("status") != "READY":
            block("CONTROL_PLANE_UNHEALTHY", "Control Plane health is not READY.", "MANUAL" if not health else "REJECT")
        subsystems = health.get("subsystems") if isinstance(health.get("subsystems"), Mapping) else {}
        repository = subsystems.get("repository") if isinstance(subsystems.get("repository"), Mapping) else None
        if config.require_repository_healthy and (repository is None or repository.get("status") != "READY"):
            block("REPOSITORY_UNHEALTHY", "Repository health evidence is missing or not READY.", "MANUAL" if repository is None else "REJECT")

        duplicate = self._active_duplicate(snapshot, candidate)
        if duplicate is True:
            block("ACTIVE_DUPLICATE_EXISTS", "An ACTIVE record with the same semantic identity already exists.", "REJECT")
        elif duplicate is None:
            block("DUPLICATE_EVIDENCE_UNKNOWN", "Duplicate identity evidence is missing or malformed.", "MANUAL")

        active_lock = self._active_lock(snapshot, knowledge_uuid)
        if active_lock is True:
            block("PROMOTION_LOCK_EXISTS", "An active promotion lock exists for this knowledge record.", "REJECT")
        elif active_lock is None:
            block("PROMOTION_LOCK_EVIDENCE_UNKNOWN", "Promotion lock evidence is malformed.", "MANUAL")

        severity = self._conflict_severity(snapshot)
        if severity is None:
            block("CONFLICT_SEVERITY_UNKNOWN", "Conflict severity evidence is missing or invalid.", "MANUAL")
        elif _SEVERITY[severity] > _SEVERITY[config.maximum_conflict_severity]:
            block("CONFLICT_SEVERITY_EXCEEDED", "Conflict severity exceeds the configured threshold.", "REJECT")

        now = _timestamp(config.evaluation_timestamp)
        if any((config.freeze_until, config.promotion_window_start, config.promotion_window_end, config.cooldown_until)) and now is None:
            block("EVALUATION_TIMESTAMP_REQUIRED", "Temporal policy boundaries require a timezone-aware evaluation timestamp.", "MANUAL")
        if config.freeze_window_active or (now is not None and _timestamp(config.freeze_until) is not None and now < _timestamp(config.freeze_until)):
            block("FREEZE_WINDOW_ACTIVE", "Promotion freeze window is active.", "DEFER")
        window_start, window_end = _timestamp(config.promotion_window_start), _timestamp(config.promotion_window_end)
        if (not config.promotion_window_open
                or (now is not None and window_start is not None and now < window_start)
                or (now is not None and window_end is not None and now > window_end)):
            block("PROMOTION_WINDOW_CLOSED", "Promotion window is closed.", "DEFER")
        cooldown_until = _timestamp(config.cooldown_until)
        if config.promotion_cooldown_active or (now is not None and cooldown_until is not None and now < cooldown_until):
            block("PROMOTION_COOLDOWN_ACTIVE", "Promotion cooldown is active.", "DEFER")

        if not blocks:
            decision, decision_status = "PROMOTE", "APPROVED"
            reasons.append({"code": "PROMOTION_ALLOWED", "detail": "All configured advisory conditions are satisfied."})
        elif "MANUAL" in priorities:
            decision, decision_status = "MANUAL_REVIEW", "BLOCKED"
        elif "REJECT" in priorities:
            decision, decision_status = "REJECT", "DENIED"
        else:
            decision, decision_status = "DEFER", "WAITING"

        identity = str(uuid5(NAMESPACE_URL, _digest({
            "knowledge_uuid": knowledge_uuid,
            "qualification_digest": qualification_digest,
            "snapshot_digest": snapshot_digest,
            "policy": config.canonical_dict(),
            "decision": decision,
            "status": decision_status,
            "reasons": reasons,
            "blocks": blocks,
        })))
        configuration_digest = _digest(config.canonical_dict())
        unsigned = {
            "decision_uuid": identity, "knowledge_uuid": knowledge_uuid, "decision": decision,
            "decision_status": decision_status, "reason": reasons,
            "blocking_conditions": blocks, "snapshot_digest": snapshot_digest,
            "qualification_digest": qualification_digest, "policy_version": config.version,
            "created_at": config.evaluation_timestamp, "schema_version": "1.0",
            "configuration_digest": configuration_digest,
        }
        signature = _digest(unsigned)
        return PromotionDecisionReport(
            identity, knowledge_uuid, decision, decision_status, tuple(reasons), tuple(blocks),
            snapshot_digest, qualification_digest, config.version, config.evaluation_timestamp,
            "1.0", configuration_digest, signature,
        )

    def decision(self, qualification_report: Any, control_plane_snapshot: Mapping[str, Any], policy_config: PromotionPolicyConfig | None = None) -> PromotionDecisionReport:
        return self.evaluate(qualification_report, control_plane_snapshot, policy_config)

    def explain(self, qualification_report: Any, control_plane_snapshot: Mapping[str, Any], policy_config: PromotionPolicyConfig | None = None) -> tuple[str, ...]:
        report = self.evaluate(qualification_report, control_plane_snapshot, policy_config)
        return tuple(f"{item['code']}: {item['detail']}" for item in (*report.reason, *report.blocking_conditions))

    def summary(self, qualification_report: Any, control_plane_snapshot: Mapping[str, Any], policy_config: PromotionPolicyConfig | None = None) -> dict[str, Any]:
        report = self.evaluate(qualification_report, control_plane_snapshot, policy_config)
        return {"knowledge_uuid": report.knowledge_uuid, "decision": report.decision, "decision_status": report.decision_status, "blocking_conditions": len(report.blocking_conditions)}