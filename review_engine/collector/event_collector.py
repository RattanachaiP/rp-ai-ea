import json, logging, os, uuid
from datetime import datetime, timezone
from pathlib import Path
from ..validation.schema_validator import SchemaValidationError, canonical_sha256, validate_event

class EventCollector:
    """Best-effort observer. Exceptions are contained and never reach a trading caller."""
    def __init__(self, root, quarantine_invalid_records=True, logger=None): self.root, self.quarantine_invalid_records, self.log = Path(root), quarantine_invalid_records, logger or logging.getLogger("raip.collector")
    @staticmethod
    def utc_now(): return datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")
    def normalize(self, event):
        event = dict(event); event.setdefault("schema_version", "1.0.0"); event.setdefault("event_id", str(uuid.uuid4())); event.setdefault("observed_at_utc", self.utc_now()); event.setdefault("source_version", "unknown")
        for key in ("account_id_hash", "trade_id", "position_id", "series_id", "candidate_id", "sequence_id", "correlation_id"): event.setdefault(key, None)
        event.setdefault("payload", {}); event["integrity"] = {"payload_sha256": canonical_sha256(event["payload"])}
        return event
    def collect(self, event):
        try:
            event = self.normalize(event); validate_event(event); day = datetime.fromisoformat(event["occurred_at_utc"].replace("Z", "+00:00"))
            self._append_atomic(self.root / "events" / day.strftime("%Y/%m/%d") / "events.jsonl", event)
            return {"accepted": True, "event": event}
        except Exception as exc:
            self.log.exception("RAIP event observation failed")
            return self._reject(event, exc)
    def collect_json(self, raw):
        try: return self.collect(json.loads(raw))
        except Exception as exc: return self._reject(raw, exc)
    def _append_atomic(self, path, record):
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "a", encoding="utf-8") as handle:
            handle.write(json.dumps(record, sort_keys=True, separators=(",", ":")) + "\n"); handle.flush(); os.fsync(handle.fileno())
    def _reject(self, raw, exc):
        if self.quarantine_invalid_records:
            path = self.root / "rejected" / datetime.now(timezone.utc).strftime("%Y/%m/%d") / (str(uuid.uuid4()) + ".json")
            path.parent.mkdir(parents=True, exist_ok=True); path.write_text(json.dumps({"reason": type(exc).__name__, "message": str(exc), "record": raw}, default=str), encoding="utf-8")
        return {"accepted": False, "reason": str(exc)}

    def observe_closed_trade(self, event, builder, repository):
        """Collect and snapshot a closed-trade copy; every failure is RAIP-local."""
        result = self.collect(event)
        if not result["accepted"]: return result
        try:
            snapshot = builder.build(result["event"])
            return {**result, "snapshot_result": repository.store(snapshot)}
        except Exception as exc:
            self.log.exception("RAIP snapshot observation failed")
            return {**result, "snapshot_result": self._reject(event, exc)}

    def load_state(self):
        path = self.root / "runtime" / "collector_state.json"
        try: return json.loads(path.read_text(encoding="utf-8"))
        except FileNotFoundError: return {}

    def save_state(self, state):
        """Atomically save observer progress only; callers own source-file cursors."""
        path = self.root / "runtime" / "collector_state.json"; path.parent.mkdir(parents=True, exist_ok=True); temp = path.with_suffix(".json.tmp")
        with open(temp, "w", encoding="utf-8") as handle:
            json.dump(state, handle, sort_keys=True); handle.flush(); os.fsync(handle.fileno())
        os.replace(temp, path)
