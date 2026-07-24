from datetime import datetime, timezone
from uuid import uuid4
import pytest
from learning.active_registry import ActiveKnowledgeRegistry

def artifacts(semantic="family/xau", knowledge=None):
    decision, knowledge, record = str(uuid4()), knowledge or str(uuid4()), str(uuid4())
    return ({"record_uuid": record, "decision_uuid": decision, "knowledge_uuid": knowledge, "semantic_identity": semantic, "status": "COMMITTED"},
            {"decision_uuid": decision, "knowledge_uuid": knowledge, "semantic_identity": semantic, "decision": "PROMOTE", "decision_status": "APPROVED"})

def register(registry, record, decision, **kwargs):
    return registry.register(record, decision, activation_timestamp="2026-01-01T00:00:00Z", **kwargs)

def test_activation_lookup_history_and_replay(tmp_path):
    registry, (record, decision) = ActiveKnowledgeRegistry(root=tmp_path), artifacts()
    entry = register(registry, record, decision)
    assert register(registry, record, decision) == entry
    assert registry.get_active(entry.knowledge_uuid) == entry
    assert registry.lookup(entry.semantic_identity) == entry
    assert registry.list_active() == (entry,)
    assert len(registry.history()) == 1

def test_duplicate_and_broken_artifacts_fail_closed(tmp_path):
    registry = ActiveKnowledgeRegistry(root=tmp_path)
    first, first_d = artifacts(); register(registry, first, first_d)
    second, second_d = artifacts()
    with pytest.raises(ValueError, match="DUPLICATE_ACTIVE_SEMANTIC"): register(registry, second, second_d)
    with pytest.raises(ValueError, match="MISSING_PROMOTION_RECORD"): registry.register(None, second_d)
    with pytest.raises(ValueError, match="BROKEN_PROMOTION_LINEAGE"): register(registry, second, {**second_d, "knowledge_uuid": str(uuid4())})

def test_supersession_and_retirement_keep_immutable_history(tmp_path):
    registry = ActiveKnowledgeRegistry(root=tmp_path)
    old_r, old_d = artifacts(); old = register(registry, old_r, old_d)
    new_r, new_d = artifacts(knowledge=str(uuid4()))
    new = register(registry, new_r, new_d, supersedes_knowledge_uuid=old.knowledge_uuid)
    assert registry.get_active(old.knowledge_uuid) is None
    assert registry.resolve(old.semantic_identity) == new
    old_history = registry.history(old.knowledge_uuid)
    assert old_history[0] == old and old_history[-1].status == "SUPERSEDED"
    retired_r, retired_d = artifacts(semantic=new.semantic_identity, knowledge=new.knowledge_uuid)
    # terminal registry event must still bind to a genuine promotion lineage for this knowledge
    register(registry, retired_r, retired_d, status="RETIRED")
    assert registry.get_by_uuid(new.knowledge_uuid).status == "RETIRED"
    assert registry.list_active() == ()
