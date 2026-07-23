"""Append-only, non-execution telemetry for Knowledge observations."""
from __future__ import annotations

import json
from queue import Full, Queue
from threading import Event, Thread
from pathlib import Path
from typing import Any, Protocol


class KnowledgeObservationAuditSink(Protocol):
    """A dedicated sink which is never part of a published decision payload."""

    def try_enqueue(self, observation: dict[str, Any]) -> bool: ...


class JsonLinesKnowledgeObservationAuditSink:
    """Queue bounded telemetry and write it on a dedicated daemon worker."""

    def __init__(self, path: Path | str, *, max_queue_size: int = 256) -> None:
        self._path = Path(path)
        self._queue: Queue[dict[str, Any] | None] = Queue(maxsize=max_queue_size)
        self.dropped_count = 0
        self._closed = Event()
        self._worker = Thread(target=self._run, name="knowledge-observation-audit", daemon=True)
        self._worker.start()

    def try_enqueue(self, observation: dict[str, Any]) -> bool:
        if self._closed.is_set():
            return False
        try:
            self._queue.put_nowait(dict(observation))
            return True
        except Full:
            self.dropped_count += 1
            return False

    def shutdown(self, timeout_seconds: float = 0.005) -> None:
        self._closed.set()
        try:
            self._queue.put_nowait(None)
        except Full:
            self.dropped_count += 1
        self._worker.join(timeout_seconds)

    def _run(self) -> None:
        while not self._closed.is_set() or not self._queue.empty():
            item = self._queue.get()
            if item is None:
                return
            self._write(item)

    def _write(self, observation: dict[str, Any]) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        with self._path.open("a", encoding="utf-8") as stream:
            stream.write(json.dumps(observation, sort_keys=True, separators=(",", ":")) + "\n")
