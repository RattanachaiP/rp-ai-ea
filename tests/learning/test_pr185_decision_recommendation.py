"""PR185 governed advisory Decision Recommendation tests."""
import json
import pytest
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).parents[2]))
sys.path.insert(1, str(Path(__file__).parent))
from learning.decision_recommendation import (DecisionRecommendationError, DecisionRecommendationPolicy,
    DecisionRecommendationRepository, GovernedDecisionRecommendationEngine)
from learning.decision_recommendation.identity import canonical_bytes
from test_pr184_decision_intelligence import setup_engine as setup_intelligence_engine

def setup_engine(root):
    context_report, _, intelligence_engine=setup_intelligence_engine(root)
    intelligence_report=intelligence_engine.construct_intelligence(context_report)
    engine=GovernedDecisionRecommendationEngine(intelligence_engine.repository,DecisionRecommendationRepository(root/"decision_recommendation"))
    return intelligence_report,intelligence_engine.repository,engine

def test_supported_inputs_produce_immutable_advisory_recommendation(tmp_path):
    report,repo,engine=setup_engine(tmp_path)
    for source in (report.decision_intelligences[0],report,repo.latest_snapshot()):
        result=engine.construct_recommendation(source); item=result.recommendations[0]
        assert item.recommendation_state=="RECOMMENDATION_READY"
        assert item.recommendation_classification in {"READY_FOR_DECISION","MANUAL_REVIEW","NOT_READY"}
        assert item.advisory_only is result.advisory_only is True
        assert item.authority_scope=="ADVISORY_DECISION_RECOMMENDATION_ONLY"
    for invalid in (None,{},[],report.decision_intelligences):
        with pytest.raises(DecisionRecommendationError,match="INVALID_DECISION_INTELLIGENCE"): engine.recommend(invalid)
    assert not any(hasattr(engine,n) for n in ("trade","execute","activate","publish_decision"))

def test_replay_is_canonical_append_only_and_policy_governed(tmp_path):
    report,_,engine=setup_engine(tmp_path); first=engine.run(report); paths=tuple(engine.repository.root.glob("*.json")); second=engine.run(report)
    assert second.duplicate_count==1 and second.recommendations==first.recommendations and tuple(engine.repository.root.glob("*.json"))==paths
    item=first.recommendations[0]; path=engine.repository.root/f"{item.recommendation_uuid}.json"
    assert path.read_bytes()==canonical_bytes(item.to_dict())
    assert json.loads(path.read_text())["recommendation_classification"] not in {"BUY","SELL","HOLD"}
    with pytest.raises(ValueError,match="INVALID_RECOMMENDATION_POLICY"): DecisionRecommendationPolicy(recommendation_engine_version="PR999")

def test_provenance_and_repository_tampering_fail_closed(tmp_path):
    report,repo,engine=setup_engine(tmp_path); item=report.decision_intelligences[0]
    object.__setattr__(item,"intelligence_digest","0"*64)
    with pytest.raises(DecisionRecommendationError,match="BROKEN_PROVENANCE"): engine.run(item)
    object.__setattr__(item,"intelligence_digest",repo.records()[0].intelligence_digest)
    produced=engine.run(report).recommendations[0]; path=engine.repository.root/f"{produced.recommendation_uuid}.json"; path.write_text(json.dumps(produced.to_dict(),indent=2))
    with pytest.raises(DecisionRecommendationError,match="NONCANONICAL_DECISION_RECOMMENDATION_JSON"): engine.repository.records()
