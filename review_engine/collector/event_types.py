"""Validation and normalization for RAIP-owned event envelopes."""
from __future__ import annotations
from datetime import datetime, timezone
from hashlib import sha256
from typing import Any
from uuid import UUID

ALLOWED_EVENT_TYPES = frozenset({"DECISION_OBSERVED", "ENTRY_REQUEST_OBSERVED", "ORDER_FILL_OBSERVED", "POSITION_UPDATE_OBSERVED", "EXIT_REQUEST_OBSERVED", "TRADE_CLOSED", "SNAPSHOT_CREATED", "SNAPSHOT_REJECTED", "DAILY_REVIEW_CREATED"})
class EventValidationError(ValueError): pass

def utc_timestamp(value: Any) -> str:
    if not isinstance(value, str): raise EventValidationError("TIMESTAMP_MUST_BE_STRING")
    try: parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as error: raise EventValidationError("TIMESTAMP_INVALID") from error
    if parsed.tzinfo is None: raise EventValidationError("TIMESTAMP_MUST_BE_UTC")
    return parsed.astimezone(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")

def canonical_json(value: Any) -> str:
    import json
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False)

def validate_event(event: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(event, dict): raise EventValidationError("EVENT_MUST_BE_OBJECT")
    normalized = dict(event)
    if normalized.get("schema_version") != "1.0.0": raise EventValidationError("UNSUPPORTED_SCHEMA_VERSION")
    try: UUID(str(normalized["event_id"]))
    except (KeyError, ValueError, TypeError) as error: raise EventValidationError("EVENT_ID_MUST_BE_UUID") from error
    if normalized.get("event_type") not in ALLOWED_EVENT_TYPES: raise EventValidationError("EVENT_TYPE_NOT_ALLOWED")
    for field in ("occurred_at_utc", "observed_at_utc"):
        normalized[field] = utc_timestamp(normalized.get(field))
    for field in ("source_module", "source_version", "symbol"):
        if not isinstance(normalized.get(field), str) or not normalized[field]: raise EventValidationError(f"{field.upper()}_REQUIRED")
    if not isinstance(normalized.get("payload"), dict): raise EventValidationError("PAYLOAD_MUST_BE_OBJECT")
    for field in ("account_id_hash", "trade_id", "position_id", "series_id", "candidate_id", "sequence_id", "correlation_id"):
        if field not in normalized: normalized[field] = None
        if normalized[field] is not None and not isinstance(normalized[field], str): raise EventValidationError(f"{field.upper()}_MUST_BE_STRING_OR_NULL")
    digest = sha256(canonical_json(normalized["payload"]).encode()).hexdigest()
    if normalized.get("integrity", {}).get("payload_sha256") != digest: raise EventValidationError("PAYLOAD_SHA256_MISMATCH")
    return normalized
