"""Append-only, non-execution telemetry for Knowledge observations."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Protocol


class KnowledgeObservationAuditSink(Protocol):
    """A dedicated sink which is never part of a published decision payload."""

    def record(self, observation: dict[str, Any]) -> None: ...


class JsonLinesKnowledgeObservationAuditSink:
    """Write bounded observation metadata as one append-only JSON line."""

    def __init__(self, path: Path | str) -> None:
        self._path = Path(path)

    def record(self, observation: dict[str, Any]) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        with self._path.open("a", encoding="utf-8") as stream:
            stream.write(json.dumps(observation, sort_keys=True, separators=(",", ":")) + "\n")
