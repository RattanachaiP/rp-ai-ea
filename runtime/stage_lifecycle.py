"""Structured, observer-only lifecycle evidence for governed Runtime bring-up."""

from __future__ import annotations

import json
import os
import time
from datetime import datetime, timezone
from pathlib import Path
from threading import Lock
from typing import Callable
from uuid import uuid4


class RuntimeStageLifecycle:
    """Append complete ENTER/SUCCESS/FAIL stage evidence without changing control flow."""

    def __init__(self, path: Path | str | None = None, *, clock: Callable[[], float] = time.time):
        configured = os.environ.get("RP_RUNTIME_STAGE_TRACE")
        self.path = Path(path or configured or "logs/runtime_stage_trace.jsonl")
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._clock = clock
        self._lock = Lock()

    @staticmethod
    def _timestamp(value: float) -> str:
        return datetime.fromtimestamp(value, timezone.utc).isoformat().replace("+00:00", "Z")

    def stage(self, name: str, upstream_dependency: str) -> "RuntimeStageSpan":
        return RuntimeStageSpan(self, name, upstream_dependency)

    def termination(self, error: BaseException, propagation_path: tuple[str, ...]) -> None:
        now = self._clock()
        self._emit({
            "event": "RUNTIME_TERMINATED",
            "stage_name": propagation_path[0] if propagation_path else "Runtime",
            "stage_uuid": None,
            "start_timestamp": None,
            "end_timestamp": self._timestamp(now),
            "duration_ms": None,
            "upstream_dependency": propagation_path[1] if len(propagation_path) > 1 else None,
            "failure_reason": str(error) or type(error).__name__,
            "exception_type": type(error).__name__,
            "exception_message": str(error) or None,
            "propagation_path": list(propagation_path),
        })

    def _emit(self, event: dict[str, object]) -> None:
        with self._lock, self.path.open("a", encoding="utf-8") as stream:
            stream.write(json.dumps(event, sort_keys=True, separators=(",", ":")) + "\n")
            stream.flush()


class RuntimeStageSpan:
    def __init__(self, lifecycle: RuntimeStageLifecycle, name: str, dependency: str):
        self.lifecycle = lifecycle
        self.name = name
        self.dependency = dependency
        self.uuid = str(uuid4())
        self.started = 0.0

    def __enter__(self) -> "RuntimeStageSpan":
        self.started = self.lifecycle._clock()
        self._emit("ENTER", self.started, None)
        return self

    def __exit__(self, exception_type, exception, _traceback) -> bool:
        ended = self.lifecycle._clock()
        self._emit("FAIL" if exception is not None else "SUCCESS", ended, exception)
        return False

    def _emit(self, status: str, ended: float, exception: BaseException | None) -> None:
        is_enter = status == "ENTER"
        self.lifecycle._emit({
            "event": status,
            "stage_name": self.name,
            "stage_uuid": self.uuid,
            "start_timestamp": self.lifecycle._timestamp(self.started),
            "end_timestamp": None if is_enter else self.lifecycle._timestamp(ended),
            "duration_ms": None if is_enter else round((ended - self.started) * 1000.0, 3),
            "upstream_dependency": self.dependency,
            "failure_reason": (str(exception) or type(exception).__name__) if exception else None,
            "exception_type": type(exception).__name__ if exception else None,
            "exception_message": (str(exception) or None) if exception else None,
            "propagation_path": [self.name, self.dependency] if exception else [],
        })
