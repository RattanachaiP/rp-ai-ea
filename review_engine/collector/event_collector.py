"""Append-only event persistence; failures remain isolated from trading."""
from __future__ import annotations
from datetime import datetime, timezone
import json, logging, os
from pathlib import Path
from typing import Any
from ..config import ReviewEngineConfig
from .event_types import EventValidationError, canonical_json, validate_event

class EventCollector:
    def __init__(self, config: ReviewEngineConfig, clock=lambda: datetime.now(timezone.utc)):
        self.config, self.clock = config, clock
        self.logger = logging.getLogger("review_engine.collector")
    def record(self, event: dict[str, Any]) -> bool:
        """Return False for observer errors; never raise into a trading caller."""
        if not self.config.enabled: return False
        try:
            normalized = validate_event(event)
            instant = datetime.fromisoformat(normalized["occurred_at_utc"].replace("Z", "+00:00"))
            target = self._dated_path("events", instant, "events.jsonl")
            target.parent.mkdir(parents=True, exist_ok=True)
            with target.open("a", encoding="utf-8") as handle:
                handle.write(canonical_json(normalized) + "\n"); handle.flush(); os.fsync(handle.fileno())
            return True
        except Exception as error:
            self.logger.error("RAIP_EVENT_REJECTED reason=%s", type(error).__name__)
            if self.config.quarantine_invalid_records: self._quarantine(event, error)
            return False
    def _dated_path(self, category: str, instant: datetime, filename: str) -> Path:
        return self.config.review_data_root / category / instant.strftime("%Y/%m/%d") / filename
    def _quarantine(self, event: Any, error: Exception) -> None:
        try:
            target = self._dated_path("rejected", self.clock().astimezone(timezone.utc), f"event_{__import__("time").time_ns()}.json")
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(canonical_json({"reason": str(error), "record": event}), encoding="utf-8")
        except OSError: self.logger.error("RAIP_QUARANTINE_WRITE_FAILED")
