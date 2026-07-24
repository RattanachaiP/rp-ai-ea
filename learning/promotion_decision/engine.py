"""Pure evaluation over supplied qualification and Control Plane artifacts only."""
from __future__ import annotations

from hashlib import sha256
import json
from typing import Any, Mapping
from uuid import NAMESPACE_URL, uuid5

from .models import PromotionDecisionReport, PromotionPolicyConfig

_SEVERITY = {"NONE": 0, "LOW": 1, "MEDIUM": 2, "HIGH": 3, "CRITICAL": 4}


def _canonical(value: Any) -> str:
    if hasattr(value, "to_dict"):
        value = value.to_dict()
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False, default=str)


def _digest(value: Any) -> str:
    return sha256(_canonical(value).encode("utf-8")).hexdigest()


class PromotionDecisionEngine:
    """Read-only advisory decision maker; it never opens repositories or promotes knowledge."""

    def __init__(self, config: PromotionPolicyConfig | None = None) -> None:
        self.config = config if config is not None else PromotionPolicyConfig()

    @staticmethod
    def _report_value(report: Any) -> Mapping[str, Any] | None:
        value = report.to_dict() if hasattr(report, "to_dict") else report
        return value if isinstance(value, Mapping) else None

    @staticmethod
    def _active_duplicate(snapshot: Mapping[str, Any], knowledge_uuid: str) -> bool:
        candidates = snapshot.get("active_knowledge", snapshot.get("knowledge", ()))
        if not isinstance(candidates, (list, tuple)):
            return False
        for item in candidates:
            if not isinstance(item, Mapping) or item.get("knowledge_uuid") == knowledge_uuid:
                continue
            status = item.get("knowledge_status", item.get("status"))
            if status == "ACTIVE":
                return True
        return False

    def evaluate(self, qualification_report: Any, control_plane_snapshot: Mapping[str, Any],
                 policy_config: PromotionPolicyConfig | None = None) -> PromotionDecisionReport:
        """Return a deterministic decision without reading or modifying any external state."""
        config = policy_config if policy_config is not None else self.config
        if not isinstance(config, PromotionPolicyConfig):
            raise TypeError("PROMOTION_POLICY_CONFIG_REQUIRED")
        qualification = self._report_value(qualification_report)
        snapshot = control_plane_snapshot if isinstance(control_plane_snapshot, Mapping) else {}
        qualification_digest = _digest(qualification_report)
        snapshot_digest = (snapshot.get("snapshot_digest") if isinstance(snapshot.get("snapshot_digest"), str)
                           and snapshot.get("snapshot_digest") else _digest(control_plane_snapshot))
        knowledge_uuid = qualification.get("knowledge_uuid", "UNKNOWN") if qualification else "UNKNOWN"
        reasons: list[dict[str, Any]] = []
        blocks: list[dict[str, Any]] = []
        waiting = False
        manual = False

        def block(code: str, detail: str, *, wait: bool = False, review: bool = False) -> None:
            nonlocal waiting, manual
            blocks.append({"code": code, "detail": detail})
            waiting = waiting or wait
            manual = manual or review

        if not qualification or not isinstance(knowledge_uuid, str) or not knowledge_uuid:
            block("INVALID_QUALIFICATION_REPORT", "Qualification report is missing or invalid.", review=True)
        else:
            status, score = qualification.get("status"), qualification.get("qualification_score")
            if status != "QUALIFIED":
                block("QUALIFICATION_NOT_QUALIFIED", "Qualification status must be QUALIFIED.", review=status in {"INVALID_SNAPSHOT", "INSUFFICIENT_INFORMATION"})
            elif not isinstance(score, int) or isinstance(score, bool) or score < config.minimum_qualification_score:
                block("QUALIFICATION_SCORE_BELOW_THRESHOLD", "Qualification score is below the configured threshold.")
            else:
                reasons.append({"code": "QUALIFICATION_ACCEPTED", "detail": "Qualification status and score satisfy policy."})

        health = snapshot.get("health") if isinstance(snapshot.get("health"), Mapping) else {}
        if config.require_control_plane_healthy and health.get("status") != "READY":
            block("CONTROL_PLANE_UNHEALTHY", "Control Plane health is not READY.", review=not health)
        repository = health.get("subsystems", {}).get("repository", {}) if isinstance(health.get("subsystems"), Mapping) else {}
        if config.require_repository_healthy and repository.get("status", health.get("status")) != "READY":
            block("REPOSITORY_UNHEALTHY", "Repository consistency cannot be verified.")
        if self._active_duplicate(snapshot, knowledge_uuid):
            block("ACTIVE_DUPLICATE_EXISTS", "An ACTIVE knowledge record already exists for this candidate.")
        locks = snapshot.get("promotion_locks", ())
        if locks:
            block("PROMOTION_LOCK_EXISTS", "A promotion lock is present.")
        severity = snapshot.get("conflict_severity", "NONE")
        if not isinstance(severity, str) or severity.upper() not in _SEVERITY:
            block("CONFLICT_SEVERITY_UNKNOWN", "Conflict severity is missing or invalid.", review=True)
        elif _SEVERITY[severity.upper()] > _SEVERITY[config.maximum_conflict_severity]:
            block("CONFLICT_SEVERITY_EXCEEDED", "Conflict severity exceeds the configured threshold.", review=True)
        if config.freeze_window_active or snapshot.get("freeze_window_active") is True:
            block("FREEZE_WINDOW_ACTIVE", "Promotion freeze window is active.", wait=True)
        if not config.promotion_window_open or snapshot.get("promotion_window_open") is False:
            block("PROMOTION_WINDOW_CLOSED", "Promotion window is closed.", wait=True)
        if config.promotion_cooldown_active or snapshot.get("promotion_cooldown_active") is True:
            block("PROMOTION_COOLDOWN_ACTIVE", "Promotion cooldown is active.", wait=True)

        if not blocks:
            decision, decision_status = "PROMOTE", "APPROVED"
            reasons.append({"code": "PROMOTION_ALLOWED", "detail": "All configured promotion conditions are satisfied."})
        elif manual:
            decision, decision_status = "MANUAL_REVIEW", "BLOCKED"
        elif waiting:
            decision, decision_status = "DEFER", "WAITING"
        else:
            decision, decision_status = "REJECT", "DENIED"
        identity = str(uuid5(NAMESPACE_URL, _digest({"knowledge_uuid": knowledge_uuid, "qualification_digest": qualification_digest, "snapshot_digest": snapshot_digest, "policy": config.canonical_dict(), "decision": decision, "status": decision_status, "reasons": reasons, "blocks": blocks})))
        return PromotionDecisionReport(identity, knowledge_uuid, decision, decision_status, tuple(reasons), tuple(blocks), snapshot_digest, qualification_digest, config.version, config.evaluation_timestamp)

    def decision(self, qualification_report: Any, control_plane_snapshot: Mapping[str, Any], policy_config: PromotionPolicyConfig | None = None) -> PromotionDecisionReport:
        return self.evaluate(qualification_report, control_plane_snapshot, policy_config)

    def explain(self, qualification_report: Any, control_plane_snapshot: Mapping[str, Any], policy_config: PromotionPolicyConfig | None = None) -> tuple[str, ...]:
        report = self.evaluate(qualification_report, control_plane_snapshot, policy_config)
        return tuple(f"{item['code']}: {item['detail']}" for item in (*report.reason, *report.blocking_conditions))

    def summary(self, qualification_report: Any, control_plane_snapshot: Mapping[str, Any], policy_config: PromotionPolicyConfig | None = None) -> dict[str, Any]:
        report = self.evaluate(qualification_report, control_plane_snapshot, policy_config)
        return {"knowledge_uuid": report.knowledge_uuid, "decision": report.decision, "decision_status": report.decision_status, "blocking_conditions": len(report.blocking_conditions)}
