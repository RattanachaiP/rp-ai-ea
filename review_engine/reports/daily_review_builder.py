"""Factual, deterministic aggregation of immutable RAIP snapshots."""
from __future__ import annotations
from hashlib import sha256
from typing import Any, Iterable, Mapping
from review_engine.snapshots.snapshot_repository import canonical_json

class DailyReviewBuilder:
    VERSION = "1.0.0"
    def build(self, date_utc: str, snapshots: Iterable[Mapping[str, Any]], generated_at_utc: str) -> dict[str, Any]:
        rows = sorted(snapshots, key=lambda s: s["snapshot_id"]); profits = [s["outcome"]["net_profit"] for s in rows]
        wins, losses = [p for p in profits if p > 0], [p for p in profits if p < 0]
        missing: dict[str, int] = {}
        for row in rows:
            for field in row["data_quality"]["missing_fields"]: missing[field] = missing.get(field, 0) + 1
        side = lambda label: [s for s in rows if s["trade_identity"]["side"] == label]
        buy, sell = side("BUY"), side("SELL")
        complete = [s for s in rows if not s["data_quality"]["missing_fields"]]
        report = {"schema_version":"1.0.0", "date_utc":date_utc, "generated_at_utc":generated_at_utc, "scope":{"symbols":sorted({s["trade_identity"]["symbol"] for s in rows}),"trade_count":len(rows),"complete_snapshot_count":len(complete),"incomplete_snapshot_count":len(rows)-len(complete)}, "performance":{"wins":len(wins),"losses":len(losses),"breakeven":len(rows)-len(wins)-len(losses),"win_rate":round(len(wins)/len(rows), 6) if rows else None,"gross_profit":sum(s["outcome"]["gross_profit"] for s in rows),"net_profit":sum(profits),"profit_factor":round(sum(wins)/abs(sum(losses)), 6) if losses else None,"average_win":sum(wins)/len(wins) if wins else None,"average_loss":sum(losses)/len(losses) if losses else None,"average_duration_seconds":sum(s["timeline"]["duration_seconds"] for s in rows if s["timeline"]["duration_seconds"] is not None) / sum(s["timeline"]["duration_seconds"] is not None for s in rows) if any(s["timeline"]["duration_seconds"] is not None for s in rows) else None}, "direction":{"buy_trades":len(buy),"sell_trades":len(sell),"buy_net_profit":sum(s["outcome"]["net_profit"] for s in buy),"sell_net_profit":sum(s["outcome"]["net_profit"] for s in sell)}, "data_quality":{"average_completeness_ratio":sum(s["data_quality"]["completeness_ratio"] for s in rows)/len(rows) if rows else 0.0,"missing_field_counts":missing,"warnings":[]}, "provenance":{"snapshot_ids":[s["snapshot_id"] for s in rows],"builder_version":self.VERSION,"report_sha256":""}}
        report["provenance"]["report_sha256"] = sha256(canonical_json(report)).hexdigest(); return report
