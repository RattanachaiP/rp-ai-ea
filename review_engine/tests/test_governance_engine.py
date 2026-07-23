from datetime import datetime, timezone
from hashlib import sha256
import json
import time
from review_engine.governance import (ArchitectureBoundaryMonitor, DataLineageAuditor, GovernanceCoordinator,
                                      GovernanceRepository, PlatformPerformanceMonitor, RepositoryIntegrityMonitor,
                                      SchemaIntegrityMonitor)


def clock(): return datetime(2026, 7, 23, 12, 0, tzinfo=timezone.utc)
def write(path, document): path.parent.mkdir(parents=True, exist_ok=True); path.write_text(json.dumps(document))
def digest(value): return sha256(json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()).hexdigest()
def records(root):
    snapshot = {"schema_version": "2.0.0", "producer": "Snapshot", "owner": "RAIP Snapshot Layer", "created_at": "2026-07-23T12:00:00.000Z", "snapshot_id": "s1", "provenance": {"snapshot_sha256": ""}}
    snapshot["provenance"]["snapshot_sha256"] = digest(snapshot)
    evidence = {"schema_version": "2.0.0", "producer": "Evidence", "owner": "RAIP Evidence Layer", "created_at": "2026-07-23T12:00:00.000Z", "evidence_id": "e1", "snapshot_id": "s1"}
    knowledge = {"schema_version": "3.0.0", "producer": "Knowledge", "owner": "RAIP Knowledge Layer", "created_at": "2026-07-23T12:00:00.000Z", "pattern_repository_version": "k1", "generated_from": {"evidence_lineage": [{"evidence_id": "e1", "snapshot_id": "s1"}]}}
    insight = {"schema_version": "4.0.0", "producer": "Insight", "owner": "RAIP Insight Layer", "created_at": "2026-07-23T12:00:00.000Z", "insight_version": "i1", "knowledge_version": "k1", "lineage": {"evidence": [{"evidence_id": "e1", "snapshot_id": "s1"}]}}
    recommendation = {"schema_version": "5.0.0", "producer": "Recommendation", "owner": "RAIP Recommendation Layer", "created_at": "2026-07-23T12:00:00.000Z", "recommendation_version": "r1", "insight_version": "i1", "recommendations": [{"supporting_insights": ["i1"], "supporting_knowledge": ["k1"], "supporting_evidence": ["e1"], "supporting_snapshots": ["s1"]}]}
    for layer, name, doc in (("snapshots", "s.json", snapshot), ("evidence", "e.json", evidence), ("knowledge", "k.json", knowledge), ("insights", "i.json", insight), ("recommendations", "r.json", recommendation)): write(root / layer / name, doc)


def test_boundary_monitor_detects_prohibited_dependency(tmp_path):
    project = tmp_path / "project"; (project / "review_engine").mkdir(parents=True); (project / "review_engine" / "bad.py").write_text("import runtime.executor\n")
    health = ArchitectureBoundaryMonitor(project, clock=clock).check()
    assert health["status"] == "FAIL" and health["issues"][0]["code"] == "PROHIBITED_DEPENDENCY"

def test_schema_validation_detects_missing_fields(tmp_path):
    records(tmp_path); (tmp_path / "evidence" / "e.json").write_text('{"schema_version":"2.0.0"}')
    assert any(item["code"] == "MISSING_REQUIRED_FIELDS" for item in SchemaIntegrityMonitor(tmp_path, clock=clock).check()["issues"])

def test_repository_integrity_detects_duplicate_and_invalid_hash(tmp_path):
    records(tmp_path); write(tmp_path / "evidence" / "duplicate.json", {"schema_version": "2.0.0", "producer": "E", "owner": "E", "created_at": "x", "evidence_id": "e1", "snapshot_id": "s1"})
    health = RepositoryIntegrityMonitor(tmp_path, clock=clock).check()
    assert {item["code"] for item in health["issues"]} >= {"DUPLICATE_ID"}

def test_lineage_validation_detects_broken_chain(tmp_path):
    records(tmp_path); write(tmp_path / "knowledge" / "k.json", {"schema_version": "3.0.0", "producer": "K", "owner": "K", "created_at": "x", "pattern_repository_version": "k1", "generated_from": {"evidence_lineage": []}})
    assert DataLineageAuditor(tmp_path, clock=clock).check()["status"] == "FAIL"

def test_performance_monitor_collects_metrics(tmp_path):
    records(tmp_path); health = PlatformPerformanceMonitor(tmp_path, clock=clock, metrics_provider=lambda: {"queue_depth": 2, "retry_count": 1}).check(.2)
    assert health["metrics"] == {"processing_latency_ms": 200.0, "queue_depth": 2, "retry_count": 1, "failure_count": 0, "processing_throughput_per_second": 25.0}

def test_governance_aggregation_restart_recovery_and_atomic_write(tmp_path):
    records(tmp_path); coordinator = GovernanceCoordinator(tmp_path, project_root=tmp_path, clock=clock)
    first = coordinator.run(); second = coordinator.run(); coordinator.shutdown()
    history = tmp_path / "governance" / "history" / first["report_id"] / "governance_repository.json"
    assert first == second and first["overall_status"] == "HEALTHY" and history.exists() and not list(tmp_path.rglob("*.tmp"))
    assert GovernanceRepository(tmp_path).save(first) == history

def test_governance_performance_benchmark(tmp_path):
    records(tmp_path); coordinator = GovernanceCoordinator(tmp_path, project_root=tmp_path, clock=clock); started = time.perf_counter(); coordinator.run(); coordinator.shutdown()
    assert time.perf_counter() - started < 1.0
