"""Fail-closed reader for the canonical MT5 ``market_state.json`` contract.

The writer publishes by atomic rename.  This reader opens the published inode
once and additionally verifies that it did not change while being consumed.
It deliberately retains no stale/cached market state on failure.
"""

from __future__ import annotations

import json
import os
import stat
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from types import MappingProxyType
from typing import Callable, Mapping
from uuid import UUID, uuid5


PRODUCER = "RP_AI_MT5_MARKET_STATE"
PRODUCER_VERSION = "V1"
SCHEMA_VERSION = "1.0"
SOURCE_UUID = "dc3777c6-cf0d-5a7b-bd58-8a5c44568475"

REQUIRED_FIELDS = {
    "producer": str, "producer_version": str, "schema_version": str,
    "source_uuid": str, "symbol": str, "timeframe": str, "time_sync": str,
    "heartbeat_unix": int, "sequence_id": int, "server_time": str,
    "bar_time": str, "bid": (int, float), "ask": (int, float),
    "ma50": (int, float), "ma90": (int, float), "ma200": (int, float),
    "rsi": (int, float), "macd_main": (int, float),
    "macd_signal": (int, float), "macd_hist": (int, float),
    "bb_upper": (int, float), "bb_middle": (int, float),
    "bb_lower": (int, float), "bb3_upper": (int, float),
    "bb3_middle": (int, float), "bb3_lower": (int, float),
    "bb4_upper": (int, float), "bb4_middle": (int, float),
    "bb4_lower": (int, float), "buyScore": int, "sellScore": int,
}


class MarketStateReaderError(ValueError):
    """A governed publication was rejected; the message is a stable reason."""


@dataclass(frozen=True, slots=True)
class ValidatedMarketState:
    market_state_uuid: str
    sequence_id: int
    timestamp: str
    symbol: str
    timeframe: str
    producer: str
    producer_version: str
    schema_version: str
    source_uuid: str
    values: Mapping[str, object]

    def __post_init__(self) -> None:
        UUID(self.market_state_uuid)
        object.__setattr__(self, "values", MappingProxyType(dict(self.values)))


@dataclass(frozen=True, slots=True)
class ReaderDiagnostic:
    producer: str
    schema: str
    sequence: int | None
    heartbeat: int | None
    status: str
    reason: str

    def render(self) -> str:
        return "\n".join(("[READER]", f"Producer={self.producer}",
            f"Schema={self.schema}", f"Sequence={self.sequence}",
            f"Heartbeat={self.heartbeat}", f"Status={self.status}",
            f"Reason={self.reason}"))


class GovernedMarketStateReader:
    """Validate one canonical publication and enforce monotonic continuity."""

    def __init__(self, *, maximum_age_seconds: int = 30,
                 maximum_future_skew_seconds: int = 2,
                 clock: Callable[[], float] | None = None) -> None:
        if type(maximum_age_seconds) is not int or maximum_age_seconds <= 0:
            raise ValueError("INVALID_FRESHNESS_POLICY")
        if type(maximum_future_skew_seconds) is not int or maximum_future_skew_seconds < 0:
            raise ValueError("INVALID_FRESHNESS_POLICY")
        self.maximum_age_seconds = maximum_age_seconds
        self.maximum_future_skew_seconds = maximum_future_skew_seconds
        self._clock = clock or __import__("time").time
        self._last_sequence: int | None = None
        self.last_diagnostic: ReaderDiagnostic | None = None

    def _reject(self, reason: str, data: Mapping[str, object] | None = None):
        data = data or {}
        self.last_diagnostic = ReaderDiagnostic(str(data.get("producer", "UNKNOWN")),
            str(data.get("schema_version", "UNKNOWN")),
            data.get("sequence_id") if type(data.get("sequence_id")) is int else None,
            data.get("heartbeat_unix") if type(data.get("heartbeat_unix")) is int else None,
            "REJECTED", reason)
        raise MarketStateReaderError(reason)

    def read(self, path: str | Path) -> ValidatedMarketState:
        path = Path(path)
        if path.name != "market_state.json":
            self._reject("NON_CANONICAL_PUBLICATION")
        try:
            with path.open("rb") as stream:
                before = os.fstat(stream.fileno())
                if not stat.S_ISREG(before.st_mode):
                    self._reject("INVALID_PUBLICATION_TYPE")
                raw = stream.read()
                after = os.fstat(stream.fileno())
            current = path.stat()
        except (OSError, MarketStateReaderError) as exc:
            if isinstance(exc, MarketStateReaderError):
                raise
            self._reject("ATOMIC_READ_FAILED")
        if ((before.st_dev, before.st_ino, before.st_size, before.st_mtime_ns) !=
                (after.st_dev, after.st_ino, after.st_size, after.st_mtime_ns) or
                (after.st_dev, after.st_ino) != (current.st_dev, current.st_ino)):
            self._reject("PUBLICATION_CHANGED_DURING_READ")
        try:
            text = raw.decode("utf-8", errors="strict")
        except UnicodeDecodeError:
            self._reject("INVALID_UTF8")
        try:
            data = json.loads(text)
        except json.JSONDecodeError:
            self._reject("INVALID_OR_PARTIAL_JSON")
        if type(data) is not dict:
            self._reject("INVALID_JSON_SCHEMA")
        missing = tuple(sorted(set(REQUIRED_FIELDS) - set(data)))
        if missing:
            self._reject("MISSING_REQUIRED_FIELDS:" + ",".join(missing), data)
        if any(type(data[name]) not in ((kind,) if isinstance(kind, type) else kind)
               for name, kind in REQUIRED_FIELDS.items()):
            self._reject("INVALID_JSON_SCHEMA", data)
        if (data["producer"], data["producer_version"], data["source_uuid"]) != (
                PRODUCER, PRODUCER_VERSION, SOURCE_UUID):
            self._reject("UNKNOWN_PRODUCER", data)
        if data["schema_version"] != SCHEMA_VERSION:
            self._reject("UNSUPPORTED_SCHEMA_VERSION", data)
        if not data["symbol"].strip() or not data["timeframe"].strip():
            self._reject("INVALID_REQUIRED_FIELD", data)
        heartbeat, sequence, now = data["heartbeat_unix"], data["sequence_id"], int(self._clock())
        if sequence < 1 or heartbeat < 1:
            self._reject("INVALID_REQUIRED_FIELD", data)
        if heartbeat > now + self.maximum_future_skew_seconds:
            self._reject("FUTURE_HEARTBEAT", data)
        if now - heartbeat > self.maximum_age_seconds:
            self._reject("STALE_HEARTBEAT", data)
        if self._last_sequence is not None and sequence <= self._last_sequence:
            self._reject("SEQUENCE_ROLLBACK", data)

        timestamp = datetime.fromtimestamp(heartbeat, timezone.utc).isoformat().replace("+00:00", "Z")
        identity = str(uuid5(UUID(SOURCE_UUID), f"{sequence}:{heartbeat}:{data['symbol']}:{data['timeframe']}"))
        result = ValidatedMarketState(identity, sequence, timestamp, data["symbol"],
            data["timeframe"], PRODUCER, PRODUCER_VERSION, SCHEMA_VERSION,
            SOURCE_UUID, data)
        self._last_sequence = sequence  # commit only after every check succeeds
        self.last_diagnostic = ReaderDiagnostic(PRODUCER, SCHEMA_VERSION, sequence,
            heartbeat, "OK", "VALIDATED")
        return result
