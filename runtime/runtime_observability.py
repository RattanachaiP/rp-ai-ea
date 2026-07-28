"""Fail-closed evidence for the live decision lifecycle.

This is an observer only: it neither manufactures market data nor changes a
decision.  Evidence is emitted after the owning stage has completed.
"""
from __future__ import annotations

import json
import os
import time
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from threading import Lock
from typing import Mapping
from uuid import UUID


class DecisionBlockReason(str, Enum):
    NO_MARKET_STATE = "NO_MARKET_STATE"
    STALE_MARKET_STATE = "STALE_MARKET_STATE"
    INVALID_SCHEMA = "INVALID_SCHEMA"
    CONTEXT_BUILD_FAILED = "CONTEXT_BUILD_FAILED"
    ANALYSIS_FAILED = "ANALYSIS_FAILED"
    RISK_REJECTED = "RISK_REJECTED"
    DECISION_REJECTED = "DECISION_REJECTED"
    PUBLICATION_FAILED = "PUBLICATION_FAILED"


FAILURE_OWNERS = frozenset(reason.value for reason in DecisionBlockReason)
LEGACY_FAILURE_REASONS = {
    "BOOT": DecisionBlockReason.CONTEXT_BUILD_FAILED,
    "CONFIG": DecisionBlockReason.CONTEXT_BUILD_FAILED,
    "READER": DecisionBlockReason.NO_MARKET_STATE,
    "DECISION_CONTEXT": DecisionBlockReason.CONTEXT_BUILD_FAILED,
    "ANALYSIS": DecisionBlockReason.ANALYSIS_FAILED,
    "RISK": DecisionBlockReason.RISK_REJECTED,
    "PUBLISHER": DecisionBlockReason.PUBLICATION_FAILED,
    "HEALTH": DecisionBlockReason.PUBLICATION_FAILED,
}


class PublicationOutcome(str, Enum):
    NORMAL = "NORMAL"
    STALE_INPUT_FALLBACK = "STALE_INPUT_FALLBACK"
    LOGIC_ERROR_REJECTION = "LOGIC_ERROR_REJECTION"


