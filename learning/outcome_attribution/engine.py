"""PR173 offline deterministic outcome attribution: advisory-only, descriptive, non-causal evidence."""
from __future__ import annotations
from collections import defaultdict
from datetime import datetime
from hashlib import sha256
from math import isfinite
import json
from uuid import UUID, uuid5
from .models import *
class KnowledgeOutcomeAttributionError(ValueError): pass
_NAMESPACE=UUID('4cf8a00f-0d91-5fd3-9c86-9173213a575a')
def _json(v): return json.dumps(v,sort_keys=True,separators=(',',':'),allow_nan=False)
def _digest(v): return sha256(_json(v).encode()).hexdigest()
def _support(n): return ('INSUFFICIENT_SUPPORT' if n<5 else 'LOW_SUPPORT' if n<15 else 'MEDIUM_SUPPORT' if n<30 else 'HIGH_SUPPORT')
def _confidence(n): return ('INSUFFICIENT' if n<5 else 'LOW' if n<15 else 'MEDIUM' if n<30 else 'HIGH')
def _canonical(v):
 if v is None or isinstance(v,(str,bool)): return v
 if isinstance(v,int) and not isinstance(v,bool): return v
 if isinstance(v,float) and isfinite(v): return v
 if isinstance(v,(list,tuple)): return tuple(_canonical(x) for x in v)
 if isinstance(v,dict):
  if any(not isinstance(k,str) or not k for k in v): raise KnowledgeOutcomeAttributionError('UNKNOWN_FEATURE_IDENTITY')
  return tuple((k,_canonical(v[k])) for k in sorted(v))
 raise KnowledgeOutcomeAttributionError('INVALID_EVIDENCE_VALUE')
def _plain(v): return {k:_plain(x) for k,x in v} if isinstance(v,tuple) and v and all(isinstance(x,tuple) and len(x)==2 and isinstance(x[0],str) for x in v) else [_plain(x) for x in v] if isinstance(v,tuple) else v
def _time(v):
 try:
  d=datetime.fromisoformat(str(v).replace('Z','+00:00'))
  if d.tzinfo is None: raise ValueError
  return d
 except (TypeError,ValueError): raise KnowledgeOutcomeAttributionError('INVALID_TIMESTAMP')
