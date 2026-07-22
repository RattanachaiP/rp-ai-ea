"""Read-only source adapters. New exported-artifact formats implement TradeSource."""
from abc import ABC, abstractmethod
import csv, json
from pathlib import Path
from typing import Any, Iterable, Mapping

class TradeSource(ABC):
    @abstractmethod
    def read_records(self) -> Iterable[Mapping[str, Any]]:
        """Yield copies of observed closed-trade records without modifying the source."""

class CSVTradeSource(TradeSource):
    def __init__(self, path: str | Path): self.path = Path(path)
    def read_records(self):
        with self.path.open("r", encoding="utf-8", newline="") as stream:
            yield from csv.DictReader(stream)

class ReplayTradeSource(TradeSource):
    """Fixture/in-memory source used for deterministic replays."""
    def __init__(self, records: Iterable[Mapping[str, Any]]): self._records = tuple(dict(x) for x in records)
    def read_records(self):
        yield from (dict(x) for x in self._records)
