from dataclasses import replace
import pytest
from learning.knowledge import Knowledge
from learning.policy import KnowledgePolicyEngine, PolicyConfig, PolicyEvaluationRepository

def knowledge(**values):
    base=Knowledge("k1",1,"p","v","2026-07-24T00:00:00Z",("X",),("S",),("M",),40,.6,1.5,None,schema_version="1.0")
    return replace(base, **values)
def inputs(**analytics): return dict(governance={"production_eligible": True, "current_lifecycle_state":"VERIFIED"}, lifecycle_state="VERIFIED", analytics={"significance":.96,"stability_classification":"STABLE","conflict_severity":"LOW", "timestamp":"2026-07-24T00:00:00Z", **analytics}, evaluation_timestamp="2026-07-24T01:00:00Z")
def test_thresholds_and_deterministic_replay():
    engine=KnowledgePolicyEngine(source_baseline="base")
    assert engine.evaluate(knowledge(), **inputs()).eligible
    assert engine.evaluate(knowledge(), **inputs()).to_dict() == engine.evaluate(knowledge(), **inputs()).to_dict()
    assert not engine.evaluate(knowledge(sample_count=29), **inputs()).eligible
    assert not engine.evaluate(knowledge(average_rr=.9), **inputs()).eligible
    assert not engine.evaluate(knowledge(verified_win_rate=.4), **inputs()).eligible
def test_lifecycle_governance_conflict_schema_and_freshness():
    engine=KnowledgePolicyEngine(source_baseline="base")
    assert not engine.evaluate(knowledge(), **{**inputs(), "lifecycle_state": "ACTIVE"}).eligible
    assert not engine.evaluate(knowledge(), **inputs(conflict_severity="HIGH")).eligible
    assert not engine.evaluate(knowledge(schema_version="2.0"), **inputs()).eligible
    assert not engine.evaluate(knowledge(), **inputs(timestamp="2026-07-22T00:00:00Z")).eligible is False
    assert engine.evaluate(knowledge(), **inputs(timestamp="2026-07-22T00:00:00Z")).warnings
def test_immutable_repository_and_versioned_configuration(tmp_path):
    first=KnowledgePolicyEngine(source_baseline="base").evaluate(knowledge(), **inputs())
    repo=PolicyEvaluationRepository(tmp_path); assert repo.save(first) == repo.save(first)
    with pytest.raises(FileExistsError): repo.storage.write(replace(first, score=0))
    assert KnowledgePolicyEngine(PolicyConfig(version="2.0", minimum_sample_count=50), source_baseline="base").evaluate(knowledge(), **inputs()).policy_version == "2.0"

def test_policy_layer_has_no_runtime_authority_dependencies():
    from pathlib import Path
    source = "\n".join(path.read_text(encoding="utf-8") for path in Path("learning/policy").glob("*.py"))
    for forbidden in ("runtime", "bridge", "broker", "decision_engine", "executor"):
        assert forbidden not in source.lower()
