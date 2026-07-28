"""Execution-bound operational evidence for the canonical AI Runtime.

This module observes completed runtime work.  It owns no trading decision,
governance threshold, retry policy, or execution behaviour.
"""
from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from threading import Lock
from typing import Mapping


FAILURE_OWNERS = frozenset({
    "BOOT", "CONFIG", "READER", "DECISION_CONTEXT", "ANALYSIS", "RISK",
    "PUBLISHER", "HEALTH",
})


class PublicationOutcome(str, Enum):
    NORMAL = "NORMAL"
    STALE_INPUT_FALLBACK = "STALE_INPUT_FALLBACK"
    LOGIC_ERROR_REJECTION = "LOGIC_ERROR_REJECTION"


class RuntimeObservability:
    """Append stage logs and atomically replace ``runtime_health.json``."""

    def __init__(self, root: Path | str) -> None:
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)
        self._lock = Lock()
        self._last_stage = "BOOT"
        self._health: dict[str, object] = {
            "status": "STARTING", "health_state": "HEALTHY",
            "loop_count": 0, "publication_count": 0,
            "successful_loop_count": 0, "fallback_count": 0,
            "rejected_loop_count": 0, "last_market_state": None,
            "last_decision": None, "loop_latency_ms": 0.0,
            "exception_count": 0, "current_stage": "BOOT",
            "failure_owner": None, "failure_reason": None,
        }
        self._append("runtime.log", "STAGE", "BOOT")
        self._append("runtime_startup.log", "STAGE", "BOOT")
        self._write_health()

    def stage(self, current: str) -> None:
        """Record a stage only when its caller reached the documented boundary."""
        message = f"{self._last_stage} -> {current}"
        self._append("runtime.log", "TRANSITION", message)
        if self._health["status"] == "STARTING":
            self._append("runtime_startup.log", "TRANSITION", message)
        self._last_stage = current
        self._health["current_stage"] = current
        self._write_health()

    def market_state(self, state: Mapping[str, object]) -> None:
        self._health["last_market_state"] = {
            "sequence_id": state.get("sequence_id"),
            "heartbeat_unix": state.get("heartbeat_unix"),
            "source_uuid": state.get("source_uuid"),
        }
        self.stage("MARKET STATE ACCEPTED")

    def publication(self, document: Mapping[str, object], latency_ms: float,
                    outcome: PublicationOutcome) -> None:
        """Record one atomically persisted document and its truthful outcome."""
        if not isinstance(outcome, PublicationOutcome):
            raise ValueError("INVALID_PUBLICATION_OUTCOME")
        with self._lock:
            first_publication = not self._health["publication_count"]
            persisted_stage = "FIRST DECISION PERSISTED" if first_publication else "DECISION PERSISTED"
            self.stage(persisted_stage)
            self._health["publication_count"] = int(self._health["publication_count"]) + 1
            counter = {
                PublicationOutcome.NORMAL: "successful_loop_count",
                PublicationOutcome.STALE_INPUT_FALLBACK: "fallback_count",
                PublicationOutcome.LOGIC_ERROR_REJECTION: "rejected_loop_count",
            }[outcome]
            self._health[counter] = int(self._health[counter]) + 1
            self._health["loop_count"] = (
                int(self._health["successful_loop_count"])
                + int(self._health["fallback_count"])
                + int(self._health["rejected_loop_count"])
            )
            self._health["last_decision"] = {
                "sequence_id": document.get("sequence_id"),
                "heartbeat_unix": document.get("heartbeat_unix"),
                "decision_uuid": document.get("decision_uuid"),
                "outcome": outcome.value,
            }
            self._health.update(status="RUNNING", current_stage="RUNTIME LOOP",
                                loop_latency_ms=round(float(latency_ms), 3))
            if outcome is PublicationOutcome.NORMAL:
                self._health.update(health_state="HEALTHY", failure_owner=None,
                                    failure_reason=None)
            else:
                self._health["health_state"] = "DEGRADED"
            self._append("decision.log", "PUBLISHED", json.dumps(self._health["last_decision"], sort_keys=True))
            first = self.root / "first_decision.json"
            if not first.exists():
                self._atomic_write(first, (json.dumps(dict(document), indent=2, sort_keys=True) + "\n").encode())
            self._last_stage = "RUNTIME LOOP"
            self._append("runtime.log", "TRANSITION", f"{persisted_stage} -> RUNTIME LOOP")
            if first_publication:
                self._append("runtime_startup.log", "TRANSITION", "FIRST DECISION PERSISTED -> RUNTIME LOOP")
            self._write_health()

    def failure(self, owner: str, error: BaseException, *, terminal: bool = False) -> None:
        if owner not in FAILURE_OWNERS:
            raise ValueError("INVALID_FAILURE_OWNER")
        self._health["exception_count"] = int(self._health["exception_count"]) + 1
        self._health.update(status="STOPPED" if terminal else self._health["status"],
                            health_state="STOPPED" if terminal else "DEGRADED",
                            current_stage=owner, failure_owner=owner,
                            failure_reason=str(error) or type(error).__name__)
        self._append("runtime.log", "FAILURE", f"owner={owner} reason={self._health['failure_reason']}")
        self._write_health()

    def snapshot(self) -> dict[str, object]:
        return dict(self._health)

    def _append(self, name: str, event: str, detail: str) -> None:
        timestamp = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
        with (self.root / name).open("a", encoding="utf-8") as stream:
            stream.write(f"{timestamp} {event} {detail}\n")
            stream.flush()

    def _write_health(self) -> None:
        self._health["updated_at"] = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
        payload = (json.dumps(self._health, indent=2, sort_keys=True) + "\n").encode()
        self._atomic_write(self.root / "runtime_health.json", payload)

    @staticmethod
    def _atomic_write(path: Path, payload: bytes) -> None:
        temporary = path.with_name(path.name + ".tmp")
        with temporary.open("wb") as stream:
            stream.write(payload)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
