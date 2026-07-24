"""Deterministic, fail-closed PR173 evidence analytics; it has no execution authority."""
from __future__ import annotations
from collections import defaultdict
from datetime import datetime
from hashlib import sha256
import json, math
from uuid import UUID
from .models import *

class KnowledgeAnalyticsError(ValueError): pass

def _json(value): return json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False, default=str)
def _digest(value): return sha256(_json(value).encode()).hexdigest()
def _time(value):
    try:
        parsed=datetime.fromisoformat(str(value).replace('Z','+00:00'))
        if parsed.tzinfo is None: raise ValueError
        return parsed
    except (TypeError, ValueError): raise KnowledgeAnalyticsError('INVALID_TIMESTAMP')
def _uuid(value, code):
    try: UUID(str(value))
    except (TypeError, ValueError, AttributeError): raise KnowledgeAnalyticsError(code)
def _mapping(value): return value.to_dict() if hasattr(value, 'to_dict') else value

class KnowledgeAnalyticsEngine:
    """Consumes caller-supplied immutable evidence only; never reads or changes Runtime/Registry."""
    analytics_version = 'PR173.1.0'
    def __init__(self, repository=None): self._repository=repository

    def analyze(self, evidence, *, created_at=None):
        rows=self._validate(evidence)
        # A report is intentionally one version only: mixing versions invalidates causality.
        versions={(r['knowledge_uuid'], r['knowledge_version']) for r in rows}
        if len({v for _, v in versions}) > 1: raise KnowledgeAnalyticsError('MIXED_KNOWLEDGE_VERSIONS')
        source_digest=_digest(rows); replay_digest=_digest([r['replay_digest'] for r in rows])
        at=created_at or max(r['timestamp'] for r in rows)
        _time(at)
        report=KnowledgeAnalyticsReport(
            analytics_uuid=_digest({'source_digest':source_digest,'version':self.analytics_version})[:32], analytics_version=self.analytics_version,
            created_at=at, source_digest=source_digest, replay_digest=replay_digest, knowledge_versions=tuple(versions),
            summary=self._summary(rows, replay_digest), feature_contributions=self._features(rows),
            failure_patterns=self._patterns(rows, False), success_patterns=self._patterns(rows, True),
            performance_profiles=self._profiles(rows), market_regimes=self._regimes(rows),
            indicator_contributions=self._indicators(rows), risk_contributions=self._risks(rows),
            confidence=self._confidence(rows), context_attribution=self._contexts(rows))
        if self._repository: self._repository.save(report)
        return report

    def _validate(self, evidence):
        if not isinstance(evidence, (tuple,list)) or not evidence: raise KnowledgeAnalyticsError('MISSING_EVIDENCE')
        rows=[]
        for raw in evidence:
            r=_mapping(raw)
            if not isinstance(r, dict): raise KnowledgeAnalyticsError('INVALID_EVIDENCE')
            for key in ('knowledge_uuid','knowledge_version','timestamp','replay_digest','outcome'):
                if key not in r or r[key] in ('',None): raise KnowledgeAnalyticsError('MISSING_EVIDENCE')
            _uuid(r['knowledge_uuid'],'INVALID_KNOWLEDGE_IDENTITY'); _time(r['timestamp'])
            if not isinstance(r['knowledge_version'],str): raise KnowledgeAnalyticsError('INVALID_KNOWLEDGE_VERSION')
            if not isinstance(r['replay_digest'],str) or len(r['replay_digest']) != 64: raise KnowledgeAnalyticsError('REPLAY_MISMATCH')
            if not isinstance(r['outcome'],(int,float)) or isinstance(r['outcome'],bool) or not math.isfinite(r['outcome']): raise KnowledgeAnalyticsError('INVALID_EVIDENCE')
            features=r.get('features',{})
            if not isinstance(features,dict) or any(not isinstance(k,str) or not k for k in features): raise KnowledgeAnalyticsError('UNKNOWN_FEATURE_IDENTITY')
            for field in ('indicators','risk_factors','context'):
                if field in r and not isinstance(r[field],dict): raise KnowledgeAnalyticsError('INVALID_EVIDENCE')
            rows.append({**r,'outcome':float(r['outcome']),'features':dict(features)})
        return sorted(rows,key=lambda x: (_time(x['timestamp']),x['knowledge_uuid'],_json(x)))

    def _summary(self, rows, replay):
        values=[r['outcome'] for r in rows]; wins=sum(v>0 for v in values)
        return AnalyticsSummary(len(rows),wins,sum(v<0 for v in values),sum(values),sum(values)/len(values),len({r['knowledge_version'] for r in rows}),replay)
    def _features(self, rows):
        groups=defaultdict(list)
        for r in rows:
            for k,v in r['features'].items(): groups[f'{k}={_json(v)}'].append(r['outcome'])
        overall=sum(r['outcome'] for r in rows)/len(rows)
        return tuple(FeatureContribution(k,len(v),sum(x>0 for x in v),sum(x<0 for x in v),sum(v)/len(v),sum(v)/len(v)-overall) for k,v in sorted(groups.items()))
    def _patterns(self, rows, success):
        grouped=defaultdict(list)
        for r in rows:
            for k,v in r['features'].items(): grouped[f'{k}={_json(v)}'].append(r['outcome'])
        answer=[]
        for key, values in sorted(grouped.items()):
            count=sum(v>0 for v in values) if success else sum(v<0 for v in values)
            if count: answer.append((key,count,len(values)))
        maker=SuccessPattern if success else FailurePattern
        return tuple(maker(_digest({'success':success,'condition':k})[:16],(k,),n,n/total) for k,n,total in answer)
    def _profiles(self, rows):
        groups=defaultdict(list)
        for r in rows: groups[(r['knowledge_uuid'],r['knowledge_version'])].append(r['outcome'])
        return tuple(KnowledgePerformanceProfile(k[0],k[1],len(v),sum(x>0 for x in v),sum(x<0 for x in v),sum(x>0 for x in v)/len(v),sum(v),sum(v)/len(v)) for k,v in sorted(groups.items()))
    def _regimes(self, rows): return self._categorize(rows,'context','regime',MarketRegimeProfile)
    def _indicators(self, rows):
        groups=self._groups(rows,'indicators'); return tuple(IndicatorContribution(k,len(v),sum(v)/len(v),sum(x>0 for x in v)/len(v)) for k,v in sorted(groups.items()))
    def _risks(self, rows):
        groups=self._groups(rows,'risk_factors'); return tuple(RiskContribution(k,len(v),sum(v)/len(v),sum(x<0 for x in v)/len(v)) for k,v in sorted(groups.items()))
    def _groups(self, rows, field):
        groups=defaultdict(list)
        for r in rows:
            for k,v in r.get(field,{}).items(): groups[f'{k}={_json(v)}'].append(r['outcome'])
        return groups
    def _categorize(self, rows, field, key, cls):
        groups=defaultdict(list)
        for r in rows:
            if key in r.get(field,{}): groups[str(r[field][key])].append(r['outcome'])
        return tuple(cls(k,len(v),sum(x>0 for x in v),sum(x<0 for x in v),sum(v)/len(v)) for k,v in sorted(groups.items()))
    def _confidence(self, rows):
        groups=defaultdict(list)
        for r in rows: groups[(r['knowledge_uuid'],r['knowledge_version'])].append(r['outcome'])
        return tuple(KnowledgeConfidence(k[0],k[1],len(v),min(1.,len(v)/30.),'HIGH' if len(v)>=30 else 'LOW') for k,v in sorted(groups.items()))
    def _contexts(self, rows):
        groups=self._groups(rows,'context'); return {k:{'sample_count':len(v),'average_outcome':sum(v)/len(v)} for k,v in sorted(groups.items())}
