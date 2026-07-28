"""Fail-closed reader for the MT5-owned V28 market-state boundary."""
from __future__ import annotations

import json
from math import isfinite
from pathlib import Path
import time
from typing import Any, Callable, Mapping

REQUIRED_MARKET_FIELDS = frozenset({
    "symbol", "timeframe", "heartbeat_unix", "sequence_id", "bid", "ask",
})


class MarketStateError(ValueError):
    """A classified market-state validation failure."""

    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


class MarketReader:
    def __init__(self, path: str | Path, *, max_age_seconds: float = 5.0,
                 allowed_future_skew_seconds: float = 2.0,
                 clock: Callable[[], float] = time.time) -> None:
        self.path = Path(path)
        self.max_age_seconds = _non_negative(max_age_seconds, "INVALID_MAX_AGE")
        self.allowed_future_skew_seconds = _non_negative(
            allowed_future_skew_seconds, "INVALID_FUTURE_SKEW"
        )
        self.clock = clock

    def read(self) -> dict[str, Any]:
        try:
            value = json.loads(self.path.read_text(encoding="utf-8"))
        except FileNotFoundError as error:
            raise MarketStateError("MARKET_STATE_MISSING") from error
        except (OSError, UnicodeDecodeError, json.JSONDecodeError) as error:
            raise MarketStateError("MARKET_STATE_MALFORMED_JSON") from error
        self.validate_schema(value)
        self.validate_heartbeat(value)
        self.validate_freshness(value)
        return dict(value)

    @staticmethod
    def validate_schema(value: object) -> None:
        if type(value) is not dict:
            raise MarketStateError("SCHEMA_INVALID_ROOT")
        missing = REQUIRED_MARKET_FIELDS - value.keys()
        if missing:
            raise MarketStateError("SCHEMA_MISSING_FIELDS:" + ",".join(sorted(missing)))
        if not isinstance(value["symbol"], str) or not value["symbol"].strip():
            raise MarketStateError("SCHEMA_INVALID_SYMBOL")
        if not isinstance(value["timeframe"], str) or not value["timeframe"].strip():
            raise MarketStateError("SCHEMA_INVALID_TIMEFRAME")
        if type(value["sequence_id"]) is not int or value["sequence_id"] < 0:
            raise MarketStateError("SCHEMA_INVALID_SEQUENCE")
        for field in ("bid", "ask"):
            if not _finite_number(value[field]) or value[field] <= 0:
                raise MarketStateError("SCHEMA_INVALID_" + field.upper())
        if value["ask"] < value["bid"]:
            raise MarketStateError("SCHEMA_INVALID_QUOTE")

    def validate_heartbeat(self, value: Mapping[str, Any]) -> None:
        heartbeat = value["heartbeat_unix"]
        if not _finite_number(heartbeat) or heartbeat <= 0:
            raise MarketStateError("HEARTBEAT_INVALID")
        now = self.clock()
        if not _finite_number(now):
            raise MarketStateError("CLOCK_INVALID")
        if heartbeat - now > self.allowed_future_skew_seconds:
            raise MarketStateError("HEARTBEAT_FUTURE")

    def validate_freshness(self, value: Mapping[str, Any]) -> None:
        if self.clock() - value["heartbeat_unix"] > self.max_age_seconds:
            raise MarketStateError("MARKET_STATE_STALE")


def _finite_number(value: object) -> bool:
    return type(value) in (int, float) and isfinite(value)


def _non_negative(value: object, code: str) -> float:
    if not _finite_number(value) or value < 0:
        raise ValueError(code)
    return float(value)
