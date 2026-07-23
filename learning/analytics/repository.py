from __future__ import annotations
import json
from .models import AnalyticsReport
from .storage import AnalyticsStorage
class AnalyticsRepository:
    def __init__(self, root="learning_data"): self.storage = AnalyticsStorage(root)
    def save(self, report): return self.storage.write(report)
    def load(self, analytics_uuid): return AnalyticsReport.from_dict(json.loads(self.storage.path_for(analytics_uuid).read_text(encoding="utf-8")))
    def history(self): return tuple(self.load(path.name[7:-5]) for path in sorted(self.storage.root.glob("report_*.json")))
    def latest(self):
        """Return the latest observed source snapshot; UUID is a stable tie-breaker.

        Canonical artifacts intentionally have no wall-clock creation timestamp.
        """
        values = self.history()
        return max(values, key=lambda item: ((item.knowledge_snapshot["latest_record_timestamp"] or ""), item.analytics_uuid)) if values else None
    def query(self, status=None, analytics_version=None, source_digest=None):
        return tuple(report for report in self.history() if (status is None or report.status == status) and (analytics_version is None or report.analytics_version == analytics_version) and (source_digest is None or report.knowledge_snapshot["source_digest"] == source_digest))
