from dataclasses import replace
from uuid import uuid4
import json, math, pytest
from learning.learning_policy import *
from learning.outcome_attribution import KnowledgeOutcomeAttributionEngine

def attribution(n):
 k=str(uuid4()); rows=[{'knowledge_uuid':k,'knowledge_version':'1','timestamp':'2026-07-24T00:00:00Z','replay_digest':'a'*64,'outcome':1 if i%2 else -1,'outcome_metric':'REALIZED_PNL','outcome_unit':'USD','features':{'x':'x'},'indicators':{'x':'x'},'risk_factors':{'x':'x'},'context':{'x':'x'}} for i in range(n)]
 return KnowledgeOutcomeAttributionEngine().analyze(rows)
def corrupt(report,name,value): object.__setattr__(report,name,value);return report

@pytest.mark.parametrize('n,state,additional',[(1,'REQUIRES_MORE_DATA',29),(29,'REQUIRES_MORE_DATA',1),(30,'ELIGIBLE_FOR_PATTERN_MINING',0),(31,'ELIGIBLE_FOR_PATTERN_MINING',0)])
def test_threshold_decisions(n,state,additional):
 r=GovernedLearningPolicyEngine().evaluate(attribution(n));assert (r.eligibility_state,r.additional_samples_required)==(state,additional)
 assert r.blocking_reasons==(() if not additional else ('MINIMUM_SAMPLE_THRESHOLD_NOT_MET',))
 assert r.warning_codes==(() if additional else ('ELIGIBILITY_DOES_NOT_IMPLY_STABILITY','ELIGIBILITY_DOES_NOT_IMPLY_PROMOTION'))
def test_config_and_determinism():
 a=attribution(50); low=GovernedLearningPolicyEngine(GovernedLearningPolicyConfig(50)); high=GovernedLearningPolicyEngine(GovernedLearningPolicyConfig(51))
 assert low.assess(a)==low.evaluate(a) and low.evaluate(a).policy_uuid!=high.evaluate(a).policy_uuid
 assert GovernedLearningPolicyEngine(GovernedLearningPolicyConfig(50)).evaluate(attribution(49)).eligibility_state=='REQUIRES_MORE_DATA'

def test_fail_closed_validation():
 e=GovernedLearningPolicyEngine()
 with pytest.raises(GovernedLearningPolicyError):e.evaluate({})
 cases=[('advisory_only',False),('attribution_uuid','bad'),('source_digest','bad'),('replay_digest','bad'),('attribution_version','bad'),('created_at','bad')]
 for field,value in cases:
  with pytest.raises(GovernedLearningPolicyError): e.evaluate(corrupt(attribution(2),field,value))
 r=attribution(3);corrupt(r,'performance_profiles',(replace(r.performance_profiles[0],wins=2,losses=1),))
 with pytest.raises(GovernedLearningPolicyError,match='INCONSISTENT_PROFILE_SUMMARY'):e.evaluate(r)
 r=attribution(2);corrupt(r,'confidence',(replace(r.confidence[0],classification='HIGH'),))
 with pytest.raises(GovernedLearningPolicyError,match='INCONSISTENT_CONFIDENCE'):e.evaluate(r)
 r=attribution(2);corrupt(r,'summary',replace(r.summary,outcome_metric='BAD'))
 with pytest.raises(GovernedLearningPolicyError,match='UNSUPPORTED_OUTCOME_CONTRACT'):e.evaluate(r)
 r=attribution(2);corrupt(r,'context_attribution',{'bad':math.nan})
 with pytest.raises(GovernedLearningPolicyError):e.evaluate(r)

def test_config_and_repository(tmp_path):
 with pytest.raises(ValueError):GovernedLearningPolicyConfig(0)
 with pytest.raises(ValueError):GovernedLearningPolicyConfig(30,())
 report=GovernedLearningPolicyEngine().evaluate(attribution(30));repo=GovernedLearningPolicyRepository(tmp_path)
 path=repo.save(report);assert path==repo.save(report) and path.read_bytes()==json.dumps(report.to_dict(),sort_keys=True,separators=(',',':'),allow_nan=False).encode()
 with pytest.raises(FileExistsError):repo.save(replace(report,warning_codes=()))
 with pytest.raises(ValueError):repo.path_for('../escape')
