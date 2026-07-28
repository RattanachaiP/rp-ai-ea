import json
import pytest
from bridge.v28.market_reader import MarketReader, MarketStateError


def state(**changes):
    value = {"symbol": "XAUUSD", "timeframe": "M1", "heartbeat_unix": 100.0,
             "sequence_id": 7, "bid": 2300.0, "ask": 2300.2}
    value.update(changes); return value


def test_reader_validates_market_state(tmp_path):
    path = tmp_path / "market_state.json"; path.write_text(json.dumps(state()))
    assert MarketReader(path, clock=lambda: 101).read()["sequence_id"] == 7

@pytest.mark.parametrize(("changes", "code"), [
    ({"heartbeat_unix": 90}, "MARKET_STATE_STALE"),
    ({"heartbeat_unix": 104}, "HEARTBEAT_FUTURE"),
    ({"bid": "2300"}, "SCHEMA_INVALID_BID"),
])
def test_reader_fails_closed(tmp_path, changes, code):
    path = tmp_path / "market_state.json"; path.write_text(json.dumps(state(**changes)))
    with pytest.raises(MarketStateError, match=code):
        MarketReader(path, max_age_seconds=5, clock=lambda: 100).read()
