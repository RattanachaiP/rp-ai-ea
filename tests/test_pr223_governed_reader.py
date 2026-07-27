"""PR223 contract tests derived from the canonical V14 Writer source."""

import inspect
import json
from pathlib import Path
import re
import sys
from types import SimpleNamespace

import pytest

sys.path.insert(0, str(Path(__file__).parents[1]))

from runtime.execution_package_bootstrap import ExecutionPackageRuntimeBootstrap
from runtime.market_state_reader import (
    GovernedMarketStateReader, MarketStateReaderError, PRODUCER,
    PRODUCER_VERSION, SCHEMA_VERSION, SOURCE_UUID,
)


WRITER = Path("mt5/canonical/RP_Market_State_Writer_V14_TIME_SYNC_STANDARD_V1_COMPILE_FIX.mq5")
NOW = 2_000_000_000


def _writer_source():
    return WRITER.read_text(encoding="utf-8")


def _define(name):
    match = re.search(rf'^#define\s+{name}\s+"([^"]+)"$', _writer_source(), re.MULTILINE)
    assert match
    return match.group(1)


def writer_compatible_payload(**changes):
    """Values and types emitted by the actual Writer JSON construction block."""
    values = {
        "producer": _define("MARKET_STATE_PRODUCER"),
        "producer_version": _define("MARKET_STATE_PRODUCER_VERSION"),
        "schema_version": _define("MARKET_STATE_SCHEMA_VERSION"),
        "source_uuid": _define("MARKET_STATE_SOURCE_UUID"),
        "symbol": "XAUUSD", "timeframe": "M5",
        "time_sync": "RP_TIME_SYNC_STANDARD_V1", "heartbeat_unix": NOW,
        "sequence_id": 10, "server_time": "2033.05.18 03:33:20",
        "bar_time": "2033.05.18 03:30:00", "bid": 2000.1, "ask": 2000.2,
        "spread_points": 10.0, "market_session_quality": 1.0,
        "slippage_expectation": 0.1, "market_liquidity_quality": 1.0,
        "telemetry_policy_uuid": "684556d1-439c-5d73-8622-da5ae1566915",
        "telemetry_policy_digest": "ba6636d510f80e8b4c3ff17d47b046bc852552b2315238516467c5a251ab6e1c",
        "telemetry_policy_version": "RP_MT5_MODELED_TELEMETRY_V2",
        "telemetry_source_provenance": "MT5_SYMBOL_TRADE_MODE_AND_LIVE_TICK_STREAM",
        "ma50": 1.0, "ma90": 1.0, "ma200": 1.0, "rsi": 50.0,
        "macd_main": 0.1, "macd_signal": 0.1, "macd_hist": 0.0,
        "bb_upper": 2.0, "bb_middle": 1.0, "bb_lower": 0.0,
        "bb3_upper": 3.0, "bb3_middle": 1.0, "bb3_lower": -1.0,
        "bb4_upper": 4.0, "bb4_middle": 1.0, "bb4_lower": -2.0,
        "buyScore": 2, "sellScore": 1,
    }
    values.update(changes)
    return values


def publish(path, values=None):
    path.write_text(json.dumps(values or writer_compatible_payload()), encoding="utf-8")


def test_contract_and_identity_are_derived_from_canonical_writer(tmp_path):
    source = _writer_source()
    assert (PRODUCER, PRODUCER_VERSION, SCHEMA_VERSION, SOURCE_UUID) == (
        _define("MARKET_STATE_PRODUCER"), _define("MARKET_STATE_PRODUCER_VERSION"),
        _define("MARKET_STATE_SCHEMA_VERSION"), _define("MARKET_STATE_SOURCE_UUID"))
    assert "long heartbeatUnix = (long)now;" in source
    assert '"heartbeat_unix\\\": " + IntegerToString(heartbeatUnix)' in source
    path = tmp_path / "market_state.json"
    publish(path)
    state = GovernedMarketStateReader(clock=lambda: NOW).read(path)
    assert state.sequence_id == 10 and type(state.values["heartbeat_unix"]) is int


