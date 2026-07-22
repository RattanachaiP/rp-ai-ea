"""Deterministic, read-only classification of immutable trade snapshots."""
from __future__ import annotations
from typing import Mapping

SUPPORTED_CLASSIFICATIONS = ("TREND", "RANGE", "BREAKOUT", "PULLBACK", "CONTINUATION", "REVERSAL", "NEWS", "UNKNOWN")

class TradeClassifier:
    """Classifies only explicit snapshot context; it never infers or mutates data."""
    def classify(self, snapshot: Mapping[str, object]) -> str:
        market = snapshot.get("market_context", {})
        decision = snapshot.get("decision_context", {})
        values = [
            market.get("market_state") if isinstance(market, Mapping) else None,
            market.get("market_mode") if isinstance(market, Mapping) else None,
            decision.get("decision") if isinstance(decision, Mapping) else None,
            *(decision.get("reason_codes", []) if isinstance(decision, Mapping) and isinstance(decision.get("reason_codes"), list) else []),
        ]
        tokens = {str(value).upper().replace("-", "_").replace(" ", "_") for value in values if value is not None}
        for label in ("NEWS", "REVERSAL", "BREAKOUT", "PULLBACK", "CONTINUATION", "RANGE", "TREND"):
            if label in tokens or any(label in token for token in tokens):
                return label
        return "UNKNOWN"
