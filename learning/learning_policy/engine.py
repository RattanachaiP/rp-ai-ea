"""PR174: deterministic structural and sample-sufficiency eligibility only."""
from __future__ import annotations
from datetime import datetime
from hashlib import sha256
import json
from math import isfinite
from typing import Any
from uuid import UUID, uuid5
from learning.outcome_attribution import KnowledgeOutcomeAttributionReport
from .exceptions import GovernedLearningPolicyError
from .models import GovernedLearningPolicyConfig, GovernedLearningPolicyReport
_NAMESPACE=UUID('4b4c2052-2f11-59ac-8fd4-469495b8be2e')
def _json(v): return json.dumps(v,sort_keys=True,separators=(',',':'),allow_nan=False)
def _digest(v): return isinstance(v,str) and len(v)==64 and all(c in '0123456789abcdef' for c in v.lower())
def _uuid(v):
 try: UUID(str(v));return True
 except (TypeError,ValueError,AttributeError):return False
def _time(v):
 try:return datetime.fromisoformat(str(v).replace('Z','+00:00')).tzinfo is not None
 except (TypeError,ValueError,AttributeError):return False
def _finite(v):return isinstance(v,(int,float)) and not isinstance(v,bool) and isfinite(v)
def _confidence(n): return 'INSUFFICIENT' if n<5 else 'LOW' if n<15 else 'MEDIUM' if n<30 else 'HIGH'

class GovernedLearningPolicyEngine:
 """Validates one PR173 report for future offline pattern-mining entry; no execution authority."""
 policy_version='PR174.2.0'
 def __init__(self,config:GovernedLearningPolicyConfig|None=None,repository=None): self.config=config or GovernedLearningPolicyConfig();self._repository=repository
 def evaluate(self,attribution:KnowledgeOutcomeAttributionReport)->GovernedLearningPolicyReport:
  facts=self._validate(attribution); n=facts['sample_count']; minimum=self.config.minimum_pattern_samples; additional=max(0,minimum-n)
  state='NOT_ELIGIBLE' if n==0 else 'REQUIRES_MORE_DATA' if additional else 'ELIGIBLE_FOR_PATTERN_MINING'
  blocking=('ZERO_SAMPLE_REPORT',) if n==0 else ('MINIMUM_SAMPLE_THRESHOLD_NOT_MET',) if additional else ()
  warnings=() if blocking else ('ELIGIBILITY_DOES_NOT_IMPLY_STABILITY','ELIGIBILITY_DOES_NOT_IMPLY_PROMOTION')
  gates={'structural_validity':True,'identity_consistency':True,'outcome_contract_consistency':True,'replay_integrity':True}
  identity={'policy_version':self.policy_version,'config':self.config.to_dict(),'source_attribution_uuid':attribution.attribution_uuid,'source_digest':attribution.source_digest,'replay_digest':attribution.replay_digest,'knowledge_uuid':facts['knowledge_uuid'],'knowledge_version':facts['knowledge_version'],'outcome_metric':facts['outcome_metric'],'outcome_unit':facts['outcome_unit'],'sample_count':n,'minimum_required_samples':minimum,'eligibility_state':state,'hard_gates':gates,'blocking_reasons':blocking,'warning_codes':warnings}
  report=GovernedLearningPolicyReport(str(uuid5(_NAMESPACE,sha256(_json(identity).encode()).hexdigest())),self.policy_version,facts['knowledge_uuid'],facts['knowledge_version'],state,n,minimum,additional,gates,blocking,warnings,{'source_attribution_uuid':attribution.attribution_uuid,'source_digest':attribution.source_digest,'replay_digest':attribution.replay_digest,'outcome_contract':[facts['outcome_metric'],facts['outcome_unit']],'eligibility_scope':'OFFLINE_PATTERN_MINING_EVALUATION_ONLY'},attribution.created_at,True,min(1.0,n/minimum))
  if self._repository:self._repository.save(report)
  return report
 assess=evaluate
 def _validate(self,a:Any)->dict[str,Any]:
  if not isinstance(a,KnowledgeOutcomeAttributionReport):raise GovernedLearningPolicyError('INVALID_OUTCOME_ATTRIBUTION_REPORT')
  try:_json(a.to_dict())
  except (TypeError,ValueError,OverflowError) as e:raise GovernedLearningPolicyError('INVALID_NESTED_REPORT_CONTENT') from e
  if not a.advisory_only or not _uuid(a.attribution_uuid) or not _digest(a.source_digest) or not _digest(a.replay_digest) or not _time(a.created_at):raise GovernedLearningPolicyError('INVALID_ATTRIBUTION_EVIDENCE')
  if a.attribution_version not in self.config.supported_attribution_versions:raise GovernedLearningPolicyError('UNSUPPORTED_ATTRIBUTION_VERSION')
  if len(a.knowledge_versions)!=1:raise GovernedLearningPolicyError('MIXED_KNOWLEDGE_IDENTITIES')
  k,v=a.knowledge_versions[0];s=a.summary
  if not _uuid(k) or not isinstance(v,str) or not v:raise GovernedLearningPolicyError('INVALID_KNOWLEDGE_IDENTITY')
  if (s.outcome_metric,s.outcome_unit) not in self.config.supported_outcome_contracts:raise GovernedLearningPolicyError('UNSUPPORTED_OUTCOME_CONTRACT')
  if s.replay_digest!=a.replay_digest:raise GovernedLearningPolicyError('REPLAY_MISMATCH')
  counts=(s.trade_count,s.winning_trade_count,s.losing_trade_count,s.neutral_count)
  if not all(isinstance(x,int) and not isinstance(x,bool) and x>=0 for x in counts) or sum(counts[1:])!=counts[0] or not all(_finite(x) for x in (s.total_outcome,s.average_outcome)):raise GovernedLearningPolicyError('INVALID_OUTCOME_EVIDENCE')
  if len(a.performance_profiles)!=1 or len(a.confidence)!=1:raise GovernedLearningPolicyError('MIXED_KNOWLEDGE_IDENTITIES')
  p,c=a.performance_profiles[0],a.confidence[0]
  if (p.knowledge_uuid,p.knowledge_version)!=(k,v):raise GovernedLearningPolicyError('INCONSISTENT_PROFILE_IDENTITY')
  if (c.knowledge_uuid,c.knowledge_version)!=(k,v):raise GovernedLearningPolicyError('INCONSISTENT_CONFIDENCE_IDENTITY')
  if (p.sample_count,p.wins,p.losses,p.neutral_count,p.total_outcome,p.average_outcome)!=(s.trade_count,s.winning_trade_count,s.losing_trade_count,s.neutral_count,s.total_outcome,s.average_outcome):raise GovernedLearningPolicyError('INCONSISTENT_PROFILE_SUMMARY')
  if c.sample_count!=s.trade_count or not _finite(c.sample_support) or c.sample_support!=min(1,s.trade_count/30) or c.classification!=_confidence(s.trade_count):raise GovernedLearningPolicyError('INCONSISTENT_CONFIDENCE')
  return {'knowledge_uuid':k,'knowledge_version':v,'sample_count':s.trade_count,'outcome_metric':s.outcome_metric,'outcome_unit':s.outcome_unit}
