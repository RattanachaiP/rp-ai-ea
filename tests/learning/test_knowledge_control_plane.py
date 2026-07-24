from __future__ import annotations

from learning.control_plane import KnowledgeControlPlane
from learning.governance import GovernanceRepository, KnowledgeGovernance
from learning.knowledge import Knowledge, KnowledgeRepository
from learning.lifecycle import LifecycleRepository, transition


def _plane(tmp_path):
    knowledge_repo = KnowledgeRepository(tmp_path)
    record = Knowledge.create(knowledge_uuid="knowledge-1", pattern_uuid="pattern-1", validation_uuid="validation-1", sample_count=40, verified_win_rate=.5, average_rr=1, created_timestamp="2026-07-24T00:00:00Z")
    knowledge_repo.save(record)
    governance = GovernanceRepository(tmp_path)
    governance.save(KnowledgeGovernance("knowledge-1", "pattern-1", "validation-1", "analytics-1", "a" * 40, "1.0", "1.0", "DRAFT", "pattern-1/1", False))
    lifecycle = LifecycleRepository(tmp_path)
    transition(repository=lifecycle, knowledge_uuid="knowledge-1", previous_state="DRAFT", new_state="VERIFIED", triggering_component="test", reason="test", governance_version="1.0", lifecycle_version="1.0", timestamp="2026-07-24T00:00:01Z", transition_uuid="00000000-0000-4000-8000-000000000001")
    return KnowledgeControlPlane(tmp_path), record


def test_snapshot_is_deterministic_and_contains_required_coordination_metadata(tmp_path):
    plane, record = _plane(tmp_path)
    first = plane.get_snapshot(record.knowledge_uuid)
    assert first == plane.get_snapshot(record.knowledge_uuid)
    assert first["knowledge"][0]["governance"]["knowledge_uuid"] == record.knowledge_uuid
    assert first["knowledge"][0]["lifecycle"][0]["new_state"] == "VERIFIED"
    assert set(first) >= {"analytics_summary", "configuration_versions", "health", "repository_version", "schema_versions", "snapshot_digest"}


def test_health_isolated_failure_does_not_block_other_subsystems(tmp_path):
    plane, record = _plane(tmp_path)
    class BrokenGovernance:
        def load(self, _): raise RuntimeError("unavailable")
        def query(self): raise RuntimeError("unavailable")
    plane = KnowledgeControlPlane(tmp_path, governance_repository=BrokenGovernance())
    assert plane.get_knowledge(record.knowledge_uuid)["knowledge_uuid"] == record.knowledge_uuid
    assert plane.get_health()["subsystems"]["governance"]["status"] == "FAILED"
    assert plane.get_health()["subsystems"]["policy"]["status"] == "UNKNOWN"


def test_control_plane_has_no_mutating_public_methods(tmp_path):
    plane, _ = _plane(tmp_path)
    assert not {"save", "append", "build", "transition", "promote", "retire", "execute"} & set(dir(plane))
    assert plane.capabilities() == tuple(sorted(plane.capabilities()))
