from uuid import uuid4
import pytest
from learning.knowledge_versions import KnowledgeVersionManager


def _uuid(): return str(uuid4())
def _contracts(): return {"architecture_version": "PR167", "policy_version": "1.0", "runtime_contract": "runtime-v1", "knowledge_contract": "knowledge-v1", "applicability_contract": "applicability-v1"}
def _inputs(*, knowledge_uuid=None, activation_uuid=None, promotion_uuid=None):
    knowledge_uuid = knowledge_uuid or _uuid(); contracts = _contracts()
    return ({"activation_uuid": activation_uuid or _uuid(), "knowledge_uuid": knowledge_uuid, "effective_at": "2026-07-24T00:00:00Z", **contracts}, {"promotion_uuid": promotion_uuid or _uuid(), "knowledge_uuid": knowledge_uuid, **contracts}, {"knowledge_uuid": knowledge_uuid, "registry_version": "1.0", **contracts})

def test_version_is_deterministic_append_only_and_replay_safe(tmp_path):
    manager = KnowledgeVersionManager(root=tmp_path); inputs = _inputs()
    first = manager.register(*inputs); replay = manager.register(*inputs)
    assert replay == first
    assert (tmp_path / "knowledge_versions" / "manifest" / f"manifest_{first.version_uuid}.json").exists()
    assert (tmp_path / "knowledge_versions" / "history" / f"history_{first.version_uuid}.json").exists()

def test_parent_lineage_and_rollback_descriptor(tmp_path):
    manager = KnowledgeVersionManager(root=tmp_path); first = manager.register(*_inputs())
    activation, promotion, snapshot = _inputs(knowledge_uuid=first.knowledge_uuid)
    second = manager.create_version(activation, promotion, snapshot, parent_version_uuid=first.version_uuid)
    assert manager.lineage_for(first.version_uuid).children == (second.version_uuid,)
    rollback = manager.rollback_descriptor(second.version_uuid)
    assert rollback.rollback_parent_uuid == first.version_uuid and rollback.eligible and rollback.compatible

def test_rejects_contract_mismatch_and_unknown_parent(tmp_path):
    manager = KnowledgeVersionManager(root=tmp_path); activation, promotion, snapshot = _inputs()
    promotion["runtime_contract"] = "other"
    with pytest.raises(ValueError, match="CONTRACT_MISMATCH"): manager.register(activation, promotion, snapshot)
    activation, promotion, snapshot = _inputs()
    with pytest.raises(ValueError, match="INVALID_PARENT_VERSION"): manager.register(activation, promotion, snapshot, parent_version_uuid=_uuid())
