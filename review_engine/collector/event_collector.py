"""Observation-only event normalization. Snapshot construction is intentionally absent."""
from collections import deque
from datetime import datetime, timezone
import hashlib, json, uuid
from typing import Any, Callable, Mapping
from .event_types import EventType
from .trade_source import TradeSource

class EventQueue:
    def __init__(self): self._items = deque()
    def publish(self, event: Mapping[str, Any]) -> None: self._items.append(dict(event))
    def drain(self):
        while self._items: yield self._items.popleft()

def _utc(value: Any) -> str:
    if value is None or value == "": return datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")
    text = str(value).replace("Z", "+00:00")
    point = datetime.fromisoformat(text)
    if point.tzinfo is None: point = point.replace(tzinfo=timezone.utc)
    return point.astimezone(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")

class EventCollector:
    """Converts records from a TradeSource into normalized events and publishes them.

    This class does not import builders/repositories and never creates snapshots.
    """
    def __init__(self, source: TradeSource, event_sink: EventQueue | Callable[[Mapping[str, Any]], None], *, source_module="trade_export", source_version="unknown"):
        self.source, self.event_sink = source, event_sink
        self.source_module, self.source_version = source_module, source_version
    def collect(self) -> list[dict[str, Any]]:
        events = []
        for record in self.source.read_records():
            event = self.normalize(record)
            self._emit(event); events.append(event)
        return events
    def normalize(self, record: Mapping[str, Any]) -> dict[str, Any]:
        payload = dict(record.get("payload", record))
        encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str).encode()
        get = record.get
        return {"schema_version":"1.0.0", "event_id":str(get("event_id") or uuid.uuid4()),
          "event_type":str(get("event_type") or EventType.TRADE_CLOSED.value), "occurred_at_utc":_utc(get("occurred_at_utc", get("closed_at_utc"))),
          "observed_at_utc":_utc(get("observed_at_utc")), "source_module":str(get("source_module", self.source_module)), "source_version":str(get("source_version", self.source_version)),
          "symbol":str(get("symbol", "")), "account_id_hash":get("account_id_hash"), "trade_id":None if get("trade_id") is None else str(get("trade_id")),
          "position_id":None if get("position_id") is None else str(get("position_id")), "series_id":get("series_id"), "candidate_id":get("candidate_id"), "sequence_id":get("sequence_id"), "correlation_id":get("correlation_id"), "payload":payload,
          "integrity":{"payload_sha256":hashlib.sha256(encoded).hexdigest()}}
    def _emit(self, event):
        if hasattr(self.event_sink, "publish"): self.event_sink.publish(event)
        else: self.event_sink(event)
