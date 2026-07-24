from __future__ import annotations
from dataclasses import dataclass
from datetime import datetime
from uuid import NAMESPACE_URL,uuid5
from .models import *
def _dt(v): return datetime.fromisoformat(str(v).replace('Z','+00:00'))
def _report(kind,start,end,observations,incidents=()):
 if not valid_time(start) or not valid_time(end) or _dt(end)<=_dt(start): raise RuntimeKnowledgeObservabilityError('INVALID_REPORT_BOUNDARY')
 window=tuple(o for o in observations if _dt(start)<=_dt(o.observed_at)<_dt(end))
 states={s:sum(o.state==s for o in window) for s in OBSERVATION_STATES}; latencies={'gateway':[],'applicability':[]}
 # latency may live only in reason detail in generic source observations, so retain deterministic zero-free aggregates.
 body={'kind':kind,'start':start,'end':end,'observation_uuids':[o.observation_uuid for o in window],'incident_uuids':[i.incident_uuid for i in incidents], 'states':states}
 rid=str(uuid5(NAMESPACE_URL,'pr170-report:'+digest(body))); return body,rid,digest(body)
@dataclass(frozen=True)
class RuntimeKnowledgeDailyReport:
 report_uuid:str; day_start:str; day_end:str; total_observations:int; state_counts:Mapping[str,int]; unresolved_incident_count:int; digest:str
 def to_dict(self): return {n:(dict(getattr(self,n)) if n=='state_counts' else getattr(self,n)) for n in self.__dataclass_fields__}
@dataclass(frozen=True)
class RuntimeKnowledgeWeeklyReport:
 report_uuid:str; week_start:str; week_end:str; total_observations:int; state_counts:Mapping[str,int]; unresolved_incident_count:int; digest:str
 def to_dict(self): return {n:(dict(getattr(self,n)) if n=='state_counts' else getattr(self,n)) for n in self.__dataclass_fields__}
def daily_report(start,end,observations,incidents=()):
 body,rid,d=_report('daily',start,end,observations,incidents); return RuntimeKnowledgeDailyReport(rid,start,end,len(body['observation_uuids']),body['states'],sum(not i.resolved for i in incidents),d)
def weekly_report(start,end,observations,incidents=()):
 if (_dt(end)-_dt(start)).total_seconds()!=604800: raise RuntimeKnowledgeObservabilityError('INVALID_REPORT_BOUNDARY')
 body,rid,d=_report('weekly',start,end,observations,incidents); return RuntimeKnowledgeWeeklyReport(rid,start,end,len(body['observation_uuids']),body['states'],sum(not i.resolved for i in incidents),d)
