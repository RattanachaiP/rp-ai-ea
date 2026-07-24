from dataclasses import replace
from uuid import uuid4
import math, pytest
from learning.outcome_attribution import *
from learning.analytics import KnowledgeAnalyticsEngine

def row(outcome, **more):
 return {'knowledge_uuid':str(uuid4()),'knowledge_version':'1.0.0','timestamp':'2026-07-24T00:00:00Z','replay_digest':'a'*64,'outcome':outcome,'outcome_metric':'REALIZED_PNL','outcome_unit':'USD','features':{'trend':['up',{'strength':2}]},'indicators':{'rsi':'low'},'risk_factors':{'volatility':'high'},'context':{'regime':'TREND'},**more}
def paired(outcomes):
 r=[row(x) for x in outcomes]
 for x in r[1:]:x['knowledge_uuid']=r[0]['knowledge_uuid']
 return r
def test_names_are_scoped_and_existing_analytics_authority_remains():
 import learning.outcome_attribution as package
 assert 'KnowledgeAnalyticsEngine' not in package.__all__ and KnowledgeAnalyticsEngine.__module__=='learning.analytics.engine'
def test_deterministic_deep_canonical_attribution_and_neutral_outcomes():
 rows=paired([2,-1,0]); a=KnowledgeOutcomeAttributionEngine().analyze(rows); b=KnowledgeOutcomeAttributionEngine().analyze(list(reversed(rows)))
 assert a.to_dict()==b.to_dict() and a.created_at=='2026-07-24T00:00:00Z'
 assert (a.summary.winning_trade_count,a.summary.losing_trade_count,a.summary.neutral_count)==(1,1,1)
 assert all(0<=x.success_rate<=1 for x in a.indicator_contributions)
def test_fail_closed_identity_replay_units_and_invalid_nested_values():
 rows=paired([1,2]); rows[1]['knowledge_uuid']=str(uuid4())
 with pytest.raises(KnowledgeOutcomeAttributionError,match='MIXED_KNOWLEDGE_IDENTITIES'):KnowledgeOutcomeAttributionEngine().analyze(rows)
 rows=paired([1,2]); rows[1]['knowledge_version']='2.0.0'
 with pytest.raises(KnowledgeOutcomeAttributionError,match='MIXED_KNOWLEDGE_IDENTITIES'):KnowledgeOutcomeAttributionEngine().analyze(rows)
 bad=row(1,replay_digest='g'*64)
 with pytest.raises(KnowledgeOutcomeAttributionError,match='REPLAY_MISMATCH'):KnowledgeOutcomeAttributionEngine().analyze([bad])
 for value in (object(),math.nan,math.inf,{1:'bad'}):
  bad=row(1);bad['features']={'bad':value}
  with pytest.raises(KnowledgeOutcomeAttributionError):KnowledgeOutcomeAttributionEngine().analyze([bad])
def test_contract_validation_and_append_only_storage(tmp_path):
 r=KnowledgeOutcomeAttributionEngine().analyze(paired([1])); repo=KnowledgeOutcomeAttributionRepository(tmp_path)
 assert repo.save(r)==repo.save(r)
 with pytest.raises(FileExistsError):repo.save(replace(r,attribution_version='changed'))
 with pytest.raises(ValueError):replace(r,advisory_only=False)
 with pytest.raises(ValueError):AnalyticsSummary(1,1,1,0,1,1,1,'X','Y','a'*64)
