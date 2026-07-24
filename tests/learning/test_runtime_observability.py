from learning.runtime_observability import *
from learning.runtime_observability.incidents import incident_for
from learning.runtime_observability.reports import daily_report,weekly_report
from learning.runtime_observability.storage import RuntimeKnowledgeObservabilityStorage
from uuid import uuid4
import pytest

def artifact(**more):
 return {'source_authority':'runtime.gateway','observed_at':'2026-01-01T00:00:00Z','knowledge_uuid':str(uuid4()),'version_uuid':str(uuid4()),**more}
def test_deterministic_observation_and_staleness(tmp_path):
 p=RuntimeKnowledgeObservabilityPolicy(evaluation_timestamp='2026-01-01T00:01:01Z',heartbeat_stale_seconds=60)
 o=RuntimeKnowledgeObserver(p,RuntimeKnowledgeObservabilityStorage(tmp_path)); a=artifact()
 first=o.observe('RUNTIME_HEARTBEAT_OBSERVATION',a,runtime_instance_id='r1'); second=o.observe('RUNTIME_HEARTBEAT_OBSERVATION',a,runtime_instance_id='r1')
 assert first==second and first.state=='STALE'
 assert incident_for(first,p).classification=='RUNTIME_HEARTBEAT_STALE'
def test_adoption_reports_and_append_only(tmp_path):
 p=RuntimeKnowledgeObservabilityPolicy(evaluation_timestamp='2026-01-01T00:00:00Z'); o=RuntimeKnowledgeObserver(p); a=artifact(); x=o.observe('REGISTRY_STATE_OBSERVATION',a,runtime_instance_id='r')
 correlation=o.correlate(knowledge_uuid=x.knowledge_uuid,version_uuid=x.version_uuid,runtime_instance_id='r')
 assert o.assess_adoption(correlation).adoption_state=='ADOPTION_CONFIRMED'
 assert daily_report('2026-01-01T00:00:00Z','2026-01-02T00:00:00Z',(x,)).total_observations==1
 assert weekly_report('2026-01-01T00:00:00Z','2026-01-08T00:00:00Z',(x,)).total_observations==1
 with pytest.raises(RuntimeKnowledgeObservabilityError): daily_report('2026-01-02T00:00:00Z','2026-01-01T00:00:00Z',(x,))
