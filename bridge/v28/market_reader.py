"""Fail-closed reader for the authoritative MT5 Writer market contract."""
from __future__ import annotations
import json
from math import isfinite
from pathlib import Path
from typing import Any, Mapping

PRODUCER = "RP_AI_MT5_MARKET_STATE"
PRODUCER_VERSION = "V1"
SCHEMA_VERSION = "1.0"
SOURCE_UUID = "dc3777c6-cf0d-5a7b-bd58-8a5c44568475"
REQUIRED_MARKET_FIELDS = frozenset({
    "producer", "producer_version", "schema_version", "source_uuid", "symbol",
    "timeframe", "heartbeat_unix", "sequence_id", "bid", "ask",
})


class MarketStateError(ValueError):
    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


class MarketReader:
    def __init__(self, path: str | Path, *, expected_symbol: str = "XAUUSD",
                 expected_timeframe: str | None = None, max_age_seconds: float = 5.0,
                 allowed_future_skew_seconds: float = 2.0) -> None:
        self.path = Path(path)
        self.expected_symbol = _identifier(expected_symbol, "INVALID_EXPECTED_SYMBOL")
        self.expected_timeframe = (_identifier(expected_timeframe, "INVALID_EXPECTED_TIMEFRAME")
                                   if expected_timeframe is not None else None)
        self.max_age_seconds = _non_negative(max_age_seconds, "INVALID_MAX_AGE")
        self.allowed_future_skew_seconds = _non_negative(allowed_future_skew_seconds, "INVALID_FUTURE_SKEW")
        if self.path.name != "market_state.json":
            raise ValueError("INVALID_MARKET_STATE_PATH")

    def read(self, *, now: float) -> dict[str, Any]:
        if not _finite_number(now):
            raise MarketStateError("CLOCK_INVALID")
        try:
            value = json.loads(self.path.read_text(encoding="utf-8"))
        except FileNotFoundError as error:
            raise MarketStateError("MARKET_STATE_MISSING") from error
        except (OSError, UnicodeDecodeError, json.JSONDecodeError) as error:
            raise MarketStateError("MARKET_STATE_MALFORMED_JSON") from error
        self.validate_schema(value)
        self.validate_identity(value)
        self.validate_heartbeat(value, now=now)
        self.validate_freshness(value, now=now)
        return dict(value)

    @staticmethod
    def validate_schema(value: object) -> None:
        if type(value) is not dict:
            raise MarketStateError("SCHEMA_INVALID_ROOT")
        missing = REQUIRED_MARKET_FIELDS - value.keys()
        if missing:
            raise MarketStateError("SCHEMA_MISSING_FIELDS:" + ",".join(sorted(missing)))
        for field in ("producer", "producer_version", "schema_version", "source_uuid", "symbol", "timeframe"):
            if type(value[field]) is not str or not value[field].strip():
                raise MarketStateError("SCHEMA_INVALID_" + field.upper())
        if type(value["sequence_id"]) is not int or value["sequence_id"] < 0:
            raise MarketStateError("SCHEMA_INVALID_SEQUENCE")
        for field in ("bid", "ask"):
            if not _finite_number(value[field]) or value[field] <= 0:
                raise MarketStateError("SCHEMA_INVALID_" + field.upper())
        if value["ask"] < value["bid"]:
            raise MarketStateError("SCHEMA_INVALID_QUOTE")

    def validate_identity(self, value: Mapping[str, Any]) -> None:
        expected = {"producer": PRODUCER, "producer_version": PRODUCER_VERSION,
                    "schema_version": SCHEMA_VERSION, "source_uuid": SOURCE_UUID}
        for field, wanted in expected.items():
            if value[field] != wanted:
                raise MarketStateError("INCOMPATIBLE_" + field.upper())
        if value["symbol"].upper() != self.expected_symbol:
            raise MarketStateError("SYMBOL_MISMATCH")
        if self.expected_timeframe is not None and value["timeframe"].upper() != self.expected_timeframe:
            raise MarketStateError("TIMEFRAME_MISMATCH")

    def validate_heartbeat(self, value: Mapping[str, Any], *, now: float) -> None:
        heartbeat = value["heartbeat_unix"]
        if not _finite_number(heartbeat) or heartbeat <= 0:
            raise MarketStateError("HEARTBEAT_INVALID")
        if heartbeat - now > self.allowed_future_skew_seconds:
            raise MarketStateError("HEARTBEAT_FUTURE")

    def validate_freshness(self, value: Mapping[str, Any], *, now: float) -> None:
        if now - value["heartbeat_unix"] > self.max_age_seconds:
            raise MarketStateError("MARKET_STATE_STALE")


def _finite_number(value: object) -> bool:
    return type(value) in (int, float) and isfinite(value)


def _non_negative(value: object, code: str) -> float:
    if not _finite_number(value) or value < 0:
        raise ValueError(code)
    return float(value)


def _identifier(value: object, code: str) -> str:
    if type(value) is not str or not value.strip():
        raise ValueError(code)
    return value.strip().upper()
