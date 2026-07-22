"""Deterministic, factual aggregation of immutable RAIP snapshots."""
from __future__ import annotations
from hashlib import sha256
from typing import Any
from ..collector.event_types import canonical_json
class DailyReviewBuilder:
    version = "1.0.0"
    def build(self, date_utc: str, snapshots: list[dict[str, Any]], generated_at_utc: str) -> dict[str, Any]:
        ordered = sorted(snapshots, key=lambda item: item["snapshot_id"])
        values = [item["outcome"].get("net_profit") for item in ordered]
        numeric = [value for value in values if isinstance(value, (int,float))]
        wins, losses = [v for v in numeric if v > 0], [v for v in numeric if v < 0]
        complete = [s for s in ordered if not s["data_quality"]["missing_fields"]]
        durations = [s["timeline"]["duration_seconds"] for s in ordered if isinstance(s["timeline"]["duration_seconds"], (int,float))]
        missing: dict[str,int] = {}
        for snapshot in ordered:
            for field in snapshot["data_quality"]["missing_fields"]: missing[field] = missing.get(field, 0) + 1
        buys = [s for s in ordered if s["trade_identity"]["side"] == "BUY"]; sells = [s for s in ordered if s["trade_identity"]["side"] == "SELL"]
        report = {"schema_version":"1.0.0","date_utc":date_utc,"generated_at_utc":generated_at_utc,"scope":{"symbols":sorted({s["trade_identity"]["symbol"] for s in ordered}),"trade_count":len(ordered),"complete_snapshot_count":len(complete),"incomplete_snapshot_count":len(ordered)-len(complete)},"performance":{"wins":len(wins),"losses":len(losses),"breakeven":len([v for v in numeric if v == 0]),"win_rate":len(wins)/len(numeric) if numeric else None,"gross_profit":sum((s["outcome"].get("gross_profit") or 0) for s in ordered),"net_profit":sum(numeric),"profit_factor":sum(wins)/abs(sum(losses)) if losses else None,"average_win":sum(wins)/len(wins) if wins else None,"average_loss":sum(losses)/len(losses) if losses else None,"average_duration_seconds":sum(durations)/len(durations) if durations else None},"direction":{"buy_trades":len(buys),"sell_trades":len(sells),"buy_net_profit":sum((s["outcome"].get("net_profit") or 0) for s in buys),"sell_net_profit":sum((s["outcome"].get("net_profit") or 0) for s in sells)},"data_quality":{"average_completeness_ratio":sum(s["data_quality"]["completeness_ratio"] for s in ordered)/len(ordered) if ordered else 0.0,"missing_field_counts":missing,"warnings":[]},"provenance":{"snapshot_ids":[s["snapshot_id"] for s in ordered],"builder_version":self.version,"report_sha256":""}}
        report["provenance"]["report_sha256"] = sha256(canonical_json(report).encode()).hexdigest()
        return report
