"""Immutable PR173 contracts for offline, non-causal outcome attribution evidence."""
from __future__ import annotations
from dataclasses import dataclass, asdict, field
from datetime import datetime
from math import isfinite
from typing import Any, Mapping
from uuid import UUID
from learning.common.immutable import freeze, thaw


def _uuid(value):
    try: UUID(str(value)); return True
    except (ValueError, TypeError, AttributeError): return False
def _time(value):
    try: return datetime.fromisoformat(str(value).replace('Z','+00:00')).tzinfo is not None
    except (ValueError, TypeError, AttributeError): return False
def _digest(value): return isinstance(value,str) and len(value)==64 and all(c in '0123456789abcdef' for c in value.lower())
def _number(value): return isinstance(value,(int,float)) and not isinstance(value,bool) and isfinite(value)
def _rate(value): return _number(value) and 0 <= value <= 1
def _counts(sample,wins,losses,neutral): return all(isinstance(x,int) and not isinstance(x,bool) and x>=0 for x in (sample,wins,losses,neutral)) and wins+losses+neutral==sample

@dataclass(frozen=True)
class FeatureContribution:
 feature_id:str; sample_count:int; success_count:int; failure_count:int; average_outcome:float; contribution:float
 def __post_init__(self):
  if not self.feature_id or not _counts(self.sample_count,self.success_count,self.failure_count,self.sample_count-self.success_count-self.failure_count) or not all(_number(x) for x in (self.average_outcome,self.contribution)): raise ValueError('INVALID_FEATURE_CONTRIBUTION')
 def to_dict(self): return asdict(self)
@dataclass(frozen=True)
class IndicatorContribution:
 indicator_id:str; sample_count:int; contribution:float; success_rate:float
 def __post_init__(self):
  if not self.indicator_id or self.sample_count<0 or not _number(self.contribution) or not _rate(self.success_rate): raise ValueError('INVALID_INDICATOR_CONTRIBUTION')
 def to_dict(self): return asdict(self)
@dataclass(frozen=True)
class RiskContribution:
 risk_factor:str; sample_count:int; average_outcome:float; failure_rate:float
 def __post_init__(self):
  if not self.risk_factor or self.sample_count<0 or not _number(self.average_outcome) or not _rate(self.failure_rate): raise ValueError('INVALID_RISK_CONTRIBUTION')
 def to_dict(self): return asdict(self)
@dataclass(frozen=True)
class FailurePattern:
 pattern_id:str; conditions:tuple[str,...]; occurrence_count:int; failure_rate:float; support_classification:str
 def __post_init__(self):
  if not self.pattern_id or not self.conditions or self.occurrence_count<0 or not _rate(self.failure_rate) or self.support_classification not in {'INSUFFICIENT_SUPPORT','LOW_SUPPORT','MEDIUM_SUPPORT','HIGH_SUPPORT'}: raise ValueError('INVALID_FAILURE_PATTERN')
 def to_dict(self): return asdict(self)
@dataclass(frozen=True)
class SuccessPattern:
 pattern_id:str; conditions:tuple[str,...]; occurrence_count:int; success_rate:float; support_classification:str
 def __post_init__(self):
  if not self.pattern_id or not self.conditions or self.occurrence_count<0 or not _rate(self.success_rate) or self.support_classification not in {'INSUFFICIENT_SUPPORT','LOW_SUPPORT','MEDIUM_SUPPORT','HIGH_SUPPORT'}: raise ValueError('INVALID_SUCCESS_PATTERN')
 def to_dict(self): return asdict(self)
@dataclass(frozen=True)
class KnowledgePerformanceProfile:
 knowledge_uuid:str; knowledge_version:str; sample_count:int; wins:int; losses:int; neutral_count:int; win_rate:float; total_outcome:float; average_outcome:float
 def __post_init__(self):
  if not _uuid(self.knowledge_uuid) or not self.knowledge_version or not _counts(self.sample_count,self.wins,self.losses,self.neutral_count) or not _rate(self.win_rate) or not _number(self.total_outcome) or not _number(self.average_outcome): raise ValueError('INVALID_PERFORMANCE_PROFILE')
 def to_dict(self): return asdict(self)
