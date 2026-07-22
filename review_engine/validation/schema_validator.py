"""Small dependency-free validation for files owned by RAIP."""
from __future__ import annotations
import re
from datetime import datetime, timezone
from typing import Any, Mapping

UTC_ISO = re.compile(r"^\d{4}-\d{2}-\d{2}T.*Z$")
EVENT_TYPES = {"DECISION_OBSERVED", "ENTRY_REQUEST_OBSERVED", "ORDER_FILL_OBSERVED", "POSITION_UPDATE_OBSERVED", "EXIT_REQUEST_OBSERVED", "TRADE_CLOSED", "SNAPSHOT_CREATED", "SNAPSHOT_REJECTED", "DAILY_REVIEW_CREATED"}


def utc_timestamp(value: Any) -> bool:
    if not isinstance(value, str) or not UTC_ISO.match(value): return False
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00")).tzinfo == timezone.utc
    except ValueError: return False


def validate_event(event: Mapping[str, Any]) -> list[str]:
    required = ("schema_version", "event_id", "event_type", "occurred_at_utc", "observed_at_utc", "source_module", "source_version", "symbol", "payload", "integrity")
    errors = [f"missing:{key}" for key in required if key not in event]
    if event.get("schema_version") != "1.0.0": errors.append("invalid:schema_version")
    if event.get("event_type") not in EVENT_TYPES: errors.append("invalid:event_type")
    for key in ("occurred_at_utc", "observed_at_utc"):
        if not utc_timestamp(event.get(key)): errors.append(f"invalid:{key}")
    if not isinstance(event.get("payload"), dict): errors.append("invalid:payload")
    if not isinstance(event.get("integrity"), dict) or not isinstance(event.get("integrity", {}).get("payload_sha256"), str): errors.append("invalid:integrity.payload_sha256")
    return errors


def validate_snapshot(snapshot: Mapping[str, Any]) -> list[str]:
    errors = [f"missing:{key}" for key in ("schema_version", "snapshot_id", "created_at_utc", "trade_identity", "timeline", "outcome", "data_quality", "provenance") if key not in snapshot]
    identity = snapshot.get("trade_identity", {})
    if identity.get("side") not in {"BUY", "SELL"}: errors.append("invalid:trade_identity.side")
    if not utc_timestamp(snapshot.get("created_at_utc")): errors.append("invalid:created_at_utc")
    return errors
