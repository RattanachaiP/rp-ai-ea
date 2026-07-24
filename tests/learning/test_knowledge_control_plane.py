from __future__ import annotations

import pytest

from learning.control_plane import KnowledgeControlPlane
from learning.governance import GovernanceRepository, KnowledgeGovernance
from learning.knowledge import Knowledge, KnowledgeRepository
from learning.lifecycle import LifecycleRepository, transition


class AnalyticsProvider:
    def latest(self):
        return {"analytics_version": "1.0", "configuration_version": "1.0", "status": "READY"}


class PolicyProvider:
    def get_policy_result(self, knowledge_uuid=None):
        return {"knowledge_uuid": knowledge_uuid, "eligible": True}


def _plane(tmp_path, **overrides):
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
        "1.0", "1.0", "DRAFT", "pattern-1/1", False,
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
    providers = {
        "knowledge_repository": knowledge_repo,
        "governance_repository": governance,
        "lifecycle_repository": lifecycle,
        "analytics_repository": AnalyticsProvider(),
        "policy_provider": PolicyProvider(),
        **overrides,
    }
    return KnowledgeControlPlane(tmp_path, **providers), record


def test_snapshot_is_deterministic_and_uses_structured_observations(tmp_path):
    plane, record = _plane(tmp_path)
    first = plane.get_snapshot(record.knowledge_uuid)
    assert first == plane.get_snapshot(record.knowledge_uuid)
    entry = first["knowledge"][0]
    assert entry["status"] == "COMPLETE"
    assert entry["observations"]["knowledge"]["value"]["knowledge_uuid"] == record.knowledge_uuid
    assert entry["observations"]["lifecycle"]["value"][0]["new_state"] == "VERIFIED"
    assert first["complete"] is True
    assert first["eligible_for_downstream_use"] is True
    assert set(first) >= {"snapshot_status", "analytics_summary", "configuration_versions", "health", "repository_version", "schema_versions", "snapshot_digest"}


def test_missing_requested_uuid_is_explicitly_incomplete(tmp_path):
    plane, _ = _plane(tmp_path)
    snapshot = plane.get_snapshot("missing")
    entry = snapshot["knowledge"][0]
    assert snapshot["complete"] is False
    assert snapshot["eligible_for_downstream_use"] is False
    assert entry["status"] == "INCOMPLETE"
    assert entry["observations"]["knowledge"]["status"] == "DEGRADED"
    assert entry["observations"]["knowledge"]["error"] == "NOT_FOUND"


def test_repository_failure_never_becomes_empty_ready_snapshot(tmp_path):
    class BrokenRepository:
        def query(self):
            raise RuntimeError("unavailable")
        def load(self, _):
            raise RuntimeError("unavailable")

    plane, _ = _plane(tmp_path, knowledge_repository=BrokenRepository())
    snapshot = plane.get_snapshot()
    assert snapshot["complete"] is False
    assert snapshot["health"]["subsystems"]["repository"] == {"status": "FAILED", "error": "PROVIDER_FAILURE"}


def test_health_isolates_failure_and_optional_policy_is_explicit(tmp_path):
    class BrokenGovernance:
        def load(self, _):
            raise RuntimeError("unavailable")
        def query(self):
            raise RuntimeError("unavailable")

    plane, record = _plane(tmp_path, governance_repository=BrokenGovernance(), policy_provider=None)
    assert plane.get_knowledge(record.knowledge_uuid)["knowledge_uuid"] == record.knowledge_uuid
    health = plane.get_health()
    assert health["status"] == "FAILED"
    assert health["subsystems"]["governance"]["status"] == "FAILED"
    assert health["subsystems"]["policy"]["status"] == "UNKNOWN"
    assert health["optional_policy_available"] is False


def test_falsy_injected_provider_is_not_replaced(tmp_path):
    class FalsyRepository:
        def __bool__(self):
            return False
        def query(self):
            raise RuntimeError("injected")
        def load(self, _):
            raise RuntimeError("injected")

    plane, _ = _plane(tmp_path, knowledge_repository=FalsyRepository())
    assert plane.get_health()["subsystems"]["repository"]["status"] == "FAILED"


def test_policy_provider_contract_is_validated(tmp_path):
    with pytest.raises(TypeError, match="POLICY_PROVIDER_UNSUPPORTED"):
        KnowledgeControlPlane(tmp_path, policy_provider=object())


def test_partial_lineage_returns_schema_error_not_exception(tmp_path):
    class PartialKnowledge:
        def load(self, _):
            return {"knowledge_uuid": "knowledge-1"}
        def query(self):
            return [{"knowledge_uuid": "knowledge-1"}]

    plane, _ = _plane(tmp_path, knowledge_repository=PartialKnowledge())
    lineage = plane.get_lineage("knowledge-1")
    assert lineage["status"] == "FAILED"
    assert lineage["error"] == "SCHEMA_MISMATCH"


def test_control_plane_has_no_mutating_public_methods(tmp_path):
    plane, _ = _plane(tmp_path)
    assert not {"save", "append", "build", "transition", "promote", "retire", "execute"} & set(dir(plane))
    assert plane.capabilities() == tuple(sorted(plane.capabilities()))
