"""Immutable contracts for PR174's structural and sample-sufficiency gate."""
from __future__ import annotations
from dataclasses import dataclass, field
from datetime import datetime
from math import isfinite
from typing import Any, Mapping
from uuid import UUID
from learning.common.immutable import freeze, thaw

_STATES = {"NOT_ELIGIBLE", "REQUIRES_MORE_DATA", "ELIGIBLE_FOR_PATTERN_MINING"}

def _uuid(value: object) -> bool:
 try: UUID(str(value)); return True
 except (TypeError, ValueError, AttributeError): return False
def _time(value: object) -> bool:
 try: return datetime.fromisoformat(str(value).replace('Z','+00:00')).tzinfo is not None
 except (TypeError, ValueError, AttributeError): return False
def _finite(value: object) -> bool: return isinstance(value,(int,float)) and not isinstance(value,bool) and isfinite(value)
def _json_safe(value: Any) -> bool:
 if value is None or isinstance(value,(str,bool)): return True
 if _finite(value): return True
 if isinstance(value,(tuple,list)): return all(_json_safe(x) for x in value)
 if isinstance(value,Mapping): return all(isinstance(k,str) and _json_safe(v) for k,v in value.items())
 return False

@dataclass(frozen=True)
class GovernedLearningPolicyConfig:
 minimum_pattern_samples:int=30
 supported_attribution_versions:tuple[str,...]=( "PR173.1.0",)
 supported_outcome_contracts:tuple[tuple[str,str],...]=(("REALIZED_PNL","USD"),("RETURN","PERCENT"),("R_MULTIPLE","R"),("NORMALIZED_REWARD","SCORE"))
 def __post_init__(self):
  versions=tuple(self.supported_attribution_versions); contracts=tuple(tuple(x) for x in self.supported_outcome_contracts)
  if not isinstance(self.minimum_pattern_samples,int) or isinstance(self.minimum_pattern_samples,bool) or self.minimum_pattern_samples<=0 or not versions or any(not isinstance(v,str) or not v for v in versions) or not contracts or any(len(c)!=2 or any(not isinstance(v,str) or not v for v in c) for c in contracts): raise ValueError('INVALID_GOVERNED_LEARNING_POLICY_CONFIG')
  object.__setattr__(self,'supported_attribution_versions',versions);object.__setattr__(self,'supported_outcome_contracts',contracts)
 def to_dict(self): return {'minimum_pattern_samples':self.minimum_pattern_samples,'supported_attribution_versions':list(self.supported_attribution_versions),'supported_outcome_contracts':[list(x) for x in self.supported_outcome_contracts]}

@dataclass(frozen=True)
class GovernedLearningPolicyReport:
 policy_uuid:str; policy_version:str; knowledge_uuid:str; knowledge_version:str; eligibility_state:str; sample_count:int; minimum_required_samples:int; additional_samples_required:int; hard_gates:Mapping[str,bool]=field(default_factory=dict); blocking_reasons:tuple[str,...]=(); warning_codes:tuple[str,...]=(); validation_summary:Mapping[str,Any]=field(default_factory=dict); generated_at:str=''; advisory_only:bool=True; sample_sufficiency_score:float=0.0
 def __post_init__(self):
  if not _uuid(self.policy_uuid) or not self.policy_version or not _uuid(self.knowledge_uuid) or not self.knowledge_version or self.eligibility_state not in _STATES or not all(isinstance(x,int) and not isinstance(x,bool) and x>=0 for x in (self.sample_count,self.additional_samples_required)) or not isinstance(self.minimum_required_samples,int) or isinstance(self.minimum_required_samples,bool) or self.minimum_required_samples<=0 or self.additional_samples_required!=max(0,self.minimum_required_samples-self.sample_count) or not isinstance(self.advisory_only,bool) or not self.advisory_only or not _time(self.generated_at) or not _finite(self.sample_sufficiency_score) or not 0<=self.sample_sufficiency_score<=1 or not isinstance(self.hard_gates,Mapping) or not all(isinstance(k,str) and isinstance(v,bool) for k,v in self.hard_gates.items()) or not all(isinstance(x,str) and x for x in self.blocking_reasons+self.warning_codes) or not _json_safe(self.validation_summary): raise ValueError('INVALID_GOVERNED_LEARNING_POLICY_REPORT')
  object.__setattr__(self,'hard_gates',freeze(dict(self.hard_gates)));object.__setattr__(self,'validation_summary',freeze(dict(self.validation_summary)));object.__setattr__(self,'blocking_reasons',tuple(self.blocking_reasons));object.__setattr__(self,'warning_codes',tuple(self.warning_codes));object.__setattr__(self,'sample_sufficiency_score',float(self.sample_sufficiency_score))
 def to_dict(self): return {name:thaw(getattr(self,name)) for name in self.__dataclass_fields__}
