"""PR248 end-to-end operator composition acceptance tests."""
from pathlib import Path
import sys

import pytest

sys.path.insert(0, str(Path(__file__).parent))
from learning.bootstrap.operator_bootstrap import BootstrapError, construct, inspect, plan, verify
from learning.knowledge_registry import KnowledgeRegistryRepository
from learning.decision_intelligence import DecisionIntelligenceRepository
from learning.decision_intelligence.operator_activation import commit_activation
from test_pr180_runtime_knowledge import registry_report


def test_empty_fresh_install_inspection_and_plan_are_non_mutating(tmp_path):
    base = tmp_path / "learning_data"
    before = tuple(tmp_path.rglob("*"))
    status = inspect(base)
    proposed = plan(base)
    checked = verify(base)
    assert tuple(tmp_path.rglob("*")) == before
    assert status["mutation_occurred"] is proposed["mutation_occurred"] is checked["mutation_occurred"] is False
    assert status["stages"][0]["missing_dependency"] == "EXTERNAL_APPROVED_PR173_PR175_EVIDENCE"
    assert "acquire governed external outcome evidence" in status["next_required_operator_action"]


def test_missing_exact_source_fails_before_target_creation(tmp_path):
    base = tmp_path / "learning_data"
    with pytest.raises(BootstrapError, match="UPSTREAM_SNAPSHOT_REQUIRED.*mutation_occurred=false"):
        construct(base, "pr180", "00000000-0000-0000-0000-000000000000")
    assert not base.exists()


def test_exact_chain_construct_replay_resume_and_verify(tmp_path):
    base = tmp_path / "learning_data"
    report, source = registry_report(base)
    (base / "registry").rename(base / "knowledge_registry")
    source = KnowledgeRegistryRepository(base / "knowledge_registry")
    source_uuid = source.latest_snapshot().snapshot_uuid
    results = []
    for stage in ("pr180", "pr181", "pr182", "pr183", "pr184"):
        result = construct(base, stage, source_uuid)
        results.append(result)
        source_uuid = result["result_snapshot_uuid"]
    canonical = {p: p.read_bytes() for p in base.rglob("*.json")}
    source_uuid = source.latest_snapshot().snapshot_uuid
    replay = []
    for stage in ("pr180", "pr181", "pr182", "pr183", "pr184"):
        result = construct(base, stage, source_uuid)
        replay.append(result)
        source_uuid = result["result_snapshot_uuid"]
    assert [x["result_snapshot_uuid"] for x in results] == [x["result_snapshot_uuid"] for x in replay]
    assert {p: p.read_bytes() for p in base.rglob("*.json")} == canonical
    checked = verify(base)
    assert checked["learning_chain_ready"] is True
    assert checked["activation_status"] == "ACTIVATION_REQUIRED"
    assert checked["blocked_before_activation"] is True
    assert checked["production_ready"] is False
    assert not (base / "decision_intelligence" / "activation").exists()


def test_duplicate_replay_reports_no_canonical_mutation(tmp_path):
    base = tmp_path / "learning_data"
    _, source = registry_report(base)
    (base / "registry").rename(base / "knowledge_registry")
    source = KnowledgeRegistryRepository(base / "knowledge_registry")
    first = construct(base, "pr180", source.latest_snapshot().snapshot_uuid)
    replay = construct(base, "pr180", source.latest_snapshot().snapshot_uuid)
    assert first["mutation_occurred"] is True
    assert replay["mutation_occurred"] is False
    assert replay["duplicate_replay"] is True
    assert replay["constructed_record_uuids"] == first["constructed_record_uuids"]
    assert replay["result_snapshot_uuid"] == first["result_snapshot_uuid"]


def test_multi_record_pr179_snapshot_is_one_complete_pr180_operation(tmp_path):
    base = tmp_path / "learning_data"
    registry_report(base)
    registry_report(base)
    (base / "registry").rename(base / "knowledge_registry")
    source = KnowledgeRegistryRepository(base / "knowledge_registry")
    snapshot = source.latest_snapshot()
    assert len(snapshot.record_identities) == 2
    result = construct(base, "pr180", snapshot.snapshot_uuid)
    assert set(result["constructed_record_uuids"])
    assert len(result["constructed_record_uuids"]) == 2
    assert len(result["new_record_uuids"]) == 2


