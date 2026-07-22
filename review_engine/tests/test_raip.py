import tempfile, unittest
from pathlib import Path
from review_engine.collector.event_collector import EventCollector
from review_engine.snapshots.trade_snapshot_builder import TradeSnapshotBuilder
from review_engine.snapshots.snapshot_repository import SnapshotRepository
from review_engine.reports.daily_review_builder import DailyReviewBuilder
class RAIPTests(unittest.TestCase):
 def event(self): return {"event_type":"TRADE_CLOSED","occurred_at_utc":"2026-07-22T10:00:00.000Z","source_module":"export","symbol":"XAUUSD","trade_id":"1","payload":{"side":"BUY","volume":0.01,"entry_price":1.0,"exit_price":2.0,"gross_profit":1.0,"net_profit":1.0}}
 def test_closed_idempotent_and_daily(self):
  with tempfile.TemporaryDirectory() as d:
   c=EventCollector(d); r=SnapshotRepository(d); a=c.observe_closed_trade(self.event(),TradeSnapshotBuilder(),r); b=c.observe_closed_trade(self.event(),TradeSnapshotBuilder(),r)
   self.assertTrue(a['snapshot_result']['created']); self.assertTrue(b['snapshot_result']['idempotent']); report=DailyReviewBuilder().build('2026-07-22',r.read_for_date('2026-07-22'),'2026-07-23T00:01:00.000Z'); self.assertEqual(report['performance']['profit_factor'],None)
 def test_invalid_json_quarantined(self):
  with tempfile.TemporaryDirectory() as d: self.assertFalse(EventCollector(d).collect_json('{')['accepted']); self.assertTrue(list((Path(d)/'rejected').rglob('*.json')))
 def test_observer_boundary(self):
  forbidden = ('ordersend', 'positionclose', 'decision_mutation', 'threshold_mutation', 'deploy(')
  package = Path(__file__).parents[1]
  text = '\n'.join(p.read_text(encoding='utf-8').lower() for p in package.rglob('*.py') if 'test_' not in p.name)
  self.assertFalse([term for term in forbidden if term in text])
