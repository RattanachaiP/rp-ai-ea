"""Deterministic incident coordination only; this module has no operational authority."""
from datetime import datetime, timedelta, timezone
from uuid import NAMESPACE_URL, uuid5
from .models import *
from .storage import IncidentResponseStorage
def _id(kind,body): return str(uuid5(NAMESPACE_URL,'pr172:'+kind+':'+digest(body)))
def _dt(v): return datetime.fromisoformat(str(v).replace('Z','+00:00'))
def _iso(v): return v.astimezone(timezone.utc).isoformat().replace('+00:00','Z')
class IncidentResponseOrchestrator:
 def __init__(self,policy=None,*,root='learning_data',storage=None): self.policy=policy or IncidentResponsePolicy(); self.storage=storage or IncidentResponseStorage(root); self.cases={}; self.states={}; self.events={}; self.reviews=set()
 def intake(self,evidence,*,incident_category=None,source='PR171_HEALTH_MONITOR',priority=None,impact='UNKNOWN_IMPACT',incident_window_start=None):
  """Validate immutable source evidence and create/replay a deterministic case."""
  if isinstance(evidence,dict): get=evidence.get
  else: get=lambda n,d='':getattr(evidence,n,d)
  authority=get('source_authority') or source
  digest_value=get('replay_digest') or get('evaluation_digest') or get('incident_digest') or get('digest')
  src=get('incident_uuid') or get('source_incident_uuid') or ''
  runtime=get('runtime_instance_id',''); knowledge=get('knowledge_uuid',''); version=get('version_uuid',''); registry=get('registry_snapshot_digest','')
  timestamp=incident_window_start or get('evaluation_timestamp') or get('observed_at') or self.policy.evaluation_timestamp
  category=incident_category or self._category(get('health_domain') or get('incident_type') or '')
  if not authority or not digest_value or not valid_digest(digest_value) or not valid_time(timestamp) or category not in CATEGORIES or source not in SOURCES or (src and not valid_uuid(src)): raise IncidentResponseError('INVALID_SOURCE_EVIDENCE')
  priority=priority or self._priority(get('severity',''))
  if priority not in PRIORITIES or impact not in IMPACTS: raise IncidentResponseError('INVALID_INCIDENT_CLASSIFICATION')
  identity={'source_incident_uuid':src,'category':category,'runtime':runtime,'knowledge':knowledge,'version':version,'registry':registry,'policy':self.policy.policy_version,'window':timestamp}
  iid=_id('case',identity); replay=digest({'identity':identity,'evidence':digest_value,'priority':priority,'impact':impact,'authority':authority})
  prior=self.cases.get(iid)
  if prior:
   if prior.replay_digest!=replay: raise IncidentResponseError('INCIDENT_CASE_REPLAY_MISMATCH')
   return prior
  item=IncidentCase(iid,src,category,source,runtime,knowledge,version,registry,timestamp,'CREATED',priority,impact,digest_value,replay,self.policy.policy_version,self.policy.architecture_version)
  self.storage.write('cases',iid,item); self.cases[iid]=item; self.states[iid]='CREATED'; self._event(item,'INCIDENT_CREATED','system',timestamp,iid,digest_value,'incident intake'); return item
 create_case=intake
 def triage(self,case):
  c=self._case(case); self.transition(c,'TRIAGED','system','triage completed')
  workflow=self._workflow(c); body={'case':c.incident_case_uuid,'workflow':workflow,'at':self.policy.evaluation_timestamp}; item=IncidentTriageAssessment(_id('triage',body),c.incident_case_uuid,c.priority,c.impact,True,True,workflow,self.policy.evaluation_timestamp,digest(body)); self.storage.write('triage',item.triage_uuid,item); return item
 def acknowledge(self,case,acknowledged_by,acknowledgement_reason,*,acknowledged_at=None):
  c=self._case(case); at=acknowledged_at or self.policy.evaluation_timestamp
  if not acknowledged_by or not acknowledgement_reason or not valid_time(at): raise IncidentResponseError('INVALID_ACKNOWLEDGEMENT')
  self.transition(c,'ACKNOWLEDGED',acknowledged_by,acknowledgement_reason,at=at)
  body={'case':c.incident_case_uuid,'by':acknowledged_by,'at':at,'reason':acknowledgement_reason}; item=IncidentAcknowledgement(_id('ack',body),c.incident_case_uuid,acknowledged_by,at,acknowledgement_reason,digest(body)); self.storage.write('acknowledgements',item.acknowledgement_uuid,item); return item
 def assign(self,case,assigned_to,assigned_by,assignment_reason,assignment_role='INCIDENT_OWNER',*,assigned_at=None):
  c=self._case(case); at=assigned_at or self.policy.evaluation_timestamp
  if not all((assigned_to,assigned_by,assignment_reason)) or assignment_role not in {'INCIDENT_OWNER','TECHNICAL_INVESTIGATOR','RUNTIME_OWNER','LEARNING_OWNER','GOVERNANCE_OWNER','SECURITY_REVIEWER','EXECUTIVE_APPROVER'} or not valid_time(at): raise IncidentResponseError('INVALID_INCIDENT_ASSIGNMENT')
  self.transition(c,'ASSIGNED',assigned_by,assignment_reason,at=at); body={'case':c.incident_case_uuid,'to':assigned_to,'by':assigned_by,'at':at,'role':assignment_role}; item=IncidentAssignment(_id('assignment',body),c.incident_case_uuid,assigned_to,assigned_by,at,assignment_reason,assignment_role,digest(body)); self.storage.write('assignments',item.assignment_uuid,item); return item
 def begin_investigation(self,case,actor): return self.transition(case,'INVESTIGATING',actor,'investigation started')
 def response_plan(self,case,*,response_type=None):
  c=self._case(case); workflow=response_type or self._workflow(c)
  if workflow not in WORKFLOWS: raise IncidentResponseError('INVALID_RESPONSE_WORKFLOW')
  self.transition(c,'RESPONSE_PLANNED','system','response plan created'); now=_dt(self.policy.evaluation_timestamp); expires=_iso(now+timedelta(seconds=self.policy.response_plan_ttl_seconds)); body={'case':c.incident_case_uuid,'workflow':workflow,'at':self.policy.evaluation_timestamp}; item=IncidentResponsePlan(_id('plan',body),c.incident_case_uuid,workflow,self.policy.evaluation_timestamp,expires,self.policy.policy_version,self.policy.architecture_version,recommended_actions=('human governance review',),rollback_review_required=workflow=='ROLLBACK_REVIEW',maintenance_review_required=workflow=='CONTROLLED_MAINTENANCE_REVIEW',emergency_review_required=workflow=='EMERGENCY_GOVERNANCE_REVIEW'); self.storage.write('plans',item.plan_uuid,item); self._event(c,'RESPONSE_PLAN_CREATED','system',self.policy.evaluation_timestamp,item.plan_uuid,digest(item.to_dict()),'non-executable plan'); return item
 def recommendation(self,case,reason='policy assessment'):
  c=self._case(case); typ={'P0_EMERGENCY':'EMERGENCY_GOVERNANCE_REVIEW_REQUIRED'}.get(c.priority, 'ROLLBACK_REVIEW_REQUIRED' if c.impact in {'RUNTIME_KNOWLEDGE_MISMATCH','CRITICAL_RUNTIME_RISK'} else 'CONTROLLED_MAINTENANCE_REVIEW_REQUIRED' if c.impact=='RUNTIME_SERVICE_DEGRADATION' else 'TECHNICAL_INVESTIGATION_REQUIRED'); body={'case':c.incident_case_uuid,'type':typ,'reason':reason}; item=IncidentGovernanceRecommendation(_id('recommendation',body),c.incident_case_uuid,typ,reason,self.policy.evaluation_timestamp); self.storage.write('recommendations',item.recommendation_uuid,item); return item
 def transition(self,case,state,actor,reason,*,at=None):
  c=self._case(case); prior=self.states[c.incident_case_uuid]
  if state not in TRANSITIONS.get(prior,set()): raise IncidentResponseError('INVALID_INCIDENT_CASE_TRANSITION')
  at=at or self.policy.evaluation_timestamp
  self.states[c.incident_case_uuid]=state; self._event(c,{'TRIAGED':'TRIAGE_COMPLETED','ACKNOWLEDGED':'ACKNOWLEDGED','ASSIGNED':'ASSIGNED','INVESTIGATING':'INVESTIGATION_STARTED','ESCALATED':'ESCALATED','RESPONSE_PLANNED':'RESPONSE_PLAN_CREATED','MONITORING_RECOVERY':'RECOVERY_MONITORING_STARTED','RESOLVED':'INCIDENT_RESOLVED','POST_INCIDENT_REVIEW':'POST_INCIDENT_REVIEW_STARTED','CLOSED':'INCIDENT_CLOSED'}.get(state,'GOVERNANCE_REVIEW_REQUESTED'),actor,at,c.incident_case_uuid,c.evidence_digest,reason); return state
 def resolve(self,case,recovery_assessment,*,actor='governance'):
  c=self._case(case)
  if getattr(recovery_assessment,'state',None)!='CONFIRMED' or not valid_uuid(getattr(recovery_assessment,'incident_uuid','')): raise IncidentResponseError('RESOLUTION_WITHOUT_CONFIRMED_RECOVERY')
  return self.transition(c,'RESOLVED',actor,'confirmed PR171 recovery evidence')
 def post_incident_review(self,case,reviewed_by,incident_summary,impact_summary,*,reviewed_at=None):
  c=self._case(case); at=reviewed_at or self.policy.evaluation_timestamp
  if not reviewed_by or not incident_summary or not impact_summary or not valid_time(at): raise IncidentResponseError('INVALID_POST_INCIDENT_REVIEW')
  self.transition(c,'POST_INCIDENT_REVIEW',reviewed_by,'review started',at=at); body={'case':c.incident_case_uuid,'by':reviewed_by,'at':at,'summary':incident_summary,'impact':impact_summary}; item=PostIncidentReview(_id('review',body),c.incident_case_uuid,incident_summary,impact_summary,reviewed_by,at,digest(body)); self.storage.write('post_incident_reviews',item.review_uuid,item); self.reviews.add(c.incident_case_uuid); return item
 def close(self,case,approved_by,reason,*,closed_at=None):
  c=self._case(case)
  if self.policy.require_post_incident_review and c.incident_case_uuid not in self.reviews: raise IncidentResponseError('CLOSURE_WITHOUT_POST_INCIDENT_REVIEW')
  if self.policy.require_human_closure and not approved_by: raise IncidentResponseError('CLOSURE_WITHOUT_HUMAN_APPROVAL')
  at=closed_at or self.policy.evaluation_timestamp; self.transition(c,'CLOSED',approved_by,reason,at=at); body={'case':c.incident_case_uuid,'by':approved_by,'at':at,'reason':reason}; item=IncidentClosureRecord(_id('closure',body),c.incident_case_uuid,approved_by,at,reason,digest(body)); self.storage.write('closures',item.closure_uuid,item); return item
 def _event(self,c,typ,actor,at,source_uuid,source_digest,reason):
  body={'case':c.incident_case_uuid,'type':typ,'actor':actor,'at':at,'source':source_uuid,'reason':reason}; item=IncidentTimelineEvent(_id('timeline',body),c.incident_case_uuid,typ,actor,at,source_uuid,source_digest,reason,self.policy.policy_version,self.policy.architecture_version); last=self.events.get(c.incident_case_uuid)
  if last and _dt(at)<_dt(last.occurred_at): raise IncidentResponseError('INVALID_INCIDENT_TIMELINE_CHRONOLOGY')
  self.storage.write('timelines',item.event_uuid,item); self.storage.write('history',item.event_uuid,item); self.events[c.incident_case_uuid]=item; return item
 def _case(self,x):
  key=x.incident_case_uuid if hasattr(x,'incident_case_uuid') else x
  if key not in self.cases: raise IncidentResponseError('UNKNOWN_INCIDENT_CASE')
  return self.cases[key]
 def _priority(self,severity): return {'EMERGENCY':'P0_EMERGENCY','CRITICAL':'P1_CRITICAL','ERROR':'P2_HIGH','WARNING':'P3_MEDIUM','INFO':'P5_INFORMATIONAL'}.get(severity,'P3_MEDIUM')
 def _category(self,v): return v if v in CATEGORIES else {'RUNTIME_HEARTBEAT':'RUNTIME_HEARTBEAT','ACTIVE_REGISTRY':'ACTIVE_REGISTRY','KNOWLEDGE_VERSION':'KNOWLEDGE_VERSION','OBSERVABILITY_PIPELINE':'OBSERVABILITY_PIPELINE'}.get(v,'UNKNOWN')
 def _workflow(self,c): return 'EMERGENCY_GOVERNANCE_REVIEW' if c.priority=='P0_EMERGENCY' else 'ROLLBACK_REVIEW' if c.impact in {'RUNTIME_KNOWLEDGE_MISMATCH','CRITICAL_RUNTIME_RISK'} else 'CONTROLLED_MAINTENANCE_REVIEW' if c.impact=='RUNTIME_SERVICE_DEGRADATION' else 'INVESTIGATE'
 # Explicit stable aliases; none confer runtime, registry, activation, or rollback authority.
 intake_incident = intake
 create_response_plan = response_plan
 assign_human = assign
 acknowledge_incident = acknowledge
 create_post_incident_review = post_incident_review
 close_incident = close
