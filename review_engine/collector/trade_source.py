"""Read-only source boundary for already-exported trade evidence."""
from __future__ import annotations
from abc import ABC, abstractmethod
import json
from pathlib import Path
from typing import Iterable, Mapping

class TradeSource(ABC):
    @abstractmethod
    def read_events(self) -> Iterable[Mapping[str, object]]:
        """Return copies of source records; implementations must never mutate sources."""

class FileTradeSource(TradeSource):
    """Reads JSON objects from exported JSONL files without locking or rewriting them."""
    def __init__(self, paths: Iterable[Path | str]) -> None:
        self._paths = tuple(Path(path) for path in paths)

    def read_events(self) -> Iterable[Mapping[str, object]]:
        for path in self._paths:
            try:
                with path.open(encoding="utf-8") as stream:
                    for line in stream:
                        if line.strip():
                            parsed = json.loads(line)
                            if isinstance(parsed, dict):
                                yield parsed
            except (OSError, UnicodeDecodeError, json.JSONDecodeError):
                continue
