import json
from review_engine.collector import EventCollector, make_event
from review_engine.snapshots import SnapshotRepository, TradeSnapshotBuilder
from review_engine.reports import DailyReviewBuilder

def closed():
    return make_event("TRADE_CLOSED", {"side":"BUY","volume":0.01,"filled_at_utc":"2026-07-22T09:30:00.000Z","entry_price":1.0,"exit_price":2.0,"gross_profit":3.0,"net_profit":3.0}, occurred_at_utc="2026-07-22T10:00:00.000Z", trade_id="T1", symbol="XAUUSD")
def test_closed_event_snapshot_is_idempotent_and_atomic(tmp_path):
    event=closed(); assert EventCollector(tmp_path).collect(event)["accepted"]
    snapshot=TradeSnapshotBuilder().build(event); repo=SnapshotRepository(tmp_path)
    assert repo.store(snapshot)["created"]
    assert not list(tmp_path.rglob("*.tmp"))
    # Repository prohibits contradictory duplicate trade identity.
    snapshot["outcome"]["net_profit"]=4
    assert repo.store(snapshot)["conflict"]
def test_invalid_event_is_quarantined(tmp_path):
    result=EventCollector(tmp_path).collect({"broken":True})
    assert not result["accepted"] and "reason" in json.loads(open(result["path"]).read())
def test_daily_report_is_deterministic_and_handles_zero_loss_denominator():
    snapshot=TradeSnapshotBuilder().build(closed())
    a=DailyReviewBuilder().build("2026-07-22",[snapshot]); b=DailyReviewBuilder().build("2026-07-22",[snapshot])
    for report in (a,b): report["generated_at_utc"]="fixed"; report["provenance"]["report_sha256"]="fixed"
    assert a == b and a["performance"]["profit_factor"] is None
def test_observer_boundary_has_no_trading_authority():
    from pathlib import Path
    source="\n".join(p.read_text() for p in Path("review_engine").rglob("*.py") if "tests" not in p.parts)
    for forbidden in ("OrderSend", "position_close", "decision_mutation", "threshold_mutation", "deploy("):
        assert forbidden not in source
