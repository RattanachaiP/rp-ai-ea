"""Offline read-only analytics over an injected KnowledgeReader snapshot."""
from __future__ import annotations
import hashlib
import json
from .models import ANALYTICS_VERSION, AnalyticsConfig, AnalyticsReport
from .aggregation import finite, performance
from .conflict import detect_conflicts
from .coverage import coverage
from .stability import stability

DOMAINS = ("inventory", "coverage", "performance", "stability", "conflicts", "data_quality")
def _digest(value): return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")).hexdigest()

class KnowledgeAnalyticsEngine:
    def __init__(self, knowledge_reader, analytics_repository=None, config=None, analytics_version=ANALYTICS_VERSION):
        if knowledge_reader is None or not hasattr(knowledge_reader, "query"):
            raise TypeError("KNOWLEDGE_READER_REQUIRED")
        self._reader, self._repository = knowledge_reader, analytics_repository
        self.config, self.analytics_version = config or AnalyticsConfig(), analytics_version

    def _snapshot(self):
        # Reader ordering is not an analytics contract: normalize once and use
        # this exact immutable ordering for every domain and source identity.
        return tuple(sorted(self._reader.query(status=None), key=lambda record: (
            record.pattern_uuid, record.knowledge_version,
            record.created_timestamp, record.knowledge_uuid,
        )))

    def analyze_inventory(self, records=None):
        records = tuple(records if records is not None else self._snapshot()); statuses = {name: 0 for name in ("ACTIVE", "DEPRECATED", "SUPERSEDED", "ARCHIVED")}
        for record in records: statuses[record.knowledge_status] = statuses.get(record.knowledge_status, 0) + 1
        def distribution(attribute):
            return {str(key): sum(1 for record in records if str(getattr(record, attribute)) == str(key)) for key in sorted({getattr(record, attribute) for record in records}, key=str)}
        return {"total_knowledge_records": len(records), "active_knowledge_count": statuses["ACTIVE"], "deprecated_knowledge_count": statuses["DEPRECATED"], "superseded_knowledge_count": statuses["SUPERSEDED"], "archived_knowledge_count": statuses["ARCHIVED"], "unique_pattern_count": len({record.pattern_uuid for record in records}), "unique_symbol_count": len({value for record in records for value in record.applicable_symbols}), "unique_session_count": len({value for record in records for value in record.applicable_sessions}), "unique_market_state_count": len({value for record in records for value in record.applicable_market_states}), "schema_version_distribution": distribution("schema_version"), "knowledge_version_distribution": distribution("knowledge_version")}

    def analyze_coverage(self, records=None): return coverage(tuple(records if records is not None else self._snapshot()), self.config)
    def analyze_performance(self, records=None): return performance(tuple(records if records is not None else self._snapshot()))
    def analyze_stability(self, records=None): return stability(tuple(records if records is not None else self._snapshot()), self.config)
    def detect_conflicts(self, records=None): return detect_conflicts(tuple(records if records is not None else self._snapshot()), self.config)

    def analyze_data_quality(self, records=None):
        records, issues, identities = tuple(records if records is not None else self._snapshot()), [], set()
        for record in records:
            if record.schema_version not in self.config.supported_schema_versions: issues.append({"knowledge_uuid": record.knowledge_uuid, "issue": "UNSUPPORTED_SCHEMA_VERSION"})
            identity = (record.pattern_uuid, record.knowledge_version)
            if identity in identities: issues.append({"knowledge_uuid": record.knowledge_uuid, "issue": "DUPLICATE_ANALYTICAL_IDENTITY"})
            identities.add(identity)
            for field in ("sample_count", "verified_win_rate", "average_rr"):
                if finite(getattr(record, field, None)) is None: issues.append({"knowledge_uuid": record.knowledge_uuid, "issue": "NON_FINITE_OR_INVALID_VALUE", "field": field})
            if not record.applicable_symbols or not record.applicable_sessions or not record.applicable_market_states: issues.append({"knowledge_uuid": record.knowledge_uuid, "issue": "MISSING_OPTIONAL_CONDITIONS"})
        return {"issue_count": len(issues), "issues": sorted(issues, key=lambda item: (item["knowledge_uuid"], item["issue"], item.get("field", "")))}

    def analyze(self):
        records = self._snapshot(); source_digest = _digest([record.to_dict() for record in records]); config_digest = _digest(self.config.canonical_dict())
        latest = max((record.created_timestamp for record in records), default=None)
        snapshot = {"record_count": len(records), "knowledge_ids": [record.knowledge_uuid for record in records], "latest_record_timestamp": latest, "source_digest": source_digest, "schema_versions": sorted({record.schema_version for record in records})}
        identity = _digest({"source_digest": source_digest, "analytics_version": self.analytics_version, "configuration_digest": config_digest})
        values, diagnostics = {}, []
        for name, function in (("inventory", self.analyze_inventory), ("coverage", self.analyze_coverage), ("performance", self.analyze_performance), ("stability", self.analyze_stability), ("conflicts", self.detect_conflicts), ("data_quality", self.analyze_data_quality)):
            try: values[name] = function(records)
            except Exception as error:
                values[name] = [] if name == "conflicts" else {}
                diagnostics.append({"domain": name, "error_code": "ANALYTICS_DOMAIN_FAILED", "exception_type": type(error).__name__})
        status = "EMPTY_INPUT" if not records else "PARTIAL" if diagnostics else "COMPLETE"
        report = AnalyticsReport(analytics_uuid=identity[:32], analytics_version=self.analytics_version, created_at=None, source_baseline="cb751c0", configuration_version=self.config.version, configuration_digest=config_digest, knowledge_snapshot=snapshot, inventory=values["inventory"], coverage=values["coverage"], performance=values["performance"], stability=values["stability"], conflicts=tuple(values["conflicts"]), data_quality=values["data_quality"], status=status, completed_domains=tuple(name for name in DOMAINS if name not in {item["domain"] for item in diagnostics}), failed_domains=tuple(item["domain"] for item in diagnostics), failure_diagnostics=tuple(diagnostics))
        if self._repository and self.config.persistence_enabled: self._repository.save(report)
        return report
