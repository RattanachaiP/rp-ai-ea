from datetime import datetime, timezone
from hashlib import sha256
from pathlib import Path
from uuid import uuid4
from review_engine import ReviewEngineConfig
from review_engine.collector import EventCollector
from review_engine.collector.event_types import canonical_json
from review_engine.snapshots import TradeSnapshotBuilder, SnapshotRepository, SnapshotConflictError
from review_engine.reports import DailyReviewBuilder
NOW = datetime(2026, 7, 22, 10, 1, tzinfo=timezone.utc)
def event(kind="TRADE_CLOSED", payload=None):
    payload = payload or {"side":"BUY", "volume":0.01, "entry_price":2300.0, "exit_price":2301.0, "gross_profit":1.0, "commission":-0.1, "swap":0.0}
    return {"schema_version":"1.0.0", "event_id":str(uuid4()), "event_type":kind, "occurred_at_utc":"2026-07-22T10:00:00Z", "observed_at_utc":"2026-07-22T10:00:00Z", "source_module":"export", "source_version":"unknown", "symbol":"XAUUSD", "account_id_hash":None, "trade_id":"42", "position_id":None, "series_id":None, "candidate_id":None, "sequence_id":None, "correlation_id":None, "payload":payload, "integrity":{"payload_sha256":sha256(canonical_json(payload).encode()).hexdigest()}}
def test_event_append_and_invalid_quarantine(tmp_path):
    config = ReviewEngineConfig(enabled=True, review_data_root=tmp_path)
    assert EventCollector(config, clock=lambda: NOW).record(event())
    assert not EventCollector(config, clock=lambda: NOW).record({})
    assert len(list((tmp_path / "rejected").rglob("*.json"))) == 1
    assert len((tmp_path / "events/2026/07/22/events.jsonl").read_text().splitlines()) == 1
def test_snapshot_immutable_idempotency_and_daily_determinism(tmp_path):
    snapshot = TradeSnapshotBuilder(clock=lambda: NOW).build([event()])
    repo = SnapshotRepository(tmp_path)
    assert repo.store(snapshot) and not repo.store(snapshot)
    altered = dict(snapshot); altered["snapshot_id"] = "changed"
    try: repo.store(altered)
    except SnapshotConflictError: pass
    else: assert False
    a = DailyReviewBuilder().build("2026-07-22", [snapshot], "2026-07-23T00:01:00.000Z")
    b = DailyReviewBuilder().build("2026-07-22", [snapshot], "2026-07-23T00:01:00.000Z")
    assert a == b and a["performance"]["net_profit"] == 0.9
def test_observer_package_has_no_execution_authority():
    source = "\n".join(path.read_text() for path in Path("review_engine").rglob("*.py"))
    for forbidden in ("OrderSend", "position_close", "cancel_order", "decision_mutation"): assert forbidden not in source
