"""PR247 PR183 operator construction entrypoint regression tests."""

from pathlib import Path
import subprocess
import sys

import pytest

sys.path.insert(0, str(Path(__file__).parents[2]))
sys.path.insert(1, str(Path(__file__).parent))

from learning.decision_context import DecisionContextError
from learning.decision_context.operator_construction import construct_from_snapshot
from test_pr183_decision_context import setup_engine


def test_exact_snapshot_constructs_deterministically_through_owner(tmp_path):
    _, confidence_repository, _ = setup_engine(tmp_path)
    snapshot = confidence_repository.latest_snapshot()
    target = tmp_path / "constructed"

    first = construct_from_snapshot(
        confidence_repository_root=confidence_repository.root,
        repository_root=target,
        confidence_snapshot_uuid=snapshot.snapshot_uuid,
    )
    before = {path.relative_to(target): path.read_bytes() for path in target.rglob("*.json")}
    second = construct_from_snapshot(
        confidence_repository_root=confidence_repository.root,
        repository_root=target,
        confidence_snapshot_uuid=snapshot.snapshot_uuid,
    )

    assert first.decision_contexts == second.decision_contexts
    assert first.snapshot_uuid == second.snapshot_uuid
    assert second.duplicate_count == 1
    assert before == {path.relative_to(target): path.read_bytes() for path in target.rglob("*.json")}


def test_missing_or_unknown_source_fails_before_target_initialization(tmp_path):
    target = tmp_path / "decision_context"
    with pytest.raises(DecisionContextError, match="CONFIDENCE_REPOSITORY_MISSING"):
        construct_from_snapshot(
            confidence_repository_root=tmp_path / "missing",
            repository_root=target,
            confidence_snapshot_uuid="00000000-0000-0000-0000-000000000000",
        )
    assert not target.exists()

    _, confidence_repository, _ = setup_engine(tmp_path / "source")
    with pytest.raises(DecisionContextError, match="CONFIDENCE_SNAPSHOT_MISMATCH"):
        construct_from_snapshot(
            confidence_repository_root=confidence_repository.root,
            repository_root=target,
            confidence_snapshot_uuid="00000000-0000-0000-0000-000000000000",
        )
    assert not target.exists()


def test_module_cli_constructs_only_decision_context(tmp_path):
    _, confidence_repository, _ = setup_engine(tmp_path)
    snapshot = confidence_repository.latest_snapshot()
    target = tmp_path / "cli-context"
    result = subprocess.run(
        [
            sys.executable, "-m", "learning.decision_context.operator_construction",
            "--confidence-repository-root", str(confidence_repository.root),
            "--repository-root", str(target),
            "--confidence-snapshot-uuid", snapshot.snapshot_uuid,
            "--format", "json",
        ],
        check=True, capture_output=True, text=True,
    )
    assert '"prepared_count":1' in result.stdout
    assert not (tmp_path / "decision_intelligence").exists()
