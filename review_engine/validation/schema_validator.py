from datetime import datetime
from review_engine.collector.event_types import ALLOWED_EVENT_TYPES, payload_hash
class SchemaValidationError(ValueError): pass
def _utc(value):
    try:
        if not isinstance(value,str) or not value.endswith("Z"): raise ValueError
        datetime.fromisoformat(value.replace("Z","+00:00"))
    except ValueError: raise SchemaValidationError("timestamp must be UTC ISO-8601 ending in Z")
def _need(data, *names):
    missing=[n for n in names if n not in data]
    if missing: raise SchemaValidationError("missing fields: "+", ".join(missing))
def validate_event(event):
    _need(event,"schema_version","event_id","event_type","occurred_at_utc","observed_at_utc","payload","integrity")
    if event["event_type"] not in ALLOWED_EVENT_TYPES: raise SchemaValidationError("unsupported event_type")
    _utc(event["occurred_at_utc"]); _utc(event["observed_at_utc"])
    if event["integrity"].get("payload_sha256") != payload_hash(event["payload"]): raise SchemaValidationError("payload hash mismatch")
    return event
def validate_snapshot(snapshot):
    _need(snapshot,"schema_version","snapshot_id","created_at_utc","trade_identity","timeline","outcome","data_quality","provenance")
    _utc(snapshot["created_at_utc"])
    identity=snapshot["trade_identity"]
    _need(identity,"trade_id","symbol","side","volume")
    if not identity["trade_id"] or identity["side"] not in {"BUY","SELL"}: raise SchemaValidationError("trade identity is invalid")
    for k in ("filled_at_utc","closed_at_utc"):
        if snapshot["timeline"].get(k) is not None: _utc(snapshot["timeline"][k])
    if len(snapshot["provenance"].get("snapshot_sha256", "")) != 64: raise SchemaValidationError("snapshot hash missing")
    return snapshot
def validate_daily_review(report):
    _need(report,"schema_version","date_utc","generated_at_utc","scope","performance","provenance")
    _utc(report["generated_at_utc"])
    if len(report["provenance"].get("report_sha256", "")) != 64: raise SchemaValidationError("report hash missing")
    return report
