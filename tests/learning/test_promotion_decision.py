"""Regression coverage for the PR155 advisory-only promotion decision boundary."""
from __future__ import annotations

import ast
from dataclasses import replace
import hashlib
import inspect
import json

import pytest

from learning.promotion_decision import (
    PromotionDecisionEngine, PromotionDecisionRepository, PromotionPolicyConfig,
)


def digest_snapshot(value):
    body = dict(value)
    body.pop("snapshot_digest", None)
    value["snapshot_digest"] = hashlib.sha256(
        json.dumps(body, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    return value


def snapshot(**overrides):
    result = {
        "health": {"status": "READY", "subsystems": {"repository": {"status": "READY"}}},
        "knowledge": [{"knowledge_uuid": "knowledge-1", "pattern_uuid": "pattern-1", "status": "COMPLETE"}],
        "active_knowledge": [],
        "promotion_locks": [],
        "analytics_summary": {"status": "READY", "value": {"conflict_severity": "LOW"}},
    }
    result.update(overrides)
    return digest_snapshot(result)


def qualification(control_plane_digest=None, **overrides):
    result = {
        "qualification_uuid": "00000000-0000-4000-8000-000000000155",
        "knowledge_uuid": "knowledge-1",
        "qualified": True,
        "qualification_score": 100,
        "status": "QUALIFIED",
        "failed_checks": [],
        "unknown_checks": [],
        "control_plane_digest": control_plane_digest or snapshot()["snapshot_digest"],
        "configuration_version": "1.0",
    }
    result.update(overrides)
    return result


def artifacts(**snapshot_overrides):
    plane = snapshot(**snapshot_overrides)
    return qualification(plane["snapshot_digest"]), plane


def test_qualified_promotion_and_deterministic_replay():
    report_input, plane = artifacts()
    engine = PromotionDecisionEngine()
    first = engine.evaluate(report_input, plane)
    second = engine.decision(report_input, plane)
    assert (first.decision, first.decision_status) == ("PROMOTE", "APPROVED")
    assert first.to_dict() == second.to_dict()
    assert engine.summary(report_input, plane)["decision"] == "PROMOTE"


def test_tampered_snapshot_requires_manual_review():
    report_input, plane = artifacts()
    plane["health"]["status"] = "FAILED"
    report = PromotionDecisionEngine().evaluate(report_input, plane)
    assert (report.decision, report.decision_status) == ("MANUAL_REVIEW", "BLOCKED")
    assert "INVALID_CONTROL_PLANE_SNAPSHOT" in {item["code"] for item in report.blocking_conditions}


def test_qualification_is_bound_to_snapshot_digest_and_uuid():
    report_input, plane = artifacts()
    mismatch = dict(report_input, control_plane_digest="f" * 64)
    report = PromotionDecisionEngine().evaluate(mismatch, plane)
    assert report.decision == "MANUAL_REVIEW"
    assert "QUALIFICATION_SNAPSHOT_DIGEST_MISMATCH" in {item["code"] for item in report.blocking_conditions}

    other = dict(report_input, knowledge_uuid="knowledge-2")
    report = PromotionDecisionEngine().evaluate(other, plane)
    assert report.decision == "MANUAL_REVIEW"
    assert "KNOWLEDGE_SNAPSHOT_BINDING_MISSING" in {item["code"] for item in report.blocking_conditions}


def test_forged_or_inconsistent_qualification_cannot_promote():
    report_input, plane = artifacts()
    forged = dict(report_input, qualified=False)
    report = PromotionDecisionEngine().evaluate(forged, plane)
    assert (report.decision, report.decision_status) == ("REJECT", "DENIED")
    assert "QUALIFICATION_NOT_QUALIFIED" in {item["code"] for item in report.blocking_conditions}

    missing_contract = {"knowledge_uuid": "knowledge-1", "status": "QUALIFIED", "qualification_score": 100}
    report = PromotionDecisionEngine().evaluate(missing_contract, plane)
    assert report.decision == "MANUAL_REVIEW"


def test_duplicate_requires_same_semantic_identity():
    report_input, plane = artifacts(active_knowledge=[
        {"knowledge_uuid": "other", "pattern_uuid": "pattern-2", "status": "ACTIVE"},
    ])
    assert PromotionDecisionEngine().evaluate(report_input, plane).decision == "PROMOTE"

    report_input, plane = artifacts(active_knowledge=[
        {"knowledge_uuid": "other", "pattern_uuid": "pattern-1", "status": "ACTIVE"},
    ])
    report = PromotionDecisionEngine().evaluate(report_input, plane)
    assert (report.decision, report.decision_status) == ("REJECT", "DENIED")
    assert "ACTIVE_DUPLICATE_EXISTS" in {item["code"] for item in report.blocking_conditions}


def test_locks_are_candidate_scoped_and_schema_checked():
    report_input, plane = artifacts(promotion_locks=[
        {"knowledge_uuid": "other", "active": True},
    ])
    assert PromotionDecisionEngine().evaluate(report_input, plane).decision == "PROMOTE"

    report_input, plane = artifacts(promotion_locks=[
        {"knowledge_uuid": "knowledge-1", "active": True},
    ])
    assert PromotionDecisionEngine().evaluate(report_input, plane).decision == "REJECT"

    report_input, plane = artifacts(promotion_locks="malformed")
    assert PromotionDecisionEngine().evaluate(report_input, plane).decision == "MANUAL_REVIEW"


def test_missing_conflict_evidence_is_fail_closed():
    report_input, plane = artifacts(analytics_summary={"status": "DEGRADED"})
    report = PromotionDecisionEngine().evaluate(report_input, plane)
    assert report.decision == "MANUAL_REVIEW"
    assert "CONFLICT_SEVERITY_UNKNOWN" in {item["code"] for item in report.blocking_conditions}


@pytest.mark.parametrize("config, code", [
    (PromotionPolicyConfig(promotion_window_open=False), "PROMOTION_WINDOW_CLOSED"),
    (PromotionPolicyConfig(freeze_window_active=True), "FREEZE_WINDOW_ACTIVE"),
    (PromotionPolicyConfig(promotion_cooldown_active=True), "PROMOTION_COOLDOWN_ACTIVE"),
    (PromotionPolicyConfig(evaluation_timestamp="2026-07-24T00:00:00Z", cooldown_until="2026-07-25T00:00:00Z"), "PROMOTION_COOLDOWN_ACTIVE"),
])
def test_temporal_blocks_defer(config, code):
    report_input, plane = artifacts()
    report = PromotionDecisionEngine(config).evaluate(report_input, plane)
    assert (report.decision, report.decision_status) == ("DEFER", "WAITING")
    assert code in {item["code"] for item in report.blocking_conditions}


def test_permanent_rejection_precedes_temporary_defer():
    report_input, plane = artifacts()
    report_input["qualified"] = False
    report = PromotionDecisionEngine(PromotionPolicyConfig(freeze_window_active=True)).evaluate(report_input, plane)
    assert (report.decision, report.decision_status) == ("REJECT", "DENIED")


def test_manual_review_precedes_reject_and_defer():
    report_input, plane = artifacts()
    plane["snapshot_digest"] = "tampered"
    report_input["qualified"] = False
    report = PromotionDecisionEngine(PromotionPolicyConfig(freeze_window_active=True)).evaluate(report_input, plane)
    assert (report.decision, report.decision_status) == ("MANUAL_REVIEW", "BLOCKED")


def test_unhealthy_repository_is_denied():
    report_input, plane = artifacts()
    plane["health"]["subsystems"]["repository"]["status"] = "FAILED"
    plane = digest_snapshot(plane)
    report_input["control_plane_digest"] = plane["snapshot_digest"]
    report = PromotionDecisionEngine().evaluate(report_input, plane)
    assert report.decision == "REJECT"
    assert "REPOSITORY_UNHEALTHY" in {item["code"] for item in report.blocking_conditions}


def test_policy_timestamp_validation():
    with pytest.raises(ValueError, match="INVALID_PROMOTION_POLICY_CONFIG"):
        PromotionPolicyConfig(evaluation_timestamp="2026-07-24")
    with pytest.raises(ValueError, match="INVALID_PROMOTION_POLICY_CONFIG"):
        PromotionPolicyConfig(promotion_window_start="2026-07-25T00:00:00Z", promotion_window_end="2026-07-24T00:00:00Z")


def test_report_is_immutable_and_storage_is_append_only(tmp_path):
    report_input, plane = artifacts()
    report = PromotionDecisionEngine().evaluate(report_input, plane)
    with pytest.raises(TypeError):
        report.reason[0]["code"] = "changed"
    repository = PromotionDecisionRepository(tmp_path)
    assert repository.save(report) == repository.save(report)
    with pytest.raises(FileExistsError, match="IMMUTABLE"):
        repository.storage.write(replace(report, decision="REJECT", decision_status="DENIED"))


def test_dependency_audit_has_no_forbidden_subsystem_imports():
    source = inspect.getsource(__import__("learning.promotion_decision.engine", fromlist=["PromotionDecisionEngine"]))
    imported = {node.module for node in ast.walk(ast.parse(source)) if isinstance(node, ast.ImportFrom) and node.module}
    assert not {"learning.control_plane", "learning.governance", "learning.lifecycle", "learning.analytics", "learning.policy"} & imported
    forbidden_methods = {"save", "append", "transition", "promote", "retire", "execute", "write", "delete"}
    assert not forbidden_methods & set(dir(PromotionDecisionEngine))