from uuid import uuid4
import pytest
from learning.incident_response import IncidentResponseOrchestrator, IncidentResponsePolicy, IncidentResponseError

def evidence():
 return {'incident_uuid':str(uuid4()),'runtime_instance_id':'runtime-a','knowledge_uuid':str(uuid4()),'version_uuid':str(uuid4()),'registry_snapshot_digest':'a'*64,'replay_digest':'b'*64,'evaluation_timestamp':'2026-01-01T00:00:00Z','source_authority':'PR171'}
def orch(tmp_path): return IncidentResponseOrchestrator(IncidentResponsePolicy(evaluation_timestamp='2026-01-01T00:00:01Z'),root=tmp_path)
def test_intake_is_deterministic_and_non_executable(tmp_path):
 o=orch(tmp_path); c=o.intake(evidence()); assert o.intake(evidence()).incident_case_uuid != c.incident_case_uuid # distinct source evidence creates distinct case
 assert c.impact=='UNKNOWN_IMPACT'
def test_workflow_requires_humans_and_plan_is_non_executable(tmp_path):
 o=orch(tmp_path); c=o.intake(evidence()); o.triage(c); o.acknowledge(c,'owner','recognized'); o.assign(c,'investigator','owner','investigate'); o.begin_investigation(c,'investigator'); p=o.response_plan(c); assert not p.executable
 with pytest.raises(IncidentResponseError): o.close(c,'owner','no review')
def test_invalid_evidence_and_transition_fail_closed(tmp_path):
 o=orch(tmp_path)
 with pytest.raises(IncidentResponseError): o.intake({'replay_digest':'bad'})
 c=o.intake(evidence())
 with pytest.raises(IncidentResponseError): o.begin_investigation(c,'x')