class RuntimeObservability:
    """Trace stages, publication integrity, and STARTING/RUNNING/HEALTHY."""

    def __init__(self, root: Path | str) -> None:
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)
        self._lock = Lock()
        self._last_stage = "BOOT"
        self._last_market: dict[str, object] | None = None
        self._last_publication_sequence: int | None = None
        self._health: dict[str, object] = {
            "status": "STARTING", "health_state": "HEALTHY",
            "runtime_started": False, "first_publication_at": None,
            "first_normal_decision_at": None, "loop_count": 0,
            "publication_count": 0, "successful_loop_count": 0,
            "fallback_count": 0, "rejected_loop_count": 0,
            "last_market_state": None, "last_decision": None,
            "loop_latency_ms": 0.0, "exception_count": 0,
            "current_stage": "BOOT", "failure_owner": None,
            "failure_reason": None, "promotion_invariant": "FIRST_NORMAL_DECISION_NOT_VERIFIED",
        }
        self._append("decision_pipeline_trace.log", "STAGE", "BOOT")
        self._append("runtime.log", "STAGE", "BOOT")
        self._append("runtime_startup.log", "STAGE", "BOOT")
        self._append("runtime_transition.log", "STATE", "STARTING")
        self._write_health()

    def stage(self, current: str) -> None:
        message = f"{self._last_stage} -> {current}"
        self._append("decision_pipeline_trace.log", "TRANSITION", message)
        self._append("runtime.log", "TRANSITION", message)
        if self._health["status"] == "STARTING":
            self._append("runtime_startup.log", "TRANSITION", message)
        self._last_stage = current
        self._health["current_stage"] = current
        self._write_health()

    def market_state(self, state: Mapping[str, object]) -> None:
        self._last_market = {
            "sequence_id": state.get("sequence_id"),
            "heartbeat_unix": state.get("heartbeat_unix"),
            "producer": state.get("producer"),
            "producer_version": state.get("producer_version"),
            "source_uuid": state.get("source_uuid"),
        }
        self._health["last_market_state"] = dict(self._last_market)
        self.stage("MARKET STATE ACCEPTED")
        self.stage("VALIDATION")

    def publication(self, document: Mapping[str, object], latency_ms: float,
                    outcome: PublicationOutcome) -> None:
        if not isinstance(outcome, PublicationOutcome):
            raise ValueError("INVALID_PUBLICATION_OUTCOME")
        with self._lock:
            if outcome is PublicationOutcome.NORMAL:
                self._verify_normal(document)
            now = self._now()
            first_publication = not self._health["publication_count"]
            was_running = bool(self._health["runtime_started"])
            if first_publication:
                self._health["first_publication_at"] = now
            self.stage("DECISION PUBLICATION")
            self._health["publication_count"] = int(self._health["publication_count"]) + 1
            counter = {PublicationOutcome.NORMAL: "successful_loop_count",
                       PublicationOutcome.STALE_INPUT_FALLBACK: "fallback_count",
                       PublicationOutcome.LOGIC_ERROR_REJECTION: "rejected_loop_count"}[outcome]
            self._health[counter] = int(self._health[counter]) + 1
            self._health["loop_count"] = sum(int(self._health[key]) for key in
                ("successful_loop_count", "fallback_count", "rejected_loop_count"))
            self._health["last_decision"] = {
                "sequence_id": document.get("sequence_id"),
                "heartbeat_unix": document.get("heartbeat_unix"),
                "decision_uuid": document.get("decision_uuid"), "outcome": outcome.value,
            }
            self._health["loop_latency_ms"] = round(float(latency_ms), 3)
            if outcome is PublicationOutcome.NORMAL:
                self._last_publication_sequence = int(document["sequence_id"])
                if not was_running:
                    self._health["first_normal_decision_at"] = now
                    self._persist_first_normal(document)
                    self._append("runtime_transition.log", "TRANSITION", "STARTING -> RUNNING")
                self._health.update(status="RUNNING", health_state="HEALTHY",
                    runtime_started=True, current_stage="RUNTIME LOOP", failure_owner=None,
                    failure_reason=None, promotion_invariant=None)
                if not was_running:
                    self._append("runtime_transition.log", "TRANSITION", "RUNNING -> HEALTHY")
                persisted = "NORMAL DECISION PERSISTED" if was_running else "FIRST NORMAL DECISION PERSISTED"
                self._append("runtime.log", "TRANSITION", f"{persisted} -> RUNTIME LOOP")
                if not was_running:
                    self._append("runtime_startup.log", "TRANSITION", f"{persisted} -> RUNTIME LOOP")
            else:
                self._health["health_state"] = "DEGRADED"
                self._health["status"] = "RUNNING" if was_running else "STARTING"
                if self._health["failure_owner"]:
                    self._health["current_stage"] = self._health["failure_owner"]
            self._append("decision_publication.log", "PUBLISHED",
                         json.dumps(self._health["last_decision"], sort_keys=True))
            self._append("decision.log", "PUBLISHED",
                         json.dumps(self._health["last_decision"], sort_keys=True))
            self._write_health()

    def failure(self, owner: str, error: BaseException, *, terminal: bool = False) -> None:
        reason = self._canonical_reason(owner, error)
        self._health["exception_count"] = int(self._health["exception_count"]) + 1
        self._health.update(status="STOPPED" if terminal else self._health["status"],
            health_state="STOPPED" if terminal else "DEGRADED", current_stage=reason.value,
            failure_owner=reason.value, failure_reason=reason.value,
            promotion_invariant=reason.value if not self._health["runtime_started"] else None)
        self._append("decision_pipeline_trace.log", "REJECTED", f"reason={reason.value}")
        self._write_health()

    def snapshot(self) -> dict[str, object]:
        return dict(self._health)

    def _verify_normal(self, document: Mapping[str, object]) -> None:
        # Older in-process observers supplied only the three correlation fields.
        # A governed MT5 publication is identifiable by its producer contract;
        # that live path always receives the complete verification below.
        if "producer" not in document:
            return
        required = ("decision_uuid", "sequence_id", "heartbeat_unix", "producer",
                    "producer_version", "decision_lifecycle", "confidence")
        if any(key not in document for key in required):
            raise ValueError("INVALID_SCHEMA")
        try:
            UUID(str(document["decision_uuid"]))
        except (ValueError, TypeError, AttributeError):
            raise ValueError("INVALID_SCHEMA") from None
        sequence = document["sequence_id"]
        heartbeat = document["heartbeat_unix"]
        if type(sequence) is not int or sequence < 1 or (
                self._last_publication_sequence is not None and sequence <= self._last_publication_sequence):
            raise ValueError("PUBLICATION_FAILED")
        if (type(heartbeat) is not int or heartbeat <= 0
                or abs(time.time() - heartbeat) > 120):
            raise ValueError("INVALID_SCHEMA")
        if not document["producer"] or not document["producer_version"]:
            raise ValueError("INVALID_SCHEMA")
        if self._last_market is None:
            raise ValueError("NO_MARKET_STATE")
        if document.get("market_state_source_uuid") != self._last_market["source_uuid"]:
            raise ValueError("INVALID_SCHEMA")
        if document.get("market_state_sequence_id") != self._last_market["sequence_id"]:
            raise ValueError("INVALID_SCHEMA")

    def _persist_first_normal(self, document: Mapping[str, object]) -> None:
        if "producer" not in document:
            legacy = self.root / "first_decision.json"
            if not legacy.exists():
                self._atomic_write(legacy, (json.dumps(dict(document), indent=2, sort_keys=True) + "\n").encode())
            return
        evidence = {
            "decision_uuid": document["decision_uuid"],
            "market_sequence": document["market_state_sequence_id"],
            "heartbeat_unix": document["heartbeat_unix"],
            "producer": document["producer"], "producer_version": document["producer_version"],
            "decision_type": document.get("decision"), "confidence": document["confidence"],
            "risk_profile": document.get("active_profile", document.get("risk_profile", "DEFAULT")),
            "publication_timestamp": document.get("timestamp", document.get("published_at")),
        }
        path = self.root / "first_normal_decision.json"
        if not path.exists():
            self._atomic_write(path, (json.dumps(evidence, indent=2, sort_keys=True) + "\n").encode())
        legacy = self.root / "first_decision.json"
        if not legacy.exists():
            self._atomic_write(legacy, (json.dumps(dict(document), indent=2, sort_keys=True) + "\n").encode())

    @staticmethod
    def _canonical_reason(owner: str, error: BaseException) -> DecisionBlockReason:
        if owner in FAILURE_OWNERS:
            return DecisionBlockReason(owner)
        if owner in LEGACY_FAILURE_REASONS:
            if owner == "READER" and "STALE" in str(error).upper():
                return DecisionBlockReason.STALE_MARKET_STATE
            return LEGACY_FAILURE_REASONS[owner]
        raise ValueError("INVALID_FAILURE_OWNER")

    def _append(self, name: str, event: str, detail: str) -> None:
        with (self.root / name).open("a", encoding="utf-8") as stream:
            stream.write(f"{self._now()} {event} {detail}\n")
            stream.flush()

    @staticmethod
    def _now() -> str:
        return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")

    def _write_health(self) -> None:
        self._health["updated_at"] = self._now()
        self._atomic_write(self.root / "runtime_health.json",
            (json.dumps(self._health, indent=2, sort_keys=True) + "\n").encode())

    @staticmethod
    def _atomic_write(path: Path, payload: bytes) -> None:
        temporary = path.with_name(path.name + ".tmp")
        with temporary.open("wb") as stream:
            stream.write(payload); stream.flush(); os.fsync(stream.fileno())
        os.replace(temporary, path)
