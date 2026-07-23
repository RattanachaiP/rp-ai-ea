"""Offline read-only analytics over the injected KnowledgeReader boundary."""
from __future__ import annotations
import hashlib, json
from datetime import datetime, timezone
from .models import AnalyticsConfig, AnalyticsReport, ANALYTICS_VERSION
from .aggregation import performance, finite
from .coverage import coverage
from .stability import stability
from .conflict import detect_conflicts
DOMAINS=("inventory","coverage","performance","stability","conflicts","data_quality")
class KnowledgeAnalyticsEngine:
 def __init__(self, knowledge_reader, analytics_repository=None, config=None):
  if knowledge_reader is None or not hasattr(knowledge_reader,"query"): raise TypeError("KNOWLEDGE_READER_REQUIRED")
  self._reader=knowledge_reader; self._repository=analytics_repository; self.config=config or AnalyticsConfig()
 def _snapshot(self):
  # One bounded reader query captures a stable, detached logical snapshot.
  return tuple(self._reader.query(status=None))
 def analyze_inventory(self, records=None):
  records=tuple(records if records is not None else self._snapshot()); statuses={s:0 for s in ("ACTIVE","DEPRECATED","SUPERSEDED","ARCHIVED")}
  for r in records: statuses[r.knowledge_status]=statuses.get(r.knowledge_status,0)+1
  dist=lambda attr:{str(k):sum(1 for r in records if str(getattr(r,attr))==str(k)) for k in sorted({getattr(r,attr) for r in records},key=str)}
  return {"total_knowledge_records":len(records),"active_knowledge_count":statuses["ACTIVE"],"deprecated_knowledge_count":statuses["DEPRECATED"],"superseded_knowledge_count":statuses["SUPERSEDED"],"archived_knowledge_count":statuses["ARCHIVED"],"unique_pattern_count":len({r.pattern_uuid for r in records}),"unique_symbol_count":len({x for r in records for x in r.applicable_symbols}),"unique_session_count":len({x for r in records for x in r.applicable_sessions}),"unique_market_state_count":len({x for r in records for x in r.applicable_market_states}),"schema_version_distribution":dist("schema_version"),"knowledge_version_distribution":dist("knowledge_version")}
 def analyze_coverage(self, records=None): return coverage(tuple(records if records is not None else self._snapshot()),self.config)
 def analyze_performance(self, records=None): return performance(tuple(records if records is not None else self._snapshot()))
 def analyze_stability(self, records=None): return stability(tuple(records if records is not None else self._snapshot()),self.config)
 def detect_conflicts(self, records=None): return detect_conflicts(tuple(records if records is not None else self._snapshot()),self.config)
 def analyze_data_quality(self, records=None):
  records=tuple(records if records is not None else self._snapshot()); issues=[]; identities=set()
  for r in records:
   if r.schema_version not in self.config.supported_schema_versions: issues.append({"knowledge_uuid":r.knowledge_uuid,"issue":"UNSUPPORTED_SCHEMA_VERSION"})
   identity=(r.pattern_uuid,r.knowledge_version)
   if identity in identities: issues.append({"knowledge_uuid":r.knowledge_uuid,"issue":"DUPLICATE_ANALYTICAL_IDENTITY"})
   identities.add(identity)
   for f in ("sample_count","verified_win_rate","average_rr"):
    if finite(getattr(r,f,None)) is None: issues.append({"knowledge_uuid":r.knowledge_uuid,"issue":"NON_FINITE_OR_INVALID_VALUE","field":f})
   if not r.applicable_symbols or not r.applicable_sessions or not r.applicable_market_states: issues.append({"knowledge_uuid":r.knowledge_uuid,"issue":"MISSING_OPTIONAL_CONDITIONS"})
  return {"issue_count":len(issues),"issues":sorted(issues,key=lambda x:(x["knowledge_uuid"],x["issue"],x.get("field","")))}
 def analyze(self):
  records=self._snapshot(); canonical=[r.to_dict() for r in records]; digest=hashlib.sha256(json.dumps(canonical,sort_keys=True,separators=(",",":"),allow_nan=False).encode()).hexdigest()
  latest=max((r.created_timestamp for r in records),default=None); snapshot={"record_count":len(records),"knowledge_ids":[r.knowledge_uuid for r in records],"latest_record_timestamp":latest,"source_digest":digest,"schema_versions":sorted({r.schema_version for r in records})}
  values={}; failed=[]
  for name, fn in (("inventory",self.analyze_inventory),("coverage",self.analyze_coverage),("performance",self.analyze_performance),("stability",self.analyze_stability),("conflicts",self.detect_conflicts),("data_quality",self.analyze_data_quality)):
   try: values[name]=fn(records)
   except Exception: failed.append(name); values[name]=[] if name=="conflicts" else {}
  status="EMPTY_INPUT" if not records else "PARTIAL" if failed else "COMPLETE"
  report=AnalyticsReport(analytics_uuid=digest[:32],analytics_version=ANALYTICS_VERSION,created_at=datetime.now(timezone.utc).isoformat().replace("+00:00","Z"),source_baseline="cb751c0",configuration_version=self.config.version,knowledge_snapshot=snapshot,inventory=values["inventory"],coverage=values["coverage"],performance=values["performance"],stability=values["stability"],conflicts=tuple(values["conflicts"]),data_quality=values["data_quality"],status=status,completed_domains=tuple(n for n in DOMAINS if n not in failed),failed_domains=tuple(failed))
  if self._repository and self.config.persistence_enabled: self._repository.save(report)
  return report
