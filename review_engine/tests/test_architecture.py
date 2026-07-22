import ast
from pathlib import Path
from review_engine.collector import EventCollector, EventQueue, ReplayTradeSource
from review_engine.snapshots import TradeSnapshotBuilder, SnapshotRepository
from review_engine.reports import DailyReviewBuilder

def test_pipeline_is_separated_and_idempotent(tmp_path):
 q=EventQueue(); event=EventCollector(ReplayTradeSource([{'trade_id':'t1','symbol':'XAUUSD','side':'BUY','volume':.01,'entry_price':1.,'exit_price':2.,'net_profit':1.,'gross_profit':1.,'closed_at_utc':'2026-07-22T10:00:00Z'}]),q).collect()[0]
 snap=TradeSnapshotBuilder().build(q.drain()); repo=SnapshotRepository(tmp_path)
 assert repo.store(snap)['status']=='created'; assert repo.store(snap)['status']=='idempotent'
 assert DailyReviewBuilder().build('2026-07-22',[snap])['performance']['net_profit']==1

def test_no_trading_dependencies():
 root=Path(__file__).parents[1]
 forbidden=('bridge', 'runtime', 'executor', 'mt5', 'order_manager', 'broker_safety')
 imported=[]
 for path in root.rglob('*.py'):
  if 'tests' in path.parts: continue
  tree=ast.parse(path.read_text())
  for node in ast.walk(tree):
   if isinstance(node, ast.Import): imported.extend(name.name.lower() for name in node.names)
   if isinstance(node, ast.ImportFrom) and node.module: imported.append(node.module.lower())
 assert not [name for name in imported if any(word in name for word in forbidden)]
