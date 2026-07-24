"""Passive observer: it reads artifacts and only emits immutable evidence."""
from __future__ import annotations
from datetime import datetime, timezone
from uuid import NAMESPACE_URL, uuid5
from .models import *
from .storage import RuntimeKnowledgeObservabilityStorage

def _time(v): return datetime.fromisoformat(str(v).replace('Z','+00:00'))
def _get(a,n,d=''):
 if isinstance(a,dict): return a.get(n,d)
 return getattr(a,n,d)
def _artifact(a):
 try:return payload(a)
 except (TypeError,ValueError): return {}
def _observed(a,policy):
 for n in ('observed_at','generated_at','created_at','activation_timestamp','timestamp'):
  v=_get(a,n,'')
  if v:return v
 return policy.evaluation_timestamp

class RuntimeKnowledgeObserver:
 """Read-only PR170 boundary. It has no references to runtime or registry writers."""
 def __init__(self,policy=RuntimeKnowledgeObservabilityPolicy(),storage=None): self.policy=policy; self.storage=storage
 def observe(self,observation_type,artifact,*,runtime_instance_id='observer',knowledge_uuid='',version_uuid='',registry_snapshot_digest='',source_authority=''):
  if observation_type not in OBSERVATION_TYPES: raise RuntimeKnowledgeObservabilityError('INVALID_OBSERVATION_TYPE')
  body=_artifact(artifact); authority=source_authority or _get(artifact,'source_authority','')
  observed=_observed(artifact,self.policy); source_digest=_get(artifact,'digest','') or _get(artifact,'report_digest','') or _get(artifact,'manifest_digest','') or _get(artifact,'version_digest','') or digest(body)
  if not authority: raise RuntimeKnowledgeObservabilityError('MISSING_SOURCE_AUTHORITY')
  if not valid_time(observed): raise RuntimeKnowledgeObservabilityError('INVALID_TIMESTAMP')
  if not valid_digest(source_digest): raise RuntimeKnowledgeObservabilityError('INVALID_ARTIFACT_DIGEST')
  knowledge_uuid=knowledge_uuid or _get(artifact,'knowledge_uuid',''); version_uuid=version_uuid or _get(artifact,'version_uuid',''); registry_snapshot_digest=registry_snapshot_digest or _get(artifact,'registry_snapshot_digest','') or _get(artifact,'snapshot_digest','') or _get(artifact,'registry_digest','')
  state,reason=self._state(observation_type,artifact,observed)
  identity={'type':observation_type,'runtime':runtime_instance_id,'knowledge':knowledge_uuid,'version':version_uuid,'source':source_digest,'observed':observed,'policy':self.policy.policy_version}
  oid=str(uuid5(NAMESPACE_URL,'pr170-observation:'+digest(identity)))
  replay=digest({'identity':identity,'state':state,'reason':reason,'body':body})
  result=RuntimeKnowledgeObservation(oid,observation_type,runtime_instance_id,knowledge_uuid,version_uuid,registry_snapshot_digest,observed,self.policy.evaluation_timestamp,state,reason,reason,authority,source_digest,self.policy.architecture_version,self.policy.policy_version,replay)
  if self.storage:self.storage.write('observations',oid,result)
  return result
 def _state(self,typ,a,observed):
  if _get(a,'status','').upper() in {'FAILED','ERROR'}: return 'FAILED','SOURCE_FAILED'
  threshold={'REGISTRY_STATE_OBSERVATION':self.policy.registry_stale_seconds,'RUNTIME_HEARTBEAT_OBSERVATION':self.policy.heartbeat_stale_seconds,'GATEWAY_LOAD_OBSERVATION':self.policy.gateway_receipt_stale_seconds,'APPLICABILITY_OBSERVATION':self.policy.applicability_stale_seconds,'DECISION_KNOWLEDGE_OBSERVATION':self.policy.decision_snapshot_stale_seconds,'ROLLOUT_HEALTH_OBSERVATION':self.policy.rollout_receipt_stale_seconds}.get(typ)
  if threshold is not None and (_time(self.policy.evaluation_timestamp)-_time(observed)).total_seconds()>threshold:return 'STALE','STALE_EVIDENCE'
  if not _artifact(a):return 'UNKNOWN','MISSING_EVIDENCE'
  return 'HEALTHY','OBSERVED'
 def correlate(self,**values):
  state='HEALTHY'; reason='CORRELATED'
  if values.get('expected_version_uuid') and values.get('version_uuid') and values['expected_version_uuid']!=values['version_uuid']: state,reason='MISMATCH','VERSION_MISMATCH'
  values.pop('expected_version_uuid',None); return KnowledgeIdentityCorrelation(**values,state=state,reason=reason)
 def assess_adoption(self,correlation):
  if correlation.state=='MISMATCH': state,reason='ADOPTION_MISMATCH',correlation.reason
  elif not correlation.version_uuid or not correlation.knowledge_uuid: state,reason='ADOPTION_UNKNOWN','MISSING_EVIDENCE'
  elif correlation.state=='STALE': state,reason='ADOPTION_STALE',correlation.reason
  elif not correlation.runtime_instance_id: state,reason='ADOPTION_PENDING','RUNTIME_INSTANCE_PENDING'
  else: state,reason='ADOPTION_CONFIRMED','IDENTITIES_CORRELATED'
  evidence=digest(correlation.to_dict()); return KnowledgeAdoptionAssessment(state,correlation.knowledge_uuid,correlation.version_uuid,correlation.runtime_instance_id,self.policy.evaluation_timestamp,reason,evidence)
 def compatibility(self,expected,actual):
  dimensions={k:('COMPATIBLE' if actual.get(k)==v else 'MISMATCH') for k,v in expected.items()}; compatible=all(v=='COMPATIBLE' for v in dimensions.values()); return ContractCompatibilityAssessment(compatible,dimensions,self.policy.evaluation_timestamp,'COMPATIBLE' if compatible else 'CONTRACT_MISMATCH',digest(dimensions))