@dataclass(frozen=True)
class MarketRegimeProfile:
 regime_id:str; sample_count:int; wins:int; losses:int; neutral_count:int; average_outcome:float
 def __post_init__(self):
  if not self.regime_id or not _counts(self.sample_count,self.wins,self.losses,self.neutral_count) or not _number(self.average_outcome): raise ValueError('INVALID_REGIME_PROFILE')
 def to_dict(self): return asdict(self)
@dataclass(frozen=True)
class KnowledgeConfidence:
 knowledge_uuid:str; knowledge_version:str; sample_count:int; sample_support:float; classification:str
 def __post_init__(self):
  if not _uuid(self.knowledge_uuid) or not self.knowledge_version or self.sample_count<0 or not _rate(self.sample_support) or self.classification not in {'INSUFFICIENT','LOW','MEDIUM','HIGH'}: raise ValueError('INVALID_SAMPLE_SUPPORT_CONFIDENCE')
 def to_dict(self): return asdict(self)
@dataclass(frozen=True)
class AnalyticsSummary:
 trade_count:int; winning_trade_count:int; losing_trade_count:int; neutral_count:int; total_outcome:float; average_outcome:float; knowledge_version_count:int; outcome_metric:str; outcome_unit:str; replay_digest:str
 def __post_init__(self):
  if not _counts(self.trade_count,self.winning_trade_count,self.losing_trade_count,self.neutral_count) or not all(_number(x) for x in (self.total_outcome,self.average_outcome)) or self.knowledge_version_count!=1 or not self.outcome_metric or not self.outcome_unit or not _digest(self.replay_digest): raise ValueError('INVALID_ANALYTICS_SUMMARY')
 def to_dict(self): return asdict(self)
@dataclass(frozen=True)
class KnowledgeOutcomeAttributionReport:
 attribution_uuid:str; attribution_version:str; created_at:str; source_digest:str; replay_digest:str; knowledge_versions:tuple[tuple[str,str],...]; summary:AnalyticsSummary; feature_contributions:tuple[FeatureContribution,...]=(); failure_patterns:tuple[FailurePattern,...]=(); success_patterns:tuple[SuccessPattern,...]=(); performance_profiles:tuple[KnowledgePerformanceProfile,...]=(); market_regimes:tuple[MarketRegimeProfile,...]=(); indicator_contributions:tuple[IndicatorContribution,...]=(); risk_contributions:tuple[RiskContribution,...]=(); confidence:tuple[KnowledgeConfidence,...]=(); context_attribution:Mapping[str,Any]=field(default_factory=dict); advisory_only:bool=True
 def __post_init__(self):
  if not _uuid(self.attribution_uuid) or not self.attribution_version or not _time(self.created_at) or not _digest(self.source_digest) or not _digest(self.replay_digest) or len(self.knowledge_versions)!=1 or not all(_uuid(k) and isinstance(v,str) and v for k,v in self.knowledge_versions) or not self.advisory_only: raise ValueError('INVALID_OUTCOME_ATTRIBUTION_REPORT')
  object.__setattr__(self,'knowledge_versions',tuple(tuple(x) for x in self.knowledge_versions)); object.__setattr__(self,'context_attribution',freeze(dict(self.context_attribution)))
 def to_dict(self):
  result={name:getattr(self,name) for name in self.__dataclass_fields__}; result['knowledge_versions']=[list(x) for x in self.knowledge_versions]; result['summary']=self.summary.to_dict(); result['context_attribution']=thaw(self.context_attribution)
  for name in ('feature_contributions','failure_patterns','success_patterns','performance_profiles','market_regimes','indicator_contributions','risk_contributions','confidence'): result[name]=[x.to_dict() for x in result[name]]
  return result
