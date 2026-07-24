"""Schema validation for immutable canonical analytics reports."""
from __future__ import annotations
import json
import math
import re
from collections.abc import Mapping, Sequence
from .models import AnalyticsReport, STATUSES
DOMAIN_NAMES = frozenset(("inventory", "coverage", "performance", "stability", "conflicts", "data_quality"))
_DIGEST = re.compile(r"^[0-9a-f]{64}$")
_UUID = re.compile(r"^[0-9a-f]{32}$")
def _json_safe(value):
    if isinstance(value, float) and not math.isfinite(value): return False
    if isinstance(value, Mapping): return all(isinstance(k, str) and _json_safe(v) for k,v in value.items())
    if isinstance(value, (tuple,list)): return all(_json_safe(v) for v in value)
    return value is None or isinstance(value,(str,int,float,bool))
def validate(report):
    if not isinstance(report, AnalyticsReport): raise TypeError("INVALID_ANALYTICS_REPORT")
    if not _UUID.fullmatch(report.analytics_uuid): raise ValueError("INVALID_ANALYTICS_UUID")
    if not report.analytics_version or not report.configuration_version or not report.source_baseline: raise ValueError("EMPTY_REPORT_VERSION")
    if not _DIGEST.fullmatch(report.configuration_digest) or not _DIGEST.fullmatch(report.knowledge_snapshot.get("source_digest", "")): raise ValueError("INVALID_DIGEST")
    completed, failed = tuple(report.completed_domains), tuple(report.failed_domains)
    if len(set(completed)) != len(completed) or len(set(failed)) != len(failed) or not set(completed + failed) <= DOMAIN_NAMES or set(completed)&set(failed): raise ValueError("INVALID_DOMAIN_STATUS")
    diagnostics = tuple(report.failure_diagnostics)
    if {item.get("domain") for item in diagnostics} != set(failed) or any(set(item) != {"domain","error_code","exception_type"} for item in diagnostics): raise ValueError("INVALID_FAILURE_DIAGNOSTICS")
    snapshot=report.knowledge_snapshot
    if snapshot.get("record_count") != len(snapshot.get("knowledge_ids", ())): raise ValueError("INVALID_SNAPSHOT_COUNT")
    if report.status == "EMPTY_INPUT" and snapshot["record_count"] != 0: raise ValueError("INVALID_EMPTY_INPUT")
    if report.status == "PARTIAL" and not failed: raise ValueError("INVALID_PARTIAL")
    if report.status == "COMPLETE" and failed: raise ValueError("INVALID_COMPLETE")
    if not isinstance(report.conflicts, tuple) or len(report.conflicts) > 100000 or any(not isinstance(item, Mapping) or not {"severity","condition","knowledge_ids"} <= set(item) for item in report.conflicts): raise ValueError("INVALID_CONFLICTS")
    payload=report.to_dict()
    if not _json_safe(payload): raise ValueError("NONFINITE_REPORT_VALUE")
    json.dumps(payload, sort_keys=True, allow_nan=False)
    return report
