from __future__ import annotations
import json
from .storage import AnalyticsStorage
from .models import AnalyticsReport
class AnalyticsRepository:
 def __init__(self, root="learning_data"): self.storage=AnalyticsStorage(root)
 def save(self, report): return self.storage.write(report)
 def load(self, analytics_uuid): return AnalyticsReport.from_dict(json.loads(self.storage.path_for(analytics_uuid).read_text()))
 def history(self): return tuple(self.load(p.name[7:-5]) for p in sorted(self.storage.root.glob("report_*.json")))
 def latest(self):
  values=self.history(); return values[-1] if values else None
 def query(self, status=None, analytics_version=None, source_digest=None): return tuple(r for r in self.history() if (status is None or r.status==status) and (analytics_version is None or r.analytics_version==analytics_version) and (source_digest is None or r.knowledge_snapshot["source_digest"]==source_digest))
