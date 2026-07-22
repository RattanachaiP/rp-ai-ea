import json
from pathlib import Path
from review_engine.collector.event_collector import EventCollector
from review_engine.snapshots.snapshot_repository import SnapshotRepository
from review_engine.snapshots.trade_snapshot_builder import TradeSnapshotBuilder
from review_engine.reports.daily_review_builder import DailyReviewBuilder

def source(kind, at, **payload):
    return {"event_type":kind,"occurred_at_utc":at,"observed_at_utc":at,"source_module":"closed_trade_export","symbol":"XAUUSD","trade_id":"T-1","position_id":"P-1","payload":payload}

def test_closed_event_snapshot_is_immutable_and_idempotent(tmp_path):
    repo, collector = SnapshotRepository(tmp_path), EventCollector(SnapshotRepository(tmp_path))
    events = [collector.collect(source("ORDER_FILL_OBSERVED", "2026-07-22T09:30:00.000Z", side="BUY", volume=.01, entry_price=3300.0)), collector.collect(source("TRADE_CLOSED", "2026-07-22T10:00:00.000Z", side="BUY", volume=.01, entry_price=3300.0, exit_price=3301.0, gross_profit=1.2, net_profit=1.0, commission=-.2, swap=0.0))]
    snapshot = TradeSnapshotBuilder().build(events)
    path, created = repo.store_snapshot(snapshot); assert not created and path.exists()
    assert repo.store_snapshot(snapshot) == (path, False)
    assert collector.collect(source("TRADE_CLOSED", "2026-07-22T10:00:00.000Z", side="BUY", volume=.01, entry_price=3300.0, exit_price=3301.0, gross_profit=1.2, net_profit=1.0, commission=-.2, swap=0.0)) is not None

def test_missing_optional_evidence_and_invalid_json_are_isolated(tmp_path):
    repo = SnapshotRepository(tmp_path); collector = EventCollector(repo)
    assert collector.collect("not-json") is None
    assert list((tmp_path / "rejected").rglob("*.json"))
    event = collector.collect(source("TRADE_CLOSED", "2026-07-22T10:00:00.000Z", side="SELL", volume=.01, gross_profit=0.0, net_profit=0.0))
    snapshot = TradeSnapshotBuilder().build([event]); assert snapshot["market_context"]["rsi"] is None
    assert "market_mode" in snapshot["data_quality"]["missing_fields"]

def test_daily_report_is_deterministic_and_handles_zero_loss(tmp_path):
    repo = SnapshotRepository(tmp_path); collector = EventCollector(repo)
    event = collector.collect(source("TRADE_CLOSED", "2026-07-22T10:00:00.000Z", side="BUY", volume=.01, gross_profit=1.0, net_profit=1.0))
    snapshot = TradeSnapshotBuilder().build([event]); repo.store_snapshot(snapshot)
    builder = DailyReviewBuilder(); rows = repo.load_snapshots("2026-07-22")
    one = builder.build("2026-07-22", rows, "2026-07-23T00:01:00.000Z"); two = builder.build("2026-07-22", rows, "2026-07-23T00:01:00.000Z")
    assert one == two and one["performance"]["profit_factor"] is None

def test_no_trading_path_imports_or_mutators():
    package = Path(__file__).parents[1]
    forbidden = ("MetaTrader", "OrderSend", "PositionClose", "decision.json", "threshold", "deploy")
    text = "\n".join(p.read_text() for p in package.rglob("*.py") if "tests" not in p.parts)
    assert not any(word in text for word in forbidden)
