"""Evidence-only deterministic PR171 health evaluator; it has no runtime authority."""
from __future__ import annotations
from datetime import datetime, timedelta, timezone
from uuid import NAMESPACE_URL, uuid5
from .models import *
from .storage import RuntimeHealthMonitorStorage

_PRIORITY={'HEALTHY':0,'RECOVERED':1,'RECOVERING':2,'UNKNOWN':3,'DEGRADED':4,'STALE':5,'UNSTABLE':6,'MISMATCH':7,'FAILED':8}
_SEVERITY={'HEALTHY':'INFO','RECOVERED':'INFO','RECOVERING':'WARNING','UNKNOWN':'WARNING','DEGRADED':'WARNING','STALE':'ERROR','UNSTABLE':'ERROR','MISMATCH':'CRITICAL','FAILED':'CRITICAL'}
_DOMAIN={'RUNTIME_HEARTBEAT_OBSERVATION':'RUNTIME_HEARTBEAT','REGISTRY_STATE_OBSERVATION':'ACTIVE_REGISTRY','KNOWLEDGE_VERSION_OBSERVATION':'KNOWLEDGE_VERSION','GATEWAY_LOAD_OBSERVATION':'RUNTIME_GATEWAY','APPLICABILITY_OBSERVATION':'KNOWLEDGE_APPLICABILITY','DECISION_KNOWLEDGE_OBSERVATION':'DECISION_KNOWLEDGE_INTERFACE','ROLLOUT_HEALTH_OBSERVATION':'ROLLOUT_ADOPTION','ACTIVATION_ADOPTION_OBSERVATION':'ACTIVATION_ADOPTION','ROLLBACK_ADOPTION_OBSERVATION':'ROLLBACK_ADOPTION','CONTRACT_COMPATIBILITY_OBSERVATION':'CONTRACT_COMPATIBILITY','IDENTITY_MISMATCH_OBSERVATION':'IDENTITY_CORRELATION','RUNTIME_EXCEPTION_OBSERVATION':'OBSERVABILITY_PIPELINE','STALE_STATE_OBSERVATION':'OBSERVABILITY_PIPELINE'}
_INCIDENT={'RUNTIME_HEARTBEAT':'HEARTBEAT_STALE_PERSISTENT','ACTIVE_REGISTRY':'REGISTRY_STALE_PERSISTENT','KNOWLEDGE_VERSION':'VERSION_MISMATCH_PERSISTENT','RUNTIME_GATEWAY':'GATEWAY_LOAD_FAILURE_PERSISTENT','KNOWLEDGE_APPLICABILITY':'APPLICABILITY_FAILURE_PERSISTENT','DECISION_KNOWLEDGE_INTERFACE':'DECISION_KNOWLEDGE_MISMATCH','ROLLOUT_ADOPTION':'ROLLOUT_ADOPTION_FAILURE','ACTIVATION_ADOPTION':'ACTIVATION_ADOPTION_FAILURE','ROLLBACK_ADOPTION':'ROLLBACK_ADOPTION_FAILURE','CONTRACT_COMPATIBILITY':'CONTRACT_MISMATCH_PERSISTENT','IDENTITY_CORRELATION':'IDENTITY_CORRELATION_FAILURE','OBSERVABILITY_PIPELINE':'OBSERVABILITY_PIPELINE_FAILURE'}
def _dt(v): return datetime.fromisoformat(str(v).replace('Z','+00:00'))
def _iso(v): return v.astimezone(timezone.utc).isoformat().replace('+00:00','Z')
def _asdict(v): return v.to_dict() if hasattr(v,'to_dict') else dict(v)
def _id(kind, body): return str(uuid5(NAMESPACE_URL,'pr171:'+kind+':'+digest(body)))
class RuntimeHealthMonitor:
 """Consumes PR170 artifacts only and emits advisory evidence only."""
 def __init__(self,policy=None,*,root='learning_data',storage=None): self.policy=policy or RuntimeHealthMonitorPolicy(); self.storage=storage or RuntimeHealthMonitorStorage(root); self._lifecycle={}; self._incidents={}
 def evaluate(self, observations, *, health_domain=None, source_incidents=()):
  obs=tuple(observations)
  if not obs: raise RuntimeHealthMonitorError('MISSING_SOURCE_EVIDENCE')
  for o in obs:
   if not valid_uuid(getattr(o,'observation_uuid','')) or not valid_time(getattr(o,'observed_at','')) or not valid_digest(getattr(o,'replay_digest','')): raise RuntimeHealthMonitorError('INVALID_SOURCE_EVIDENCE')
  domain=health_domain or _DOMAIN.get(obs[-1].observation_type)
  if domain not in DOMAINS: raise RuntimeHealthMonitorError('INVALID_HEALTH_DOMAIN')
  base=sorted(obs,key=lambda o:o.observed_at); states=[o.state for o in base]
  now=_dt(self.policy.evaluation_timestamp); latest=states[-1]; state=latest
  transitions=sum(a!=b for a,b in zip(states,states[1:]))
  within=[o for o in base if (now-_dt(o.observed_at)).total_seconds()<=self.policy.flapping_window_seconds]
  if len(within)>1 and transitions>=self.policy.flapping_transition_threshold: state='UNSTABLE'; reason='HEALTH_STATE_FLAPPING'
  elif latest=='FAILED' and sum(x=='FAILED' for x in states[-self.policy.failure_threshold_count:])>=self.policy.failure_threshold_count: state='FAILED'; reason='PERSISTENT_FAILURE'
  elif latest=='STALE' and sum(x=='STALE' for x in states[-self.policy.degraded_threshold_count:])>=self.policy.degraded_threshold_count: state='STALE'; reason='PERSISTENT_STALE'
  elif latest=='MISMATCH': state='MISMATCH'; reason='VERSION_MISMATCH_PERSISTENT'
  else: reason=getattr(base[-1],'reason_code','OBSERVED')
  first=base[-1]; evidence=[o.observation_uuid for o in base]; srcinc=tuple(getattr(i,'incident_uuid',str(i)) for i in source_incidents)
  identity={'runtime':first.runtime_instance_id,'knowledge':first.knowledge_uuid,'version':first.version_uuid,'registry':first.registry_snapshot_digest,'domain':domain,'observations':evidence,'incidents':srcinc,'policy':self.policy.policy_version,'at':self.policy.evaluation_timestamp}
  replay=digest({'identity':identity,'states':states,'reason':reason}); eid=_id('evaluation',identity)
  result=RuntimeHealthEvaluation(eid,first.runtime_instance_id,first.knowledge_uuid,first.version_uuid,first.registry_snapshot_digest,domain,state,_SEVERITY[state],reason,reason,tuple(evidence),srcinc,self.policy.evaluation_timestamp,self.policy.policy_version,self.policy.architecture_version,digest(identity),replay)
  self.storage.write('evaluations',eid,result)
  state_item=RuntimeHealthState(_id('state',{'evaluation':eid,'state':state}),eid,state,domain,self.policy.evaluation_timestamp,digest(result.to_dict()))
  self.storage.write('states',state_item.state_uuid,state_item)
  counts={s:states.count(s) for s in HEALTH_STATES}; trend=RuntimeHealthTrend(_id('trend',{'evaluation':eid}),eid,counts,self._tail(states,'FAILED'),self._tail(states,'STALE'),transitions,self.policy.evaluation_timestamp,digest({'counts':counts,'transitions':transitions}))
  self.storage.write('trends',trend.trend_uuid,trend)
  return result
 def assess(self,observations,**kwargs): return self.evaluate(observations,**kwargs)
 def correlate_incident(self,evaluation):
  if evaluation.state in {'HEALTHY','RECOVERED','RECOVERING'}: return None
  typ='HEALTH_STATE_FLAPPING' if evaluation.reason_code=='HEALTH_STATE_FLAPPING' else ('UNKNOWN_HEALTH_PERSISTENT' if evaluation.state=='UNKNOWN' else _INCIDENT[evaluation.health_domain])
  key={'type':typ,'runtime':evaluation.runtime_instance_id,'knowledge':evaluation.knowledge_uuid,'version':evaluation.version_uuid,'registry':evaluation.registry_snapshot_digest,'sources':evaluation.source_observation_uuids,'policy':evaluation.policy_version}
  iid=_id('incident',key); existing=self._incidents.get(iid)
  if existing: return existing
  correlation=RuntimeHealthIncidentCorrelation(_id('correlation',key),iid,typ,evaluation.evaluation_uuid,evaluation.source_observation_uuids[-1],evaluation.evaluation_timestamp,digest(key))
  self.storage.write('correlations',correlation.correlation_uuid,correlation); self._incidents[iid]=correlation
  self.transition(iid,'DETECTED','INCIDENT_DETECTED',at=evaluation.evaluation_timestamp); self.transition(iid,'OPEN','INCIDENT_OPEN',at=evaluation.evaluation_timestamp)
  return correlation
 def transition(self,incident_uuid,state,reason,*,at=None,acknowledged_by='',acknowledgement_reason=''):
  allowed={'DETECTED':{'OPEN'},'OPEN':{'ACKNOWLEDGED','SUPPRESSED','EXPIRED'},'ACKNOWLEDGED':{'INVESTIGATING'},'INVESTIGATING':{'ESCALATED'},'ESCALATED':{'MITIGATION_PENDING'},'MITIGATION_PENDING':{'RECOVERING'},'RECOVERING':{'RESOLVED'},'RESOLVED':{'CLOSED'}}
  prior=self._lifecycle.get(incident_uuid); previous=prior.state if prior else None
  if previous and state not in allowed.get(previous,set()): raise RuntimeHealthMonitorError('INVALID_INCIDENT_LIFECYCLE_TRANSITION')
  if not previous and state!='DETECTED': raise RuntimeHealthMonitorError('INVALID_INCIDENT_LIFECYCLE_TRANSITION')
  at=at or self.policy.evaluation_timestamp
  if state=='ACKNOWLEDGED' and (not acknowledged_by or not acknowledgement_reason): raise RuntimeHealthMonitorError('INVALID_ACKNOWLEDGEMENT')
  item=RuntimeHealthIncidentLifecycle(_id('lifecycle',{'incident':incident_uuid,'state':state,'at':at,'reason':reason}),incident_uuid,state,at,reason,acknowledged_by,at if state=='ACKNOWLEDGED' else '',acknowledgement_reason,digest({'incident':incident_uuid,'state':state,'at':at,'reason':reason}))
  self.storage.write('lifecycle',item.lifecycle_uuid,item); self.storage.write('history',item.lifecycle_uuid,item); self._lifecycle[incident_uuid]=item; return item
 def acknowledge(self,incident_uuid,acknowledged_by,acknowledgement_reason,*,acknowledged_at=None): return self.transition(incident_uuid,'ACKNOWLEDGED','MANUAL_ACKNOWLEDGEMENT',at=acknowledged_at or self.policy.evaluation_timestamp,acknowledged_by=acknowledged_by,acknowledgement_reason=acknowledgement_reason)
 def assess_recovery(self,incident_uuid,healthy_evidence):
  if not healthy_evidence: raise RuntimeHealthMonitorError('RECOVERY_WITHOUT_EVIDENCE')
  count=sum(getattr(x,'state','')=='HEALTHY' for x in healthy_evidence); state='CONFIRMED' if count>=self.policy.recovery_confirmation_count else 'PENDING'; now=self.policy.evaluation_timestamp
  body={'incident':incident_uuid,'count':count,'policy':self.policy.policy_version,'at':now}; item=RuntimeHealthRecoveryAssessment(_id('recovery',body),incident_uuid,state,count,self.policy.recovery_confirmation_count,now,'RECOVERY_CONFIRMED' if state=='CONFIRMED' else 'RECOVERY_NOT_CONFIRMED',digest(body)); self.storage.write('recovery',item.recovery_assessment_uuid,item); return item
 def recommend(self,evaluation,incident_uuid=''):
  type_='EMERGENCY_REVIEW_REQUIRED' if evaluation.severity=='EMERGENCY' else 'ROLLBACK_REVIEW_RECOMMENDED' if evaluation.state in {'FAILED','MISMATCH'} else 'MANUAL_REVIEW_REQUIRED'
  now=_dt(self.policy.evaluation_timestamp); expires=_iso(now+timedelta(seconds=self.policy.incident_expiration_seconds)); body={'evaluation':evaluation.evaluation_uuid,'incident':incident_uuid,'type':type_,'at':self.policy.evaluation_timestamp}; item=RuntimeHealthGovernanceRecommendation(_id('recommendation',body),evaluation.evaluation_uuid,incident_uuid,type_,evaluation.severity,evaluation.reason_code,self.policy.evaluation_timestamp,expires,self.policy.policy_version,self.policy.architecture_version,(evaluation.evaluation_digest,evaluation.replay_digest)); self.storage.write('recommendations',item.recommendation_uuid,item); return item
 @staticmethod
 def _tail(values,state):
  n=0
  for value in reversed(values):
   if value!=state: break
   n+=1
  return n
