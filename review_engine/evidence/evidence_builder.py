from __future__ import annotations
from datetime import datetime, timezone
from hashlib import sha256
import json
from typing import Callable, Mapping
from review_engine.classification import TradeClassifier
from review_engine.scoring import ReviewScoringEngine

class EvidenceBuilder:
    SCHEMA_VERSION = "2.0.0"
    def __init__(self, classifier: TradeClassifier | None = None, scoring: ReviewScoringEngine | None = None, *, clock: Callable[[], datetime] | None = None):
        self.classifier, self.scoring = classifier or TradeClassifier(), scoring or ReviewScoringEngine()
        self.clock = clock or (lambda: datetime.now(timezone.utc))
    def build(self, snapshot: Mapping[str, object]) -> dict[str, object]:
        identity = snapshot.get("trade_identity", {}) if isinstance(snapshot.get("trade_identity"), Mapping) else {}
        outcome = snapshot.get("outcome", {}) if isinstance(snapshot.get("outcome"), Mapping) else {}
        decision = snapshot.get("decision_context", {}) if isinstance(snapshot.get("decision_context"), Mapping) else {}
        market = snapshot.get("market_context", {}) if isinstance(snapshot.get("market_context"), Mapping) else {}
        trade_id = str(identity.get("trade_id", ""))
        if not trade_id: raise ValueError("TRADE_ID_REQUIRED")
        snapshot_hash = str((snapshot.get("provenance", {}) if isinstance(snapshot.get("provenance"), Mapping) else {}).get("snapshot_sha256", ""))
        if not snapshot_hash: snapshot_hash = sha256(self._canonical(snapshot)).hexdigest()
        evidence_id = sha256(f"{self.SCHEMA_VERSION}:{trade_id}:{snapshot_hash}".encode()).hexdigest()
        net_profit, rr = self._number(outcome.get("net_profit")), self._number(outcome.get("r_multiple"))
        execution = snapshot.get("execution_context", {}) if isinstance(snapshot.get("execution_context"), Mapping) else {}
        return {"schema_version": self.SCHEMA_VERSION, "producer": "RAIP Review & Evidence Engine", "owner": "RAIP Evidence Layer", "created_at": self._iso(self.clock()), "evidence_id": evidence_id, "trade_id": trade_id, "snapshot_id": snapshot.get("snapshot_id"), "snapshot_sha256": snapshot_hash, "classification": self.classifier.classify(snapshot), "result": "WIN" if net_profit > 0 else "LOSS" if net_profit < 0 else "BREAKEVEN", "win_loss": "WIN" if net_profit > 0 else "LOSS" if net_profit < 0 else "BREAKEVEN", "rr": rr, "net_profit": net_profit, "duration_seconds": self._number(outcome.get("duration_seconds") or outcome.get("duration")), "session": decision.get("session") or market.get("session") or execution.get("session") or "UNKNOWN", "confidence": decision.get("confidence"), "market_state": market.get("market_state") or market.get("market_mode") or "UNKNOWN", "statistics": self.scoring.score(snapshot)}
    @staticmethod
    def _number(value: object) -> float:
        try: return float(value) if value is not None else 0.0
        except (TypeError, ValueError): return 0.0
    @staticmethod
    def _canonical(value: object) -> bytes: return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()
    @staticmethod
    def _iso(value: datetime) -> str: return value.astimezone(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")
