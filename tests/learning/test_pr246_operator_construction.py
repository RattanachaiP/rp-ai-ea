"""PR246 operator construction entrypoint regression tests."""

from pathlib import Path
import subprocess
import sys

import pytest

sys.path.insert(0, str(Path(__file__).parents[2]))

from learning.decision_intelligence import DecisionIntelligenceError
from learning.decision_intelligence.operator_construction import construct_from_snapshot
from test_pr184_decision_intelligence import setup_engine


def test_exact_snapshot_constructs_deterministically_through_owner(tmp_path):
    _, context_repository, _ = setup_engine(tmp_path)
    snapshot = context_repository.latest_snapshot()
    target = tmp_path / "constructed"

    first = construct_from_snapshot(
        context_repository_root=context_repository.root,
        repository_root=target,
        context_snapshot_uuid=snapshot.snapshot_uuid,
    )
    before = {path.relative_to(target): path.read_bytes() for path in target.rglob("*.json")}
    second = construct_from_snapshot(
        context_repository_root=context_repository.root,
        repository_root=target,
        context_snapshot_uuid=snapshot.snapshot_uuid,
    )

    assert first.decision_intelligences == second.decision_intelligences
    assert first.snapshot_uuid == second.snapshot_uuid
    assert second.duplicate_count == 1
    assert before == {path.relative_to(target): path.read_bytes() for path in target.rglob("*.json")}


def test_missing_or_unknown_source_fails_before_target_initialization(tmp_path):
    target = tmp_path / "decision_intelligence"
    with pytest.raises(DecisionIntelligenceError, match="DECISION_CONTEXT_REPOSITORY_MISSING"):
        construct_from_snapshot(
            context_repository_root=tmp_path / "missing",
            repository_root=target,
            context_snapshot_uuid="00000000-0000-0000-0000-000000000000",
        )
    assert not target.exists()

    _, context_repository, _ = setup_engine(tmp_path / "source")
    with pytest.raises(DecisionIntelligenceError, match="CONTEXT_SNAPSHOT_MISMATCH"):
        construct_from_snapshot(
            context_repository_root=context_repository.root,
            repository_root=target,
            context_snapshot_uuid="00000000-0000-0000-0000-000000000000",
        )
    assert not target.exists()


def test_module_cli_constructs_without_activation(tmp_path):
    _, context_repository, _ = setup_engine(tmp_path)
    snapshot = context_repository.latest_snapshot()
    target = tmp_path / "cli-intelligence"
    result = subprocess.run(
        [
            sys.executable, "-m", "learning.decision_intelligence.operator_construction",
            "--context-repository-root", str(context_repository.root),
            "--repository-root", str(target),
            "--context-snapshot-uuid", snapshot.snapshot_uuid,
            "--format", "json",
        ],
        check=True, capture_output=True, text=True,
    )
    assert '"prepared_count":1' in result.stdout
    assert not (target / "activations").exists()
