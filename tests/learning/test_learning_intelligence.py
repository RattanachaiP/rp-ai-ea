from dataclasses import replace
from datetime import datetime, timedelta, timezone
from runtime.decision_knowledge_observation import DecisionKnowledgeObservationRecord, KnowledgeObservation, ObservedKnowledgeReference
from runtime.decision_outcome_observation import CompletedTradeResult, DecisionOutcomeObservation
from learning.intelligence import LearningIntelligenceEngine, LearningThresholds, LearningIntelligenceError
import pytest
from uuid import uuid4
D="a"*64

def record():
 ref=ObservedKnowledgeReference(str(uuid4()),"XAU.TEST",.8,.9,1,("x",),("x",),D,1)
 return DecisionKnowledgeObservationRecord(str(uuid4()),str(uuid4()),D,str(uuid4()),D,D,KnowledgeObservation((ref,),(ref,),"OBSERVED"),"2026-01-01T00:00:00.000000Z")
def outcome(knowledge, ticket, profit, hour=8):
 entry=datetime(2026,1,1,hour,tzinfo=timezone.utc); exit=entry+timedelta(minutes=5)
 r=CompletedTradeResult(knowledge.decision_uuid,knowledge.observation_uuid,ticket,"XAUUSD","BUY",1,2,entry.isoformat(timespec="microseconds").replace("+00:00","Z"),exit.isoformat(timespec="microseconds").replace("+00:00","Z"),profit,profit,0,0,2,1,"TAKE_PROFIT")
 return DecisionOutcomeObservation(**r.__dict__,holding_time_seconds=r.holding_time_seconds)
def test_statistics_and_minimum_sample_protection():
 k=record(); stats,recs=LearningIntelligenceEngine().evaluate([k],[outcome(k,1,10)])
 assert stats[0].win_rate==1 and stats[0].profit_factor is None
 assert recs[0].recommendation=="COLLECT_MORE_DATA"
def test_duplicate_and_evidence_rejected():
 k=record(); o=outcome(k,1,1)
 with pytest.raises(LearningIntelligenceError,match="DUPLICATE_OUTCOME") : LearningIntelligenceEngine().evaluate([k],[o,o])
def test_recommendation_after_configured_sample():
 k=record(); outcomes=[outcome(k,i,1,8+i%3) for i in range(1,4)]
 t=LearningThresholds(minimum_trades=3,minimum_wins=3,minimum_sessions=1,minimum_confidence=.1,drift_recent_trades=1)
 _,recs=LearningIntelligenceEngine(t).evaluate([k],outcomes)
 assert recs[0].recommendation=="PROMOTE" and recs[0].advisory_only
