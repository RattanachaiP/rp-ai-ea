"""Fail-closed-for-RAIP collector: invalid observations never leave review storage."""
from __future__ import annotations
import hashlib, json, logging, uuid
from datetime import datetime, timezone
from typing import Any, Mapping
from review_engine.snapshots.snapshot_repository import SnapshotRepository
from review_engine.snapshots.trade_snapshot_builder import TradeSnapshotBuilder
from review_engine.validation.schema_validator import validate_event

class EventCollector:
    def __init__(self, repository: SnapshotRepository, logger: logging.Logger | None = None): self.repository, self.logger = repository, logger or logging.getLogger("raip.collector")
    @staticmethod
    def _utc(value: str | None = None) -> str:
        if value:
            return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")
        return datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")
    def normalize(self, source: Mapping[str, Any]) -> dict[str, Any]:
        payload = source.get("payload", {})
        return {"schema_version":"1.0.0", "event_id":source.get("event_id", str(uuid.uuid5(uuid.NAMESPACE_URL, json.dumps(source, sort_keys=True, separators=(",", ":"))))), "event_type":source.get("event_type"), "occurred_at_utc":self._utc(source.get("occurred_at_utc")), "observed_at_utc":self._utc(source.get("observed_at_utc")), "source_module":source.get("source_module", "unknown"), "source_version":source.get("source_version", "unknown"), "symbol":source.get("symbol"), "account_id_hash":source.get("account_id_hash"), "trade_id":source.get("trade_id"), "position_id":source.get("position_id"), "series_id":source.get("series_id"), "candidate_id":source.get("candidate_id"), "sequence_id":source.get("sequence_id"), "correlation_id":source.get("correlation_id"), "payload":payload, "integrity":{"payload_sha256":hashlib.sha256(json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()).hexdigest()}}
    def collect(self, source: Mapping[str, Any] | str) -> dict[str, Any] | None:
        try:
            raw = json.loads(source) if isinstance(source, str) else source
            event = self.normalize(raw); errors = validate_event(event)
            if errors: self.repository.quarantine(raw, errors, event["observed_at_utc"]); return None
            self.repository.append_event(event)
            if event["event_type"] == "TRADE_CLOSED":
                snapshot = TradeSnapshotBuilder().build(self.repository.load_events_for_trade(event))
                self.repository.store_snapshot(snapshot)
            self.repository.save_collector_state({"last_event_id": event["event_id"], "last_observed_at_utc": event["observed_at_utc"]})
            return event
        except Exception as error:  # isolation: callers never receive an RAIP storage failure
            self.logger.exception("RAIP observation rejected: %s", error)
            try: self.repository.quarantine(source, [f"collector_error:{type(error).__name__}"])
            except Exception: self.logger.exception("RAIP quarantine failed")
            return None
