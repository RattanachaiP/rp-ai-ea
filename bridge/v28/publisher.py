"""Crash-safe atomic publication for decision.json."""
from __future__ import annotations
import json
import os
from pathlib import Path
from typing import Any, Mapping


class AtomicDecisionPublisher:
    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)

    def publish(self, decision: Mapping[str, Any]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temporary = self.path.with_name(self.path.name + ".tmp")
        payload = (json.dumps(dict(decision), sort_keys=True, separators=(",", ":")) + "\n").encode("utf-8")
        try:
            with temporary.open("wb") as stream:
                stream.write(payload)
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(temporary, self.path)
        finally:
            try:
                temporary.unlink()
            except FileNotFoundError:
                pass
