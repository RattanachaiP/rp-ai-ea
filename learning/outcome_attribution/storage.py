"""Atomic, append-only, replay-safe persistence for PR173 attribution reports."""
from __future__ import annotations
from pathlib import Path
import json, os, tempfile
from uuid import UUID
from .models import (AnalyticsSummary, FailurePattern, FeatureContribution,
                     IndicatorContribution, KnowledgeConfidence,
                     KnowledgeOutcomeAttributionReport, KnowledgePerformanceProfile,
                     MarketRegimeProfile, RiskContribution, SuccessPattern)
class KnowledgeOutcomeAttributionRepository:
 def __init__(self,root='learning_data'): self.root=Path(root)/'outcome_attribution';self.root.mkdir(parents=True,exist_ok=True)
 def path_for(self,attribution_uuid): return self.root/f'report_{attribution_uuid}.json'
 def save(self,report):
  data=json.dumps(report.to_dict(),sort_keys=True,separators=(',',':'),allow_nan=False).encode(); path=self.path_for(report.attribution_uuid)
  if path.exists():
   if path.read_bytes()==data:return path
   raise FileExistsError('APPEND_ONLY_REPORT_COLLISION')
  fd,tmp=tempfile.mkstemp(prefix='.report_',suffix='.tmp',dir=self.root)
  try:
   with os.fdopen(fd,'wb') as f:f.write(data);f.flush();os.fsync(f.fileno())
   try: os.link(tmp,path)
   except FileExistsError:
    if path.read_bytes()!=data:raise FileExistsError('APPEND_ONLY_REPORT_COLLISION')
  finally:
   if os.path.exists(tmp):os.unlink(tmp)
  return path
 def load(self,attribution_uuid):
  """Load one exact canonical report and fail closed on bytes or identity corruption."""
  try: normalized_uuid=str(UUID(attribution_uuid))
  except (ValueError,TypeError,AttributeError) as exc:raise ValueError('INVALID_ATTRIBUTION_UUID') from exc
  path=self.path_for(normalized_uuid)
  if not path.is_file():raise FileNotFoundError('OUTCOME_ATTRIBUTION_REPORT_MISSING')
  try:
   data=path.read_bytes(); value=json.loads(data)
   canonical=json.dumps(value,sort_keys=True,separators=(',',':'),allow_nan=False).encode()
   if data!=canonical or value.get('attribution_uuid')!=normalized_uuid:raise ValueError('REPORT_INTEGRITY_MISMATCH')
   report=KnowledgeOutcomeAttributionReport(
    attribution_uuid=value['attribution_uuid'],attribution_version=value['attribution_version'],
    created_at=value['created_at'],source_digest=value['source_digest'],replay_digest=value['replay_digest'],
    knowledge_versions=tuple(tuple(x) for x in value['knowledge_versions']),
    summary=AnalyticsSummary(**value['summary']),
    feature_contributions=tuple(FeatureContribution(**x) for x in value['feature_contributions']),
    failure_patterns=tuple(FailurePattern(**{**x,'conditions':tuple(x['conditions'])}) for x in value['failure_patterns']),
    success_patterns=tuple(SuccessPattern(**{**x,'conditions':tuple(x['conditions'])}) for x in value['success_patterns']),
    performance_profiles=tuple(KnowledgePerformanceProfile(**x) for x in value['performance_profiles']),
    market_regimes=tuple(MarketRegimeProfile(**x) for x in value['market_regimes']),
    indicator_contributions=tuple(IndicatorContribution(**x) for x in value['indicator_contributions']),
    risk_contributions=tuple(RiskContribution(**x) for x in value['risk_contributions']),
    confidence=tuple(KnowledgeConfidence(**x) for x in value['confidence']),
    context_attribution=value['context_attribution'],advisory_only=value['advisory_only'])
   if json.dumps(report.to_dict(),sort_keys=True,separators=(',',':'),allow_nan=False).encode()!=data:raise ValueError('REPORT_INTEGRITY_MISMATCH')
   return report
  except (OSError,json.JSONDecodeError,KeyError,TypeError,ValueError) as exc:
   raise ValueError('OUTCOME_ATTRIBUTION_REPOSITORY_CORRUPT') from exc