def _valid_digest(v): return isinstance(v,str) and len(v)==64 and all(c in '0123456789abcdef' for c in v.lower())
class KnowledgeOutcomeAttributionEngine:
 """Consumes supplied immutable evidence; no Runtime, Registry, or execution authority."""
 attribution_version='PR173.1.0'
 def __init__(self, repository=None): self._repository=repository
 def analyze(self,evidence):
  rows=self._validate(evidence); pairs={(r['knowledge_uuid'],r['knowledge_version']) for r in rows}
  if len(pairs)!=1: raise KnowledgeOutcomeAttributionError('MIXED_KNOWLEDGE_IDENTITIES')
  source=_digest(rows); replay=_digest([r['replay_digest'] for r in rows]); created=max(r['timestamp'] for r in rows)
  report=KnowledgeOutcomeAttributionReport(str(uuid5(_NAMESPACE,source)),self.attribution_version,created,source,replay,tuple(pairs),self._summary(rows,replay),self._features(rows),self._patterns(rows,False),self._patterns(rows,True),self._profiles(rows),self._regimes(rows),self._indicators(rows),self._risks(rows),self._confidence(rows),self._contexts(rows))
  if self._repository: self._repository.save(report)
  return report
 def _validate(self,evidence):
  if not isinstance(evidence,(list,tuple)) or not evidence: raise KnowledgeOutcomeAttributionError('MISSING_EVIDENCE')
  rows=[]
  for raw in evidence:
   r=raw.to_dict() if hasattr(raw,'to_dict') else raw
   if not isinstance(r,dict): raise KnowledgeOutcomeAttributionError('INVALID_EVIDENCE')
   required=('knowledge_uuid','knowledge_version','timestamp','replay_digest','outcome','outcome_metric','outcome_unit')
   if any(k not in r or r[k] in ('',None) for k in required): raise KnowledgeOutcomeAttributionError('MISSING_EVIDENCE')
   try: UUID(str(r['knowledge_uuid']))
   except (ValueError,TypeError,AttributeError): raise KnowledgeOutcomeAttributionError('INVALID_KNOWLEDGE_IDENTITY')
   _time(r['timestamp'])
   if not isinstance(r['knowledge_version'],str): raise KnowledgeOutcomeAttributionError('INVALID_KNOWLEDGE_VERSION')
   if not _valid_digest(r['replay_digest']): raise KnowledgeOutcomeAttributionError('REPLAY_MISMATCH')
   if not isinstance(r['outcome'],(int,float)) or isinstance(r['outcome'],bool) or not isfinite(r['outcome']): raise KnowledgeOutcomeAttributionError('INVALID_EVIDENCE')
   for field in ('features','indicators','risk_factors','context'):
    if field in r and not isinstance(r[field],dict): raise KnowledgeOutcomeAttributionError('INVALID_EVIDENCE')
   item={**r,'outcome':float(r['outcome'])}
   for field in ('features','indicators','risk_factors','context'): item[field]=_plain(_canonical(r.get(field,{})))
   rows.append(item)
  if len({(r['outcome_metric'],r['outcome_unit']) for r in rows})!=1: raise KnowledgeOutcomeAttributionError('MIXED_OUTCOME_UNITS')
  return sorted(rows,key=lambda r:(_time(r['timestamp']),r['knowledge_uuid'],_json(r)))
 def _split(self,v): return sum(x>0 for x in v),sum(x<0 for x in v),sum(x==0 for x in v)
 def _summary(self,rows,replay):
  v=[r['outcome'] for r in rows]; w,l,n=self._split(v); return AnalyticsSummary(len(v),w,l,n,sum(v),sum(v)/len(v),1,rows[0]['outcome_metric'],rows[0]['outcome_unit'],replay)
 def _groups(self,rows,field):
  d=defaultdict(list)
  for r in rows:
   for k,v in r[field].items(): d[f'{k}={_json(v)}'].append(r['outcome'])
  return d
 def _features(self,rows):
  overall=sum(r['outcome'] for r in rows)/len(rows); return tuple(FeatureContribution(k,len(v),sum(x>0 for x in v),sum(x<0 for x in v),sum(v)/len(v),sum(v)/len(v)-overall) for k,v in sorted(self._groups(rows,'features').items()))
 def _patterns(self,rows,success):
  C=SuccessPattern if success else FailurePattern; result=[]
  for k,v in sorted(self._groups(rows,'features').items()):
   count=sum(x>0 for x in v) if success else sum(x<0 for x in v)
   if count: result.append(C(_digest([success,k])[:16],(k,),len(v),count/len(v),_support(len(v))))
  return tuple(result)
 def _profiles(self,rows):
  v=[r['outcome'] for r in rows];w,l,n=self._split(v);r=rows[0];return (KnowledgePerformanceProfile(r['knowledge_uuid'],r['knowledge_version'],len(v),w,l,n,w/len(v),sum(v),sum(v)/len(v)),)
 def _regimes(self,rows):
  d=defaultdict(list)
  for r in rows:
   if 'regime' in r['context']: d[str(r['context']['regime'])].append(r['outcome'])
  return tuple(MarketRegimeProfile(k,len(v),*self._split(v),sum(v)/len(v)) for k,v in sorted(d.items()))
 def _indicators(self,rows): return tuple(IndicatorContribution(k,len(v),sum(v)/len(v),sum(x>0 for x in v)/len(v)) for k,v in sorted(self._groups(rows,'indicators').items()))
 def _risks(self,rows): return tuple(RiskContribution(k,len(v),sum(v)/len(v),sum(x<0 for x in v)/len(v)) for k,v in sorted(self._groups(rows,'risk_factors').items()))
 def _confidence(self,rows):
  r=rows[0];n=len(rows);return (KnowledgeConfidence(r['knowledge_uuid'],r['knowledge_version'],n,min(1,n/30),_confidence(n)),)
 def _contexts(self,rows): return {k:{'sample_count':len(v),'average_outcome':sum(v)/len(v),'observed_association':True} for k,v in sorted(self._groups(rows,'context').items())}
