"""Fail-closed evidence for the live decision lifecycle.

This is an observer only: it neither manufactures market data nor changes a
decision.  Evidence is emitted after the owning stage has completed.
"""
from __future__ import annotations

import json
import os
from math import isfinite
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from threading import Lock
from typing import Mapping
from uuid import UUID

from runtime.decision_publication import (
    DECISION_HEARTBEAT_MAXIMUM_AGE_SECONDS,
    DECISION_PRODUCER,
    GOVERNED_DECISION_LIFECYCLES,
    PUBLISHED_SCHEMA_VERSION,
    RUNTIME_VERSION,
)
from runtime.market_state_reader import MARKET_STATE_MAXIMUM_AGE_SECONDS
from runtime.production_metrics import ProductionMetrics


class DecisionBlockReason(str, Enum):
    NO_MARKET_STATE = "NO_MARKET_STATE"
    STALE_MARKET_STATE = "STALE_MARKET_STATE"
    INVALID_SCHEMA = "INVALID_SCHEMA"
    CONTEXT_BUILD_FAILED = "CONTEXT_BUILD_FAILED"
    ANALYSIS_FAILED = "ANALYSIS_FAILED"
    RISK_REJECTED = "RISK_REJECTED"
    DECISION_REJECTED = "DECISION_REJECTED"
    PUBLICATION_FAILED = "PUBLICATION_FAILED"


FAILURE_OWNERS = frozenset({
    "BOOT", "CONFIG", "READER", "DECISION_CONTEXT", "ANALYSIS", "RISK",
    "PUBLISHER", "HEALTH",
})
LEGACY_FAILURE_REASONS = {
    "BOOT": DecisionBlockReason.CONTEXT_BUILD_FAILED,
    "CONFIG": DecisionBlockReason.INVALID_SCHEMA,
    "READER": DecisionBlockReason.NO_MARKET_STATE,
    "DECISION_CONTEXT": DecisionBlockReason.CONTEXT_BUILD_FAILED,
    "ANALYSIS": DecisionBlockReason.ANALYSIS_FAILED,
    "RISK": DecisionBlockReason.RISK_REJECTED,
    "PUBLISHER": DecisionBlockReason.PUBLICATION_FAILED,
    "HEALTH": DecisionBlockReason.PUBLICATION_FAILED,
}


class PublicationVerificationFailure(ValueError):
    """A governed NORMAL publication failed before activation authority."""

    def __init__(self, *, owner: str, reason: DecisionBlockReason, detail: str) -> None:
        if owner not in FAILURE_OWNERS:
            raise ValueError("INVALID_FAILURE_OWNER")
        super().__init__(detail)
        self.owner = owner
        self.reason = reason
        self.detail = detail


class PublicationOutcome(str, Enum):
    NORMAL = "NORMAL"
    STALE_INPUT_FALLBACK = "STALE_INPUT_FALLBACK"
    LOGIC_ERROR_REJECTION = "LOGIC_ERROR_REJECTION"


