import uuid
from datetime import datetime, timezone
from ..collector.event_types import TRADE_CLOSED
from ..validation.schema_validator import validate_event
class TradeSnapshotBuilder:
    VERSION = "1.0.0"
    @staticmethod
    def _now(): return datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")
    def build(self, event, related_events=()):
        validate_event(event)
        if event["event_type"] != TRADE_CLOSED: raise ValueError("only TRADE_CLOSED creates snapshots")
        p = event["payload"]
        required = ("trade_id", "symbol", "side", "volume", "entry_price", "exit_price", "gross_profit", "net_profit")
        missing = [key for key in required if (event.get(key) if key in event else p.get(key)) is None]
        if missing: raise ValueError("closed trade evidence missing: " + ", ".join(missing))
        get = lambda k, default=None: p.get(k, event.get(k, default))
        closed, filled = event["occurred_at_utc"], get("filled_at_utc")
        duration = get("duration_seconds")
        if duration is None and filled:
            duration = int((datetime.fromisoformat(closed.replace("Z", "+00:00")) - datetime.fromisoformat(filled.replace("Z", "+00:00"))).total_seconds())
        optional = ("decision_at_utc", "entry_requested_at_utc", "filled_at_utc", "candidate_id", "sequence_id", "bias", "decision", "execution_state", "confidence", "veto_code", "market_mode", "market_state", "session", "atr", "rsi", "macd_histogram", "bb_state", "source_snapshot_timestamp_utc", "requested_price", "spread_points_at_entry", "slippage_points", "profit_points", "r_multiple", "mae_points", "mfe_points", "exit_reason")
        missing_optional = [k for k in optional if get(k) is None]
        ids = [event["event_id"]] + [e["event_id"] for e in related_events]
        return {"schema_version": self.VERSION, "snapshot_id": str(uuid.uuid4()), "created_at_utc": self._now(), "trade_identity": {"trade_id": str(get("trade_id")), "position_id": get("position_id"), "series_id": get("series_id"), "symbol": get("symbol"), "side": get("side"), "volume": get("volume")}, "timeline": {"decision_at_utc": get("decision_at_utc"), "entry_requested_at_utc": get("entry_requested_at_utc"), "filled_at_utc": filled, "closed_at_utc": closed, "duration_seconds": duration}, "decision_context": {"candidate_id": get("candidate_id"), "sequence_id": get("sequence_id"), "bias": get("bias"), "decision": get("decision"), "execution_state": get("execution_state"), "confidence": get("confidence"), "veto_code": get("veto_code"), "reason_codes": get("reason_codes", [])}, "market_context": {k: get(k) for k in ("market_mode", "market_state", "session", "atr", "rsi", "macd_histogram", "bb_state", "source_snapshot_timestamp_utc")}, "execution_context": {"requested_price": get("requested_price"), "entry_price": get("entry_price"), "exit_price": get("exit_price"), "spread_points_at_entry": get("spread_points_at_entry"), "slippage_points": get("slippage_points"), "commission": get("commission", 0.0), "swap": get("swap", 0.0)}, "outcome": {k: get(k) for k in ("gross_profit", "net_profit", "profit_points", "r_multiple", "mae_points", "mfe_points", "exit_reason")}, "data_quality": {"completeness_ratio": round((len(optional)-len(missing_optional))/len(optional), 6), "missing_fields": missing_optional, "warnings": [], "source_event_count": len(ids)}, "provenance": {"source_event_ids": ids, "builder_version": self.VERSION, "snapshot_sha256": ""}}
