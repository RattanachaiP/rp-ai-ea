"""Regression coverage for the PR155 advisory-only promotion decision boundary."""
from __future__ import annotations

import ast
from dataclasses import replace
import inspect

import pytest

from learning.promotion_decision import (
    PromotionDecisionEngine, PromotionDecisionRepository, PromotionPolicyConfig,
)


def qualification(**overrides):
    result = {"knowledge_uuid": "knowledge-1", "status": "QUALIFIED", "qualification_score": 100}
    result.update(overrides)
    return result


def snapshot(**overrides):
    result = {"snapshot_digest": "a" * 64, "health": {"status": "READY", "subsystems": {"repository": {"status": "READY"}}}, "knowledge": [], "conflict_severity": "LOW"}
    result.update(overrides)
    return result


def test_qualified_promotion_and_deterministic_replay():
    engine = PromotionDecisionEngine()
    first = engine.evaluate(qualification(), snapshot())
    second = engine.decision(qualification(), snapshot())
    assert (first.decision, first.decision_status) == ("PROMOTE", "APPROVED")
    assert first.to_dict() == second.to_dict()
    assert engine.summary(qualification(), snapshot())["decision"] == "PROMOTE"


def test_duplicate_active_is_denied():
    report = PromotionDecisionEngine().evaluate(qualification(), snapshot(knowledge=[{"knowledge_uuid": "other", "status": "ACTIVE"}]))
    assert (report.decision, report.decision_status) == ("REJECT", "DENIED")
    assert report.blocking_conditions[0]["code"] == "ACTIVE_DUPLICATE_EXISTS"


@pytest.mark.parametrize("change, code", [
    ({"promotion_window_open": False}, "PROMOTION_WINDOW_CLOSED"),
    ({"freeze_window_active": True}, "FREEZE_WINDOW_ACTIVE"),
    ({"promotion_cooldown_active": True}, "PROMOTION_COOLDOWN_ACTIVE"),
])
def test_temporal_blocks_defer(change, code):
    report = PromotionDecisionEngine().evaluate(qualification(), snapshot(**change))
    assert (report.decision, report.decision_status) == ("DEFER", "WAITING")
    assert report.blocking_conditions[0]["code"] == code


def test_unhealthy_repository_is_denied():
    item = snapshot(); item["health"]["subsystems"]["repository"]["status"] = "FAILED"
    report = PromotionDecisionEngine().evaluate(qualification(), item)
    assert report.decision == "REJECT"
    assert {block["code"] for block in report.blocking_conditions} >= {"REPOSITORY_UNHEALTHY"}


def test_report_is_immutable_and_storage_is_append_only(tmp_path):
    report = PromotionDecisionEngine().evaluate(qualification(), snapshot())
    with pytest.raises(TypeError): report.reason[0]["code"] = "changed"
    repository = PromotionDecisionRepository(tmp_path)
    assert repository.save(report) == repository.save(report)
    with pytest.raises(FileExistsError, match="IMMUTABLE"):
        repository.storage.write(replace(report, decision="REJECT", decision_status="DENIED"))


def test_dependency_audit_has_no_forbidden_subsystem_imports():
    source = inspect.getsource(__import__("learning.promotion_decision.engine", fromlist=["PromotionDecisionEngine"]))
    imported = {node.module for node in ast.walk(ast.parse(source)) if isinstance(node, ast.ImportFrom) and node.module}
    assert not {"learning.control_plane", "learning.governance", "learning.lifecycle", "learning.analytics", "learning.policy"} & imported
