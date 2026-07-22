from datetime import datetime, timezone
import ast
from pathlib import Path
from review_engine.collector.event_collector import EventCollector
from review_engine.collector.trade_source import TradeSource
from review_engine.config import ReviewEngineConfig
from review_engine.snapshots import TradeSnapshotBuilder, SnapshotCoordinator, SnapshotRepository
from review_engine.reports import DailyReviewBuilder
class Source(TradeSource):
 def __init__(self,records):self.records=records;self.calls=0
 def read_events(self):self.calls+=1;return self.records
def clock():return datetime(2026,7,22,10,1,tzinfo=timezone.utc)
def record():return {"event_id":"11111111-1111-4111-8111-111111111111","event_type":"TRADE_CLOSED","occurred_at_utc":"2026-07-22T10:00:00Z","source_module":"export","source_version":"1","symbol":"XAUUSD","trade_id":"42","payload":{"side":"BUY","volume":0.01,"entry_price":1.0,"exit_price":2.0,"commission":-0.1,"swap":0.0,"gross_profit":1.1,"net_profit":1.0,"filled_at_utc":"2026-07-22T09:30:00Z"}}
def test_disabled_performs_no_source_read_or_write(tmp_path):
 source=Source([record()]); result=EventCollector(source,ReviewEngineConfig(review_data_root=tmp_path),clock=clock).collect()
 assert result.disabled and source.calls==0 and not any(tmp_path.iterdir())
def test_snapshot_is_idempotent_and_daily_review_is_deterministic(tmp_path):
 event=EventCollector(Source([record()]),ReviewEngineConfig(enabled=True,review_data_root=tmp_path),clock=clock).normalize(record()); coordinator=SnapshotCoordinator(TradeSnapshotBuilder(clock=clock),SnapshotRepository(tmp_path)); first=coordinator.create_for_closed_trade([event]); second=coordinator.create_for_closed_trade([event]); assert first.created and not second.created and not second.conflict
 a=DailyReviewBuilder(clock=clock).build("2026-07-22",tmp_path); b=DailyReviewBuilder(clock=clock).build("2026-07-22",tmp_path); assert a==b and a["performance"]["profit_factor"] is None
def test_review_engine_has_no_trading_or_publication_imports():
 prohibited={"runtime","bridge","mt5","send_order","close_position","manage_trade","publish"}
 for path in Path("review_engine").rglob("*.py"):
  tree=ast.parse(path.read_text())
  names={node.module.split(".")[0] for node in ast.walk(tree) if isinstance(node,ast.ImportFrom) and node.module} | {alias.name.split(".")[0] for node in ast.walk(tree) if isinstance(node,ast.Import) for alias in node.names}
  assert not names & {"runtime","bridge","mt5"},path
  assert not ({node.name for node in ast.walk(tree) if isinstance(node,(ast.FunctionDef,ast.AsyncFunctionDef))} & prohibited),path
