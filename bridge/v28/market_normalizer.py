"""Pure normalization of validated Writer data."""
from __future__ import annotations
from typing import Any, Mapping


def normalize_market_state(market: Mapping[str, Any]) -> dict[str, Any]:
    """Return stable names/types without changing Writer ownership or semantics."""
    bid, ask = float(market["bid"]), float(market["ask"])
    normalized = dict(market)
    normalized.update({
        "symbol": str(market["symbol"]).strip().upper(),
        "timeframe": str(market["timeframe"]).strip().upper(),
        "sequence_id": int(market["sequence_id"]),
        "heartbeat_unix": float(market["heartbeat_unix"]),
        "bid": bid, "ask": ask, "mid": (bid + ask) / 2.0,
        "spread": ask - bid,
    })
    return normalized
