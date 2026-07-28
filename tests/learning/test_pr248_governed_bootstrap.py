"""PR248 end-to-end operator composition acceptance tests."""
from pathlib import Path
import sys

import pytest

sys.path.insert(0, str(Path(__file__).parent))
from learning.bootstrap.operator_bootstrap import BootstrapError, construct, inspect, plan, verify
from learning.knowledge_registry import KnowledgeRegistryRepository
from test_pr180_runtime_knowledge import registry_report


def test_empty_fresh_install_inspection_and_plan_are_non_mutating(tmp_path):
    base = tmp_path / "learning_data"
    before = tuple(tmp_path.rglob("*"))
    status = inspect(base)
    proposed = plan(base)
    assert tuple(tmp_path.rglob("*")) == before
    assert status["mutation_occurred"] is proposed["mutation_occurred"] is False
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
    assert checked["chain_valid"] is True
    assert checked["activation_checked_separately"] is True
    assert checked["production_ready"] is False
    assert not (base / "decision_intelligence" / "activation").exists()


def test_guidance_is_powershell_safe_and_never_selects_latest_for_mutation(tmp_path):
    proposed = plan(tmp_path / "learning_data")
    text = "\n".join(proposed["commands"])
    assert "$SnapshotUuid" in text
    assert "<EXACT_UUID>" not in text
    assert "latest" not in text.lower()
