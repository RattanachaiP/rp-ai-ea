from uuid import uuid4
import pytest
from learning.knowledge_analytics import KnowledgeAnalyticsEngine, KnowledgeAnalyticsError, KnowledgeAnalyticsRepository

def row(outcome, **more):
    return {'knowledge_uuid':str(uuid4()), 'knowledge_version':'1.0.0', 'timestamp':'2026-07-24T00:00:00Z', 'replay_digest':'a'*64, 'outcome':outcome, 'features':{'trend':'up','entry':'pullback'}, 'indicators':{'rsi':'low'}, 'risk_factors':{'volatility':'high'}, 'context':{'regime':'TREND'}, **more}
def test_pr173_aggregates_and_replays_deterministically():
    first, second=row(2),row(-1)
    second['knowledge_uuid']=first['knowledge_uuid']
    engine=KnowledgeAnalyticsEngine()
    a=engine.analyze([first,second]); b=engine.analyze([second,first])
    assert a.to_dict()==b.to_dict() and a.summary.trade_count==2
    assert a.feature_contributions and a.failure_patterns and a.success_patterns
    assert a.market_regimes[0].regime_id=='TREND' and a.indicator_contributions and a.risk_contributions

def test_pr173_fails_closed_for_version_feature_and_replay_errors():
    first, second=row(1),row(1); second['knowledge_uuid']=first['knowledge_uuid']; second['knowledge_version']='2.0.0'
    with pytest.raises(KnowledgeAnalyticsError, match='MIXED_KNOWLEDGE_VERSIONS'): KnowledgeAnalyticsEngine().analyze([first,second])
    invalid=row(1); invalid['features']={}
    # empty feature map is valid, but an unknown identity is not.
    invalid['features']={None:'x'}
    with pytest.raises(KnowledgeAnalyticsError, match='UNKNOWN_FEATURE_IDENTITY'): KnowledgeAnalyticsEngine().analyze([invalid])
    invalid=row(1); invalid['replay_digest']='bad'
    with pytest.raises(KnowledgeAnalyticsError, match='REPLAY_MISMATCH'): KnowledgeAnalyticsEngine().analyze([invalid])

def test_pr173_storage_is_append_only(tmp_path):
    evidence=row(1); repo=KnowledgeAnalyticsRepository(tmp_path); report=KnowledgeAnalyticsEngine(repo).analyze([evidence])
    assert repo.save(report)==repo.path_for(report.analytics_uuid)
