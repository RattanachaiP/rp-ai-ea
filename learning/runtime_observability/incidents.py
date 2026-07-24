from uuid import NAMESPACE_URL,uuid5
from .models import *
_MAP={'STALE_EVIDENCE':'REGISTRY_STALE','VERSION_MISMATCH':'VERSION_MISMATCH','CONTRACT_MISMATCH':'CONTRACT_MISMATCH','SOURCE_FAILED':'OBSERVABILITY_PIPELINE_FAILURE','MISSING_EVIDENCE':'IDENTITY_CORRELATION_FAILURE'}
def incident_for(observation,policy):
 if observation.state=='HEALTHY': return None
 classification=('RUNTIME_HEARTBEAT_STALE' if observation.observation_type=='RUNTIME_HEARTBEAT_OBSERVATION' and observation.state=='STALE' else _MAP.get(observation.reason_code, 'IDENTITY_CORRELATION_FAILURE'))
 severity=policy.severity_policy.get(classification, 'CRITICAL' if observation.state=='FAILED' else 'ERROR' if observation.state=='MISMATCH' else 'WARNING' if observation.state=='STALE' else 'INFO')
 iid=str(uuid5(NAMESPACE_URL,'pr170-incident:'+observation.observation_uuid+':'+classification)); return RuntimeKnowledgeIncident(iid,observation.observation_uuid,classification,severity,observation.evaluation_timestamp,digest(observation.to_dict()))
