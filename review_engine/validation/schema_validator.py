import hashlib, json
from datetime import datetime, timezone
from pathlib import Path
from ..collector.event_types import ALLOWED_EVENT_TYPES

class SchemaValidationError(ValueError): pass

def canonical_sha256(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()).hexdigest()
def _utc(value):
    if not isinstance(value, str) or not value.endswith("Z"): raise SchemaValidationError("timestamp must be UTC ISO-8601 ending in Z")
    try: datetime.fromisoformat(value[:-1] + "+00:00")
    except ValueError as e: raise SchemaValidationError("invalid UTC timestamp") from e
def _required(record, keys):
    missing = [key for key in keys if key not in record]
    if missing: raise SchemaValidationError("missing required fields: " + ", ".join(missing))
def validate_event(event):
    _required(event, ("schema_version", "event_id", "event_type", "occurred_at_utc", "observed_at_utc", "source_module", "source_version", "symbol", "account_id_hash", "trade_id", "position_id", "series_id", "candidate_id", "sequence_id", "correlation_id", "payload", "integrity"))
    if event["schema_version"] != "1.0.0" or event["event_type"] not in ALLOWED_EVENT_TYPES: raise SchemaValidationError("unsupported event version or type")
    _utc(event["occurred_at_utc"]); _utc(event["observed_at_utc"])
    if not isinstance(event["payload"], dict) or not isinstance(event["integrity"], dict): raise SchemaValidationError("payload and integrity must be objects")
    supplied = event["integrity"].get("payload_sha256")
    if supplied != canonical_sha256(event["payload"]): raise SchemaValidationError("payload_sha256 mismatch")
    return event
def validate_snapshot(snapshot):
    _required(snapshot, ("schema_version", "snapshot_id", "created_at_utc", "trade_identity", "timeline", "decision_context", "market_context", "execution_context", "outcome", "data_quality", "provenance"))
    identity, timeline = snapshot["trade_identity"], snapshot["timeline"]
    _required(identity, ("trade_id", "symbol", "side", "volume")); _required(timeline, ("closed_at_utc", "duration_seconds"))
    if snapshot["schema_version"] != "1.0.0" or identity["side"] not in ("BUY", "SELL"): raise SchemaValidationError("invalid snapshot version or side")
    _utc(snapshot["created_at_utc"]); _utc(timeline["closed_at_utc"])
    for key in ("decision_at_utc", "entry_requested_at_utc", "filled_at_utc"):
        if timeline.get(key) is not None: _utc(timeline[key])
    return snapshot
def validate_daily_review(report):
    _required(report, ("schema_version", "date_utc", "generated_at_utc", "scope", "performance", "direction", "data_quality", "provenance"))
    if report["schema_version"] != "1.0.0": raise SchemaValidationError("unsupported report version")
    _utc(report["generated_at_utc"]); datetime.strptime(report["date_utc"], "%Y-%m-%d")
    return report
