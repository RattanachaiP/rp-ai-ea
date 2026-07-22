from datetime import datetime, timezone
import json
from review_engine.classification import TradeClassifier
from review_engine.evidence import EvidenceBuilder, EvidenceCoordinator, EvidenceRepository
from review_engine.intelligence import DailyIntelligenceGenerator, DailyIntelligenceRepository
from review_engine.scoring import ReviewScoringEngine

def clock(): return datetime(2026, 7, 22, 12, 0, tzinfo=timezone.utc)
def snapshot():
 return {"snapshot_id":"s-1","created_at_utc":"2026-07-22T10:00:00Z","trade_identity":{"trade_id":"42","side":"BUY","symbol":"XAUUSD"},"decision_context":{"confidence":0.8,"reason_codes":["TREND"]},"market_context":{"market_state":"TREND"},"execution_context":{"spread_points_at_entry":1,"slippage_points":0.5},"outcome":{"net_profit":2,"r_multiple":1.5,"mae_points":3,"mfe_points":9},"data_quality":{"completeness_ratio":1},"provenance":{"snapshot_sha256":"a" * 64}}
def test_classification_consistency():
 classifier = TradeClassifier(); item = snapshot()
 assert classifier.classify(item) == "TREND" == classifier.classify(item)
def test_score_reproducibility():
 engine = ReviewScoringEngine(); assert engine.score(snapshot()) == engine.score(json.loads(json.dumps(snapshot())))
def test_evidence_integrity_and_duplicate_prevention(tmp_path):
 builder = EvidenceBuilder(clock=clock); evidence = builder.build(snapshot())
 assert evidence["trade_id"] == "42" and len(evidence["evidence_id"]) == 64 and evidence["producer"] == "RAIP Review & Evidence Engine"
 repo = EvidenceRepository(tmp_path); first, second = repo.save(evidence), repo.save(evidence)
 assert first.created and not second.created and first.path.read_text().endswith("\n")
def test_restart_recovery_and_atomic_write(tmp_path):
 coordinator = EvidenceCoordinator(EvidenceBuilder(clock=clock), EvidenceRepository(tmp_path))
 first = coordinator.create_for_snapshot(snapshot()); assert first.created and not list(first.path.parent.glob("*.tmp"))
 restarted = EvidenceCoordinator(EvidenceBuilder(clock=clock), EvidenceRepository(tmp_path))
 assert not restarted.create_for_snapshot(snapshot()).created
def test_daily_intelligence_is_stable_and_atomic(tmp_path):
 evidence = EvidenceBuilder(clock=clock).build(snapshot()); generator = DailyIntelligenceGenerator(clock=clock)
 first = generator.generate([evidence], "2026-07-22"); second = generator.generate([evidence], "2026-07-22")
 assert first == second and first["trade_count"] == 1 and first["entry_score"] is not None
 path = DailyIntelligenceRepository(tmp_path).write("2026-07-22", first)
 assert path.name == "daily_intelligence.json" and not list(path.parent.glob("*.tmp"))
def test_processing_overhead_is_bounded():
 import time
 builder = EvidenceBuilder(clock=clock); start = time.perf_counter()
 for _ in range(1000): builder.build(snapshot())
 assert time.perf_counter() - start < 1.0
