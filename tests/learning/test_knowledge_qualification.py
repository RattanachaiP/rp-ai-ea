from __future__ import annotations

from dataclasses import replace
import hashlib
import json

import pytest

from learning.control_plane import KnowledgeControlPlane
from learning.governance import GovernanceRepository, KnowledgeGovernance
from learning.knowledge import Knowledge, KnowledgeRepository
from learning.lifecycle import LifecycleRepository, transition
from learning.qualification import KnowledgeQualificationEngine, QualificationConfig, QualificationRepository


class AnalyticsProvider:
    def latest(self):
        return {
            "analytics_version": "1.0",
            "configuration_version": "1.0",
            "status": "READY",
            "stability_classification": "STABLE",
            "conflict_severity": "LOW",
            "timestamp": "2026-07-24T00:00:00Z",
        }


class PolicyProvider:
    def get_policy_result(self, knowledge_uuid=None):
        return {"knowledge_uuid": knowledge_uuid, "eligible": True}


def _plane(tmp_path):
    knowledge_repo = KnowledgeRepository(tmp_path)
    record = Knowledge.create(
        knowledge_uuid="knowledge-1",
        pattern_uuid="pattern-1",
        validation_uuid="validation-1",
        sample_count=40,
        verified_win_rate=.5,
        average_rr=1,
        created_timestamp="2026-07-24T00:00:00Z",
    )
    knowledge_repo.save(record)
    governance = GovernanceRepository(tmp_path)
    governance.save(KnowledgeGovernance(
        "knowledge-1", "pattern-1", "validation-1", "analytics-1", "a" * 40,
        "1.0", "1.0", "ACTIVE", "pattern-1/1", True,
        "2026-07-24T00:00:00Z",
    ))
    lifecycle = LifecycleRepository(tmp_path)
    transition(
        repository=lifecycle,
        knowledge_uuid="knowledge-1",
        previous_state="DRAFT",
        new_state="VERIFIED",
        triggering_component="test",
        reason="test",
        governance_version="1.0",
        lifecycle_version="1.0",
        timestamp="2026-07-24T00:00:01Z",
        transition_uuid="00000000-0000-4000-8000-000000000001",
    )
    return KnowledgeControlPlane(
        tmp_path,
        knowledge_repository=knowledge_repo,
        governance_repository=governance,
        lifecycle_repository=lifecycle,
        analytics_repository=AnalyticsProvider(),
        policy_provider=PolicyProvider(),
        policy_schema_version="1.0",
        policy_configuration_version="1.0",
    ), record


def digest(snapshot):
    body = dict(snapshot)
    body.pop("snapshot_digest", None)
    snapshot["snapshot_digest"] = hashlib.sha256(
        json.dumps(body, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    return snapshot


def snapshot(tmp_path):
    plane, record = _plane(tmp_path)
    result = plane.get_snapshot(record.knowledge_uuid)
    result["knowledge"][0]["observations"]["policy"]["value"] = {"eligible": True}
    return digest(result)


def test_qualified_and_deterministic_replay(tmp_path):
    engine = KnowledgeQualificationEngine()
    first = engine.qualify(snapshot(tmp_path))
    second = engine.evaluate(snapshot(tmp_path))
    assert first.status == "QUALIFIED"
    assert first.qualified is True
    assert first.to_dict() == second.to_dict()
    assert engine.summary(snapshot(tmp_path))["qualification_score"] == 100
    assert any(line.startswith("PASS:") for line in engine.explain(snapshot(tmp_path)))


@pytest.mark.parametrize("path", [
    ("knowledge", 0, "observations", "policy", "value", "eligible"),
    ("knowledge", 0, "observations", "governance", "value", "production_eligible"),
])
def test_policy_and_governance_failure_not_qualified(tmp_path, path):
    item = snapshot(tmp_path)
    target = item
    for key in path[:-1]:
        target = target[key]
    target[path[-1]] = False
    report = KnowledgeQualificationEngine().evaluate(digest(item))
    assert report.status == "NOT_QUALIFIED"
    assert not report.qualified
    assert report.unknown_checks == ()


def test_lifecycle_and_lineage_failures(tmp_path):
    item = snapshot(tmp_path)
    item["knowledge"][0]["observations"]["lifecycle"]["value"][-1]["new_state"] = "DRAFT"
    item["knowledge"][0]["observations"]["lineage"]["value"].pop("analytics_uuid")
    report = KnowledgeQualificationEngine().evaluate(digest(item))
    assert report.status == "NOT_QUALIFIED"
    assert {failure["category"] for failure in report.failed_checks} >= {"lifecycle", "lineage"}


def test_missing_analytics_is_unknown_not_failed(tmp_path):
    item = snapshot(tmp_path)
    item["analytics_summary"] = {"status": "DEGRADED", "error": "NOT_FOUND"}
    item["complete"] = False
    report = KnowledgeQualificationEngine().evaluate(digest(item))
    assert report.status == "INSUFFICIENT_INFORMATION"
    assert {check["category"] for check in report.unknown_checks} >= {"analytics"}
    assert "analytics" not in {check["category"] for check in report.failed_checks}


def test_invalid_snapshot_and_immutable_report(tmp_path):
    item = snapshot(tmp_path)
    item["snapshot_digest"] = "wrong"
    assert KnowledgeQualificationEngine().evaluate(item).status == "INVALID_SNAPSHOT"
    report = KnowledgeQualificationEngine(QualificationConfig(version="2.0")).evaluate(snapshot(tmp_path))
    repo = QualificationRepository(tmp_path)
    assert repo.save(report) == repo.save(report)
    with pytest.raises(FileExistsError, match="IMMUTABLE"):
        repo.storage.write(replace(report, qualification_score=0))
    assert report.configuration_version == "2.0"


def test_old_analytics_is_conditionally_qualified(tmp_path):
    item = snapshot(tmp_path)
    item["analytics_summary"]["value"]["age_seconds"] = 86401
    report = KnowledgeQualificationEngine().evaluate(digest(item))
    assert report.status == "CONDITIONALLY_QUALIFIED"
    assert report.qualified is False
    assert report.warnings[0]["category"] == "analytics"


def test_deterministic_timestamp_freshness(tmp_path):
    config = QualificationConfig(evaluation_timestamp="2026-07-26T00:00:01Z")
    report = KnowledgeQualificationEngine(config).evaluate(snapshot(tmp_path))
    assert report.status == "CONDITIONALLY_QUALIFIED"
    assert report.warnings[0]["category"] == "analytics"


def test_config_rejects_invalid_severity_and_timestamp():
    with pytest.raises(ValueError, match="INVALID_QUALIFICATION_CONFIG"):
        QualificationConfig(maximum_conflict_severity="IMPOSSIBLE")
    with pytest.raises(ValueError, match="INVALID_QUALIFICATION_CONFIG"):
        QualificationConfig(evaluation_timestamp="not-a-time")


def test_missing_policy_versions_prevents_qualification(tmp_path):
    item = snapshot(tmp_path)
    item["schema_versions"]["policy"] = None
    item["configuration_versions"]["policy"] = None
    report = KnowledgeQualificationEngine().evaluate(digest(item))
    assert report.status == "NOT_QUALIFIED"
    assert {failure["category"] for failure in report.failed_checks} >= {"schema", "configuration"}


def test_falsy_config_is_not_replaced(tmp_path):
    class FalsyConfig(QualificationConfig):
        def __bool__(self):
            return False

    config = FalsyConfig(version="falsy")
    engine = KnowledgeQualificationEngine(config)
    assert engine.config is config
