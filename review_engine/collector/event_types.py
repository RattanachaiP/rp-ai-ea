import hashlib
import json
import uuid
from datetime import datetime, timezone

ALLOWED_EVENT_TYPES = frozenset({"DECISION_OBSERVED", "ENTRY_REQUEST_OBSERVED", "ORDER_FILL_OBSERVED", "POSITION_UPDATE_OBSERVED", "EXIT_REQUEST_OBSERVED", "TRADE_CLOSED", "SNAPSHOT_CREATED", "SNAPSHOT_REJECTED", "DAILY_REVIEW_CREATED"})

def utc_now(): return datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")
def payload_hash(payload): return hashlib.sha256(json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
def make_event(event_type, payload, *, occurred_at_utc=None, source_module="unknown", source_version="unknown", **identity):
    if event_type not in ALLOWED_EVENT_TYPES: raise ValueError("unsupported RAIP event type")
    return {"schema_version":"1.0.0", "event_id":str(uuid.uuid4()), "event_type":event_type, "occurred_at_utc":occurred_at_utc or utc_now(), "observed_at_utc":utc_now(), "source_module":source_module, "source_version":source_version, "symbol":identity.get("symbol"), "account_id_hash":identity.get("account_id_hash"), "trade_id":identity.get("trade_id"), "position_id":identity.get("position_id"), "series_id":identity.get("series_id"), "candidate_id":identity.get("candidate_id"), "sequence_id":identity.get("sequence_id"), "correlation_id":identity.get("correlation_id"), "payload":payload, "integrity":{"payload_sha256":payload_hash(payload)}}