def test_exact_older_source_ignores_unrelated_later_upstream_snapshot(tmp_path):
    base = tmp_path / "learning_data"
    _, source = registry_report(base)
    older_uuid = source.latest_snapshot().snapshot_uuid
    registry_report(base)
    (base / "registry").rename(base / "knowledge_registry")
    source = KnowledgeRegistryRepository(base / "knowledge_registry")
    assert source.latest_snapshot().snapshot_uuid != older_uuid
    result = construct(base, "pr180", older_uuid)
    assert len(result["constructed_record_uuids"]) == 1
    snapshot = next(x for x in __import__("learning.runtime_knowledge", fromlist=["RuntimeKnowledgeRepository"]).RuntimeKnowledgeRepository(base / "runtime_knowledge").snapshots()
                    if x.snapshot_uuid == result["result_snapshot_uuid"])
    assert snapshot.source_registry_snapshot_uuid == older_uuid


def _ready_chain(base):
    _, source = registry_report(base)
    (base / "registry").rename(base / "knowledge_registry")
    source = KnowledgeRegistryRepository(base / "knowledge_registry")
    source_uuid = source.latest_snapshot().snapshot_uuid
    for stage in ("pr180", "pr181", "pr182", "pr183", "pr184"):
        result = construct(base, stage, source_uuid)
        source_uuid = result["result_snapshot_uuid"]
    return result


def test_verify_missing_invalid_and_valid_activation_is_read_only(tmp_path):
    base = tmp_path / "learning_data"
    result = _ready_chain(base)
    before = {p: p.read_bytes() for p in base.rglob("*") if p.is_file()}
    missing = verify(base)
    assert missing["learning_chain_ready"] is True
    assert missing["production_ready"] is False
    assert missing["activation_status"] == "ACTIVATION_REQUIRED"
    assert {p: p.read_bytes() for p in base.rglob("*") if p.is_file()} == before

    repository = DecisionIntelligenceRepository(base / "decision_intelligence")
    intelligence = repository.records()[0]
    snapshot = next(x for x in repository.snapshots() if x.snapshot_uuid == result["result_snapshot_uuid"])
    commit_activation(repository_root=repository.root, intelligence_uuid=intelligence.intelligence_uuid,
                      snapshot_uuid=snapshot.snapshot_uuid,
                      authority_owner="PR184_DECISION_INTELLIGENCE_OWNER",
                      activated_at=intelligence.created_at)
    valid_before = {p: p.read_bytes() for p in base.rglob("*") if p.is_file()}
    observations = (("feed_stability", .99), ("price_stream_continuity", .999),
                    ("market_session_quality", .9), ("spread_quality", 20.0),
                    ("latency_quality", 100.0), ("slippage_expectation", 10.0),
                    ("market_liquidity_quality", .9), ("environment_consistency", .9),
                    ("data_freshness", 2.0), ("environment_completeness", .95))
    valid = verify(base, observations, intelligence.created_at)
    assert valid["activation_status"] == "VALID"
    assert valid["production_ready"] is True
    assert valid["activated_pair"] == {"intelligence_uuid": intelligence.intelligence_uuid,
                                        "snapshot_uuid": snapshot.snapshot_uuid}
    assert {p: p.read_bytes() for p in base.rglob("*") if p.is_file()} == valid_before

    path = next(repository.activation_root.glob("*.json"))
    path.write_text("{}")
    invalid_before = path.read_bytes()
    invalid = verify(base)
    assert invalid["production_ready"] is False
    assert invalid["activation_status"].startswith("INVALID:")
    assert path.read_bytes() == invalid_before


def test_exact_result_does_not_depend_on_unrelated_snapshot_order(tmp_path, monkeypatch):
    base = tmp_path / "learning_data"
    _, source = registry_report(base)
    (base / "registry").rename(base / "knowledge_registry")
    source = KnowledgeRegistryRepository(base / "knowledge_registry")
    source_uuid = source.latest_snapshot().snapshot_uuid
    first = construct(base, "pr180", source_uuid)
    repository = __import__("learning.runtime_knowledge", fromlist=["RuntimeKnowledgeRepository"]).RuntimeKnowledgeRepository(base / "runtime_knowledge")
    original = repository.snapshots
    monkeypatch.setattr(type(repository), "snapshots", lambda self: tuple(reversed(original())))
    replay = construct(base, "pr180", source_uuid)
    assert replay["result_snapshot_uuid"] == first["result_snapshot_uuid"]
    assert replay["result_snapshot_digest"] == first["result_snapshot_digest"]


def test_guidance_is_powershell_safe_and_never_selects_latest_for_mutation(tmp_path):
    proposed = plan(tmp_path / "learning_data")
    text = "\n".join(proposed["commands"])
    assert "$SnapshotUuid" in text
    assert "<EXACT_UUID>" not in text
    assert "latest" not in text.lower()