class RuntimeObservability:
    """Trace stages, publication integrity, and STARTING/RUNNING/HEALTHY."""

    def __init__(self, root: Path | str, *, clock=None) -> None:
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)
        self._lock = Lock()
        self._clock = clock or __import__("time").time
        self._last_stage = "BOOT"
        self._last_market: dict[str, object] | None = None
        self._last_publication_sequence: int | None = None
        self._telemetry_diagnostics: list[str] = []
        try:
            self.metrics = ProductionMetrics(self.root, clock=self._clock)
        except Exception as exc:
            self.metrics = None
            self._telemetry_diagnostic("initialization", exc)
        self._health: dict[str, object] = {
            "status": "STARTING", "health_state": "HEALTHY",
            "runtime_started": False, "first_publication_at": None,
            "first_normal_decision_at": None, "loop_count": 0,
            "publication_count": 0, "successful_loop_count": 0,
            "fallback_count": 0, "rejected_loop_count": 0,
            "last_market_state": None, "last_decision": None,
            "loop_latency_ms": 0.0, "exception_count": 0,
            "current_stage": "BOOT", "failure_owner": None,
            "failure_reason": None, "failure_detail": None,
            "promotion_invariant": "FIRST_NORMAL_DECISION_NOT_VERIFIED",
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
                try:
                    self._verify_normal(document)
                except PublicationVerificationFailure as exc:
                    if (exc.reason is DecisionBlockReason.DECISION_REJECTED
                            and exc.detail.startswith("non-monotonic sequence:")):
                        self._record_metrics("duplicate_decision")
                    self.failure(exc.owner, exc, reason=exc.reason, detail=exc.detail)
                    raise
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
            publish_seconds = document.get("file_write_latency")
            if type(publish_seconds) not in (int, float) or publish_seconds <= 0:
                publish_seconds = document.get("decision_write_duration")
            publish_latency_ms = (
                float(publish_seconds) * 1000.0
                if type(publish_seconds) in (int, float) and publish_seconds >= 0
                else None
            )
            self._record_metrics(
                "decision_published",
                document,
                decision_latency_ms=latency_ms,
                json_publish_latency_ms=publish_latency_ms,
            )
            if outcome is PublicationOutcome.NORMAL:
                self._last_publication_sequence = int(document["sequence_id"])
                if not was_running:
                    self._health["first_normal_decision_at"] = now
                    self._persist_first_normal(document)
                    self._append("runtime_transition.log", "TRANSITION", "STARTING -> RUNNING")
                self._health.update(status="RUNNING", health_state="HEALTHY",
                    runtime_started=True, current_stage="RUNTIME LOOP", failure_owner=None,
                    failure_reason=None, failure_detail=None, promotion_invariant=None)
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

    def failure(self, owner: str, error: BaseException, *, terminal: bool = False,
                reason: DecisionBlockReason | None = None,
                detail: str | None = None) -> None:
        if owner not in FAILURE_OWNERS:
            raise ValueError("INVALID_FAILURE_OWNER")
        reason = reason or self._canonical_reason(owner, error)
        if not isinstance(reason, DecisionBlockReason):
            raise ValueError("INVALID_FAILURE_REASON")
        diagnostic = detail if detail is not None else (str(error) or type(error).__name__)
        self._health["exception_count"] = int(self._health["exception_count"]) + 1
        self._health.update(status="STOPPED" if terminal else self._health["status"],
            health_state="STOPPED" if terminal else "DEGRADED", current_stage=owner,
            failure_owner=owner, failure_reason=reason.value, failure_detail=diagnostic,
            promotion_invariant=reason.value if not self._health["runtime_started"] else None)
        self._append("decision_pipeline_trace.log", "REJECTED",
                     f"owner={owner} reason={reason.value} detail={diagnostic}")
        self._write_health()
        self._record_metrics("runtime_exception", owner=owner, reason=reason.value)

    def snapshot(self) -> dict[str, object]:
        return dict(self._health)

    def execution_result(self, **result: object) -> None:
        """Forward completed Executor telemetry to the passive PR252 collector."""
        self._record_metrics("execution_result", **result)

    def _record_metrics(self, method: str, *args: object, **kwargs: object) -> None:
        """Invoke non-authoritative telemetry without affecting Runtime state."""
        if self.metrics is None:
            return
        try:
            getattr(self.metrics, method)(*args, **kwargs)
        except Exception as exc:
            self._telemetry_diagnostic(method, exc)

    def _telemetry_diagnostic(self, operation: str, error: BaseException) -> None:
        # In-memory and bounded: diagnostics themselves must perform no I/O and
        # must never become an authoritative health signal.
        self._telemetry_diagnostics.append(
            f"{operation}:{type(error).__name__}:{error}"
        )
        del self._telemetry_diagnostics[:-32]

    def _verify_normal(self, document: Mapping[str, object]) -> None:
        required = ("decision_uuid", "sequence_id", "heartbeat_unix", "producer",
                    "producer_version", "schema_version", "decision_lifecycle",
                    "confidence", "market_state_sequence_id", "market_state_source_uuid",
                    "decision", "decision_timestamp", "timestamp")
        missing = tuple(key for key in required if key not in document)
        if missing:
            self._verification_failure("PUBLISHER", DecisionBlockReason.INVALID_SCHEMA,
                                       f"missing field: {missing[0]}")
        try:
            UUID(str(document["decision_uuid"]))
        except (ValueError, TypeError, AttributeError):
            self._verification_failure("PUBLISHER", DecisionBlockReason.INVALID_SCHEMA,
                                       "invalid field: decision_uuid")
        if document["producer"] != DECISION_PRODUCER:
            self._verification_failure("PUBLISHER", DecisionBlockReason.INVALID_SCHEMA,
                                       "invalid field: producer")
        if document["producer_version"] != RUNTIME_VERSION:
            self._verification_failure("PUBLISHER", DecisionBlockReason.INVALID_SCHEMA,
                                       "invalid field: producer_version")
        if document["schema_version"] != PUBLISHED_SCHEMA_VERSION:
            self._verification_failure("PUBLISHER", DecisionBlockReason.INVALID_SCHEMA,
                                       "invalid field: schema_version")
        if document["decision_lifecycle"] not in GOVERNED_DECISION_LIFECYCLES:
            self._verification_failure("PUBLISHER", DecisionBlockReason.INVALID_SCHEMA,
                                       "invalid field: decision_lifecycle")
        confidence = document["confidence"]
        if (type(confidence) not in (int, float) or not isfinite(confidence)
                or not 0 <= confidence <= 100):
            self._verification_failure("PUBLISHER", DecisionBlockReason.INVALID_SCHEMA,
                                       "invalid field: confidence")
        if (not isinstance(document["decision"], str) or not document["decision"]
                or document["decision_timestamp"] != document["timestamp"]):
            self._verification_failure("PUBLISHER", DecisionBlockReason.INVALID_SCHEMA,
                                       "invalid decision identity metadata")
        sequence = document["sequence_id"]
        heartbeat = document["heartbeat_unix"]
        if type(sequence) is not int or sequence < 1 or (
                self._last_publication_sequence is not None and sequence <= self._last_publication_sequence):
            self._verification_failure("PUBLISHER", DecisionBlockReason.DECISION_REJECTED,
                                       f"non-monotonic sequence: {sequence}")
        if (type(heartbeat) is not int or heartbeat <= 0
                or abs(float(self._clock()) - heartbeat) > DECISION_HEARTBEAT_MAXIMUM_AGE_SECONDS):
            self._verification_failure("PUBLISHER", DecisionBlockReason.STALE_MARKET_STATE,
                                       f"stale decision heartbeat: {heartbeat}")
        if self._last_market is None:
            self._verification_failure("READER", DecisionBlockReason.NO_MARKET_STATE,
                                       "no accepted market state")
        market_heartbeat = self._last_market["heartbeat_unix"]
        if (type(market_heartbeat) is not int or
                abs(float(self._clock()) - market_heartbeat) > MARKET_STATE_MAXIMUM_AGE_SECONDS):
            self._verification_failure("READER", DecisionBlockReason.STALE_MARKET_STATE,
                                       f"stale market heartbeat: {market_heartbeat}")
        if document.get("market_state_source_uuid") != self._last_market["source_uuid"]:
            self._verification_failure("PUBLISHER", DecisionBlockReason.DECISION_REJECTED,
                "market_state_source_uuid mismatch: "
                f"decision={document.get('market_state_source_uuid')} market={self._last_market['source_uuid']}")
        if document.get("market_state_sequence_id") != self._last_market["sequence_id"]:
            self._verification_failure("PUBLISHER", DecisionBlockReason.DECISION_REJECTED,
                "market_state_sequence_id mismatch: "
                f"decision={document.get('market_state_sequence_id')} market={self._last_market['sequence_id']}")

    @staticmethod
    def _verification_failure(owner: str, reason: DecisionBlockReason, detail: str) -> None:
        raise PublicationVerificationFailure(owner=owner, reason=reason, detail=detail)

    def _persist_first_normal(self, document: Mapping[str, object]) -> None:
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
    def _canonical_reason(owner: str, _error: BaseException) -> DecisionBlockReason:
        return LEGACY_FAILURE_REASONS[owner]

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