@pytest.mark.parametrize(("change", "reason"), (
    ({"producer": "OTHER"}, "UNKNOWN_PRODUCER"),
    ({"producer_version": "V2"}, "UNSUPPORTED_PRODUCER_VERSION"),
    ({"schema_version": "2.0"}, "UNSUPPORTED_SCHEMA_VERSION"),
    ({"source_uuid": "00000000-0000-4000-8000-000000000000"}, "UNKNOWN_SOURCE_UUID"),
    ({"heartbeat_unix": NOW - 31}, "STALE_HEARTBEAT"),
    ({"heartbeat_unix": NOW + 3}, "FUTURE_HEARTBEAT"),
))
def test_identity_and_freshness_fail_closed(tmp_path, change, reason):
    path = tmp_path / "market_state.json"
    publish(path, writer_compatible_payload(**change))
    reader = GovernedMarketStateReader(clock=lambda: NOW)
    with pytest.raises(MarketStateReaderError, match=reason):
        reader.read(path)
    assert reader.last_diagnostic.status == "REJECTED"


def test_allowed_future_clock_skew_is_accepted(tmp_path):
    path = tmp_path / "market_state.json"
    publish(path, writer_compatible_payload(heartbeat_unix=NOW + 2))
    assert GovernedMarketStateReader(clock=lambda: NOW).read(path).sequence_id == 10


@pytest.mark.parametrize(("contents", "reason"), (
    (b"\xff", "INVALID_UTF8"),
    (b'{"producer":', "INVALID_OR_PARTIAL_JSON"),
))
def test_corrupt_publication_is_rejected(tmp_path, contents, reason):
    path = tmp_path / "market_state.json"
    path.write_bytes(contents)
    with pytest.raises(MarketStateReaderError, match=reason):
        GovernedMarketStateReader(clock=lambda: NOW).read(path)


def test_missing_required_field_and_unrelated_heartbeat_types_are_rejected(tmp_path):
    path = tmp_path / "market_state.json"
    values = writer_compatible_payload()
    values.pop("symbol")
    publish(path, values)
    with pytest.raises(MarketStateReaderError, match="MISSING_REQUIRED_FIELDS:symbol"):
        GovernedMarketStateReader(clock=lambda: NOW).read(path)
    for invalid in (True, float(NOW), str(NOW)):
        publish(path, writer_compatible_payload(heartbeat_unix=invalid))
        with pytest.raises(MarketStateReaderError, match="INVALID_JSON_SCHEMA"):
            GovernedMarketStateReader(clock=lambda: NOW).read(path)


def test_sequence_rollback_and_duplicate_are_distinct_failures(tmp_path):
    path = tmp_path / "market_state.json"
    reader = GovernedMarketStateReader(clock=lambda: NOW)
    publish(path)
    reader.read(path)
    publish(path)
    with pytest.raises(MarketStateReaderError, match="DUPLICATE_SEQUENCE"):
        reader.read(path)
    publish(path, writer_compatible_payload(sequence_id=9))
    with pytest.raises(MarketStateReaderError, match="SEQUENCE_ROLLBACK"):
        reader.read(path)


def test_path_replacement_during_read_is_rejected(tmp_path, monkeypatch):
    path = tmp_path / "market_state.json"
    publish(path)
    actual_stat = Path.stat

    def replaced(candidate, *args, **kwargs):
        result = actual_stat(candidate, *args, **kwargs)
        if candidate == path:
            return SimpleNamespace(st_dev=result.st_dev, st_ino=result.st_ino + 1)
        return result

    monkeypatch.setattr(Path, "stat", replaced)
    with pytest.raises(MarketStateReaderError, match="PUBLICATION_CHANGED_DURING_READ"):
        GovernedMarketStateReader(clock=lambda: NOW).read(path)


def test_failure_returns_no_stale_validated_state(tmp_path):
    path = tmp_path / "market_state.json"
    reader = GovernedMarketStateReader(clock=lambda: NOW)
    accepted = reader.read(path) if path.exists() else None
    assert accepted is None
    publish(path)
    accepted = reader.read(path)
    path.write_bytes(b"{")
    with pytest.raises(MarketStateReaderError):
        reader.read(path)
    assert accepted.sequence_id == 10
    assert reader.last_diagnostic.status == "REJECTED"
    assert not hasattr(reader, "last_validated_state")


def test_runtime_package_wiring_has_no_package_or_execution_authority():
    source = inspect.getsource(ExecutionPackageRuntimeBootstrap)
    assert "GovernedExecutionPackageAssemblyEngine" in source
    assert "ExecutionPackageConsumer" in source
    assert all(token not in source for token in (
        "order_send", "OrderSend", "broker", "position", "def trade", "def execute"))
