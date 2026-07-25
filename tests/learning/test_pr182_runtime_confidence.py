"""PR182 governed advisory confidence architecture tests."""
import json
from dataclasses import replace
from pathlib import Path
import sys
import pytest

sys.path.insert(0,str(Path(__file__).parents[2])); sys.path.insert(1,str(Path(__file__).parent))
from learning.runtime_confidence import RuntimeConfidenceError, RuntimeConfidenceEvaluator, RuntimeConfidencePolicy, RuntimeConfidenceRepository
from learning.runtime_selection import RuntimeKnowledgeSelectionRepository, RuntimeKnowledgeSelector
from test_pr181_runtime_selection import artifacts

def setup(root):
    packaged,runtime_repo=artifacts(root)
    eligibility_repo=RuntimeKnowledgeSelectionRepository(root/"runtime_selection")
    report=RuntimeKnowledgeSelector(runtime_repo,eligibility_repo).evaluate_eligibility(packaged)
    engine=RuntimeConfidenceEvaluator(eligibility_repo,RuntimeConfidenceRepository(root/"runtime_confidence"))
    return report,eligibility_repo,engine

def test_accepts_only_pr181_artifacts_and_is_advisory(tmp_path):
    report,repo,engine=setup(tmp_path)
    for bad in (None,{},object(),report.runtime_selections):
        with pytest.raises(RuntimeConfidenceError,match="INVALID_ELIGIBILITY"): engine.evaluate_confidence(bad)
    result=engine.evaluate_confidence(report)
    record=result.confidence_records[0]
    assert record.confidence_state=="CONFIDENCE_EVALUATED" and record.confidence_score==1.0
    assert record.advisory_only is result.advisory_only is True
    assert record.runtime_package_uuid==report.runtime_selections[0].source_runtime_package_uuid

def test_record_snapshot_and_report_replay(tmp_path):
    report,repo,engine=setup(tmp_path)
    first=engine.evaluate_confidence(report.runtime_selections[0]); path=engine.repository.path_for(first.confidence_records[0].confidence_uuid); data=path.read_bytes()
    replay=engine.evaluate_confidence(report.runtime_selections[0])
    assert replay.duplicate_count==1 and replay.snapshot_uuid==first.snapshot_uuid and path.read_bytes()==data
    assert engine.evaluate_confidence(repo.latest_snapshot()).duplicate_count==1
    assert engine.evaluate_confidence(report).duplicate_count==1

def test_deterministic_uuid_canonical_serialization_and_append_only(tmp_path):
    report,repo,one=setup(tmp_path/"source")
    two=RuntimeConfidenceEvaluator(repo,RuntimeConfidenceRepository(tmp_path/"two"))
    left=one.evaluate_confidence(report).confidence_records[0]; right=two.evaluate_confidence(report).confidence_records[0]
    assert left==right
    assert one.repository.path_for(left.confidence_uuid).read_bytes()==json.dumps(left.to_dict(),sort_keys=True,separators=(",",":"),allow_nan=False).encode()

def test_broken_provenance_snapshot_and_repository_fail_closed(tmp_path):
    report,repo,engine=setup(tmp_path)
    forged=replace(report.runtime_selections[0]); object.__setattr__(forged,"selection_digest","f"*64)
    with pytest.raises(RuntimeConfidenceError,match="BROKEN_PROVENANCE"): engine.evaluate_confidence(forged)
    damaged=replace(report); object.__setattr__(damaged,"selection_snapshot_digest","e"*64)
    with pytest.raises(RuntimeConfidenceError,match="SNAPSHOT_MISMATCH"): engine.evaluate_confidence(damaged)
    damaged=replace(report); object.__setattr__(damaged,"repository_digest","d"*64)
    with pytest.raises(RuntimeConfidenceError,match="REPOSITORY_MISMATCH"): engine.evaluate_confidence(damaged)

def test_policy_engine_partition_duplicate_and_collision(tmp_path):
    report,repo,engine=setup(tmp_path); result=engine.evaluate_confidence(report)
    changed=RuntimeConfidencePolicy(confidence_policy_version="PR182-CONFIDENCE-POLICY.2.0")
    with pytest.raises(RuntimeConfidenceError,match="POLICY_MISMATCH"): RuntimeConfidenceEvaluator(repo,engine.repository,changed).evaluate_confidence(report)
    changed_engine=RuntimeConfidencePolicy(confidence_engine_version="PR182.changed")
    with pytest.raises(RuntimeConfidenceError,match="ENGINE_VERSION_MISMATCH"): RuntimeConfidenceEvaluator(repo,RuntimeConfidenceRepository(tmp_path/"changed"),changed_engine).evaluate_confidence(report)
    path=engine.repository.path_for(result.confidence_records[0].confidence_uuid); raw=json.loads(path.read_text()); raw["confidence_score"]=0.5; path.write_text(json.dumps(raw))
    with pytest.raises(RuntimeConfidenceError,match="CORRUPT_CONFIDENCE_REPOSITORY"): engine.evaluate_confidence(report)
