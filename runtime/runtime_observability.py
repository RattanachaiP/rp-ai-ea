"""Operational evidence for the canonical continuously running AI Runtime.

This observer owns no decision logic.  It only records stage transitions and
atomically exposes the state of the loop which the governed startup invoked.
"""
from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from threading import Lock
from typing import Mapping


FAILURE_OWNERS = frozenset({"BOOT", "CONFIG", "READER", "ANALYSIS", "RISK", "PUBLISHER", "HEALTH"})


class RuntimeObservability:
    """Append durable logs and atomically replace ``runtime_health.json``."""

    def __init__(self, root: Path | str) -> None:
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)
        self._lock = Lock()
        self._health: dict[str, object] = {
            "status": "STARTING", "loop_count": 0, "last_market_state": None,
            "last_decision": None, "loop_latency_ms": 0.0,
            "exception_count": 0, "current_stage": "BOOT",
            "failure_owner": None, "failure_reason": None,
        }
        self._write_health()

    def transition(self, previous: str, current: str, *, startup: bool = False) -> None:
        message = f"{previous} -> {current}"
        self._append("runtime.log", "TRANSITION", message)
        if startup:
            self._append("runtime_startup.log", "TRANSITION", message)
        self._health["current_stage"] = current
        self._write_health()

    def running(self) -> None:
        self._health.update(status="RUNNING", current_stage="RUNTIME LOOP")
        self._write_health()

    def market_state(self, state: Mapping[str, object]) -> None:
        self._health["last_market_state"] = {
            "sequence_id": state.get("sequence_id"),
            "heartbeat_unix": state.get("heartbeat_unix"),
            "source_uuid": state.get("source_uuid"),
        }
        self._health["current_stage"] = "READER"
        self._write_health()

    def decision(self, document: Mapping[str, object], latency_ms: float) -> None:
        with self._lock:
            self._health["loop_count"] = int(self._health["loop_count"]) + 1
            self._health["last_decision"] = {
                "sequence_id": document.get("sequence_id"),
                "heartbeat_unix": document.get("heartbeat_unix"),
                "decision_uuid": document.get("decision_uuid"),
            }
            self._health.update(status="RUNNING", current_stage="RUNTIME LOOP",
                                loop_latency_ms=round(float(latency_ms), 3),
                                failure_owner=None, failure_reason=None)
            self._append("decision.log", "PUBLISHED", json.dumps(self._health["last_decision"], sort_keys=True))
            first = self.root / "first_decision.json"
            if not first.exists():
                self._atomic_write(first, (json.dumps(dict(document), indent=2, sort_keys=True) + "\n").encode())
            self._write_health()

    def failure(self, owner: str, error: BaseException, *, terminal: bool = False) -> None:
        if owner not in FAILURE_OWNERS:
            raise ValueError("INVALID_FAILURE_OWNER")
        self._health["exception_count"] = int(self._health["exception_count"]) + 1
        self._health.update(status="STOPPED" if terminal else "RUNNING",
                            current_stage=owner, failure_owner=owner,
                            failure_reason=f"{type(error).__name__}: {error}")
        self._append("runtime.log", "FAILURE", f"owner={owner} reason={self._health['failure_reason']}")
        self._write_health()

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
