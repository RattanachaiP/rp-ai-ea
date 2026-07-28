"""Production-only telemetry for the decision and execution lifecycle.

The collector is deliberately observational.  Callers report completed events;
the collector never retries, rejects, or otherwise changes trading behaviour.
"""
from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from math import isfinite
from pathlib import Path
from threading import Lock
from typing import Mapping


SCHEMA_VERSION = "PR252.RUNTIME_METRICS.1.0"


class ProductionMetrics:
    """Persist cumulative and UTC-day runtime telemetry atomically."""

    def __init__(self, root: Path | str, *, clock=None) -> None:
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)
        self._clock = clock or __import__("time").time
        self._lock = Lock()
        self._started_unix = float(self._clock())
        previous = self._load_previous()
        self._metrics = self._new_metrics(int(previous.get("runtime_restart_count", -1)) + 1)
        self._publish()

    def decision_published(
        self,
        document: Mapping[str, object],
        *,
        decision_latency_ms: float,
        json_publish_latency_ms: float | None = None,
        duplicate: bool = False,
    ) -> None:
        """Record a completed JSON publication without affecting its outcome."""
        with self._lock:
            self._observe("decision_latency_ms", decision_latency_ms)
            self._observe(
                "json_publish_latency_ms",
                decision_latency_ms if json_publish_latency_ms is None else json_publish_latency_ms,
            )
            self._metrics["decision_publish_count"] += 1
            if duplicate:
                self._metrics["duplicate_decision_count"] += 1
            self._metrics["last_decision_uuid"] = document.get("decision_uuid")
            self._publish()

    def duplicate_decision(self) -> None:
        with self._lock:
            self._metrics["duplicate_decision_count"] += 1
            self._publish()

    def runtime_exception(self, *, owner: str, reason: str) -> None:
        with self._lock:
            self._metrics["runtime_exception_count"] += 1
            self._metrics["last_runtime_exception"] = {"owner": owner, "reason": reason}
            self._publish()

    def execution_result(
        self,
        *,
        decision_to_execution_latency_ms: float,
        mt5_execution_latency_ms: float,
        spread_at_entry_points: float | None,
        slippage_points: float | None,
        accepted: bool,
        rejection_reason: str | None = None,
    ) -> None:
        """Record an already completed Executor result."""
        if accepted and rejection_reason is not None:
            raise ValueError("ACCEPTED_EXECUTION_HAS_REJECTION_REASON")
        if not accepted and (not isinstance(rejection_reason, str) or not rejection_reason.strip()):
            raise ValueError("REJECTED_EXECUTION_REQUIRES_REASON")
        with self._lock:
            self._observe("decision_to_execution_latency_ms", decision_to_execution_latency_ms)
            self._observe("mt5_execution_latency_ms", mt5_execution_latency_ms)
            if spread_at_entry_points is not None:
                self._observe("spread_at_entry_points", spread_at_entry_points)
            if slippage_points is not None:
                self._observe("slippage_points", slippage_points, allow_negative=True)
            key = "execution_accept_count" if accepted else "execution_rejection_count"
            self._metrics[key] += 1
            if rejection_reason is not None:
                reasons = self._metrics["execution_rejection_reasons"]
                reasons[rejection_reason] = int(reasons.get(rejection_reason, 0)) + 1
                self._metrics["last_execution_rejection_reason"] = rejection_reason
            self._publish()

    def snapshot(self) -> dict[str, object]:
        with self._lock:
            self._refresh_runtime_fields()
            return json.loads(json.dumps(self._metrics))

    def _new_metrics(self, restart_count: int) -> dict[str, object]:
        return {
            "schema_version": SCHEMA_VERSION,
            "runtime_started_at_utc": self._iso(self._started_unix),
            "runtime_uptime_seconds": 0.0,
            "runtime_restart_count": restart_count,
            "decision_publish_count": 0,
            "execution_accept_count": 0,
            "execution_rejection_count": 0,
            "duplicate_decision_count": 0,
            "runtime_exception_count": 0,
            "decision_latency_ms": self._series(),
            "decision_to_execution_latency_ms": self._series(),
            "json_publish_latency_ms": self._series(),
            "mt5_execution_latency_ms": self._series(),
            "spread_at_entry_points": self._series(),
            "slippage_points": self._series(),
            "execution_rejection_reasons": {},
            "last_execution_rejection_reason": None,
            "last_runtime_exception": None,
            "last_decision_uuid": None,
            "updated_at_utc": self._iso(self._started_unix),
        }

    @staticmethod
    def _series() -> dict[str, object]:
        return {"count": 0, "total": 0.0, "average": None, "minimum": None, "maximum": None}

    def _observe(self, key: str, value: float, *, allow_negative: bool = False) -> None:
        if type(value) not in (int, float) or not isfinite(float(value)):
            raise ValueError(f"INVALID_METRIC:{key}")
        number = float(value)
        if not allow_negative and number < 0:
            raise ValueError(f"INVALID_METRIC:{key}")
        series = self._metrics[key]
        series["count"] += 1
        series["total"] = round(float(series["total"]) + number, 6)
        series["average"] = round(float(series["total"]) / int(series["count"]), 6)
        series["minimum"] = number if series["minimum"] is None else min(float(series["minimum"]), number)
        series["maximum"] = number if series["maximum"] is None else max(float(series["maximum"]), number)

    def _publish(self) -> None:
        self._refresh_runtime_fields()
        self._atomic_write(self.root / "runtime_metrics.json", self._metrics)
        day = str(self._metrics["updated_at_utc"])[:10]
        summary = {
            "schema_version": SCHEMA_VERSION,
            "summary_date_utc": day,
            "generated_at_utc": self._metrics["updated_at_utc"],
            "runtime_uptime_seconds": self._metrics["runtime_uptime_seconds"],
            "runtime_restart_count": self._metrics["runtime_restart_count"],
            "decision_publish_count": self._metrics["decision_publish_count"],
            "execution_accept_count": self._metrics["execution_accept_count"],
            "execution_rejection_count": self._metrics["execution_rejection_count"],
            "duplicate_decision_count": self._metrics["duplicate_decision_count"],
            "runtime_exception_count": self._metrics["runtime_exception_count"],
            "latency_ms": {key: self._metrics[key] for key in (
                "decision_latency_ms", "decision_to_execution_latency_ms",
                "json_publish_latency_ms", "mt5_execution_latency_ms")},
            "entry_execution": {key: self._metrics[key] for key in (
                "spread_at_entry_points", "slippage_points")},
            "execution_rejection_reasons": self._metrics["execution_rejection_reasons"],
        }
        self._atomic_write(self.root / "runtime_daily_summary.json", summary)

    def _refresh_runtime_fields(self) -> None:
        now = float(self._clock())
        self._metrics["runtime_uptime_seconds"] = round(max(0.0, now - self._started_unix), 3)
        self._metrics["updated_at_utc"] = self._iso(now)

    def _load_previous(self) -> Mapping[str, object]:
        path = self.root / "runtime_metrics.json"
        if not path.exists():
            return {}
        try:
            value = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return {}
        return value if isinstance(value, dict) and value.get("schema_version") == SCHEMA_VERSION else {}

    @staticmethod
    def _iso(timestamp: float) -> str:
        return datetime.fromtimestamp(timestamp, timezone.utc).isoformat().replace("+00:00", "Z")

    @staticmethod
    def _atomic_write(path: Path, document: Mapping[str, object]) -> None:
        payload = (json.dumps(document, indent=2, sort_keys=True) + "\n").encode()
        temporary = path.with_name(path.name + ".tmp")
        with temporary.open("wb") as stream:
            stream.write(payload)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
