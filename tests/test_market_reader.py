import json
import pytest
from bridge.v28.market_reader import MarketReader, MarketStateError, PRODUCER, PRODUCER_VERSION, SCHEMA_VERSION, SOURCE_UUID


def state(**changes):
    value = {"producer": PRODUCER, "producer_version": PRODUCER_VERSION, "schema_version": SCHEMA_VERSION,
             "source_uuid": SOURCE_UUID, "symbol": "XAUUSD", "timeframe": "M1", "heartbeat_unix": 100.0,
             "sequence_id": 7, "bid": 2300.0, "ask": 2300.2, "nested": {"ticks": [1, 2]}}
    value.update(changes); return value


def write(tmp_path, value):
    path = tmp_path / "market_state.json"; path.write_text(json.dumps(value)); return path


def test_reader_validates_authoritative_contract(tmp_path):
    assert MarketReader(write(tmp_path, state()), expected_timeframe="M1").read(now=101)["sequence_id"] == 7

@pytest.mark.parametrize(("changes", "code"), [
    ({"heartbeat_unix": 94.999}, "MARKET_STATE_STALE"), ({"heartbeat_unix": 102.001}, "HEARTBEAT_FUTURE"),
    ({"bid": "2300"}, "SCHEMA_INVALID_BID"), ({"symbol": "EURUSD"}, "SYMBOL_MISMATCH"),
    ({"schema_version": "2.0"}, "INCOMPATIBLE_SCHEMA_VERSION"), ({"producer": "OTHER"}, "INCOMPATIBLE_PRODUCER"),
])
def test_reader_fails_closed(tmp_path, changes, code):
    with pytest.raises(MarketStateError, match=code):
        MarketReader(write(tmp_path, state(**changes)), max_age_seconds=5).read(now=100)


def test_freshness_and_future_boundaries_are_inclusive(tmp_path):
    assert MarketReader(write(tmp_path, state(heartbeat_unix=95)), max_age_seconds=5).read(now=100)
    assert MarketReader(write(tmp_path, state(heartbeat_unix=102))).read(now=100)
