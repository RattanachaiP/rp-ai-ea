from datetime import datetime, timezone
from uuid import uuid4
import pytest
from learning.runtime_observability import RuntimeKnowledgeObserver, RuntimeKnowledgeObservabilityPolicy
from learning.runtime_health_monitor import RuntimeHealthMonitor, RuntimeHealthMonitorPolicy, RuntimeHealthMonitorError

def obs(state='HEALTHY', typ='RUNTIME_HEARTBEAT_OBSERVATION'):
 p=RuntimeKnowledgeObservabilityPolicy(evaluation_timestamp='2026-01-01T00:01:00Z')
 return RuntimeKnowledgeObserver(p).observe(typ, {'status':'FAILED' if state=='FAILED' else 'OK','digest':'a'*64,'observed_at':'2026-01-01T00:00:30Z'}, runtime_instance_id='runtime', source_authority='PR170') if state=='FAILED' else __import__('learning.runtime_observability',fromlist=['RuntimeKnowledgeObservation']).RuntimeKnowledgeObservation(str(uuid4()),typ,'runtime','','','', '2026-01-01T00:00:30Z','2026-01-01T00:01:00Z',state,'TEST','test','PR170','a'*64,'PR170','1', 'b'*64)
def monitor(tmp_path, **overrides): return RuntimeHealthMonitor(RuntimeHealthMonitorPolicy(evaluation_timestamp='2026-01-01T00:01:00Z', **overrides),root=tmp_path)
def test_states_and_deterministic_replay(tmp_path):
 m=monitor(tmp_path); e=m.evaluate([obs()]); assert e.state=='HEALTHY' and e.advisory_only; assert m.evaluate([obs()]).state=='HEALTHY'
 assert monitor(tmp_path).evaluate([obs('UNKNOWN')]).state=='UNKNOWN'
def test_failure_incident_recommendation_is_nonexecutable(tmp_path):
 m=monitor(tmp_path,failure_threshold_count=1); e=m.evaluate([obs('FAILED')]); c=m.correlate_incident(e); r=m.recommend(e,c.incident_uuid); assert c and r.recommendation_type=='ROLLBACK_REVIEW_RECOMMENDED' and not r.executable and r.human_review_required
def test_lifecycle_acknowledgement_and_recovery(tmp_path):
 m=monitor(tmp_path,failure_threshold_count=1); c=m.correlate_incident(m.evaluate([obs('FAILED')])); a=m.acknowledge(c.incident_uuid,'reviewer','triage'); assert a.state=='ACKNOWLEDGED'
 with pytest.raises(RuntimeHealthMonitorError): m.transition(c.incident_uuid,'CLOSED','no')
 assert m.assess_recovery(c.incident_uuid,[obs(),obs()]).state=='CONFIRMED'
