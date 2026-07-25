"""PR183 advisory Decision Context boundary and persistence tests."""
import json
from pathlib import Path
import sys

import pytest

sys.path.insert(0, str(Path(__file__).parents[2]))
sys.path.insert(1, str(Path(__file__).parent))

from learning.decision_context import (DecisionContextError,
    DecisionContextPolicy, DecisionContextRepository, GovernedDecisionContextEngine)
from learning.decision_context.identity import canonical_bytes
from learning.runtime_confidence import RuntimeConfidenceRepository
from test_pr182_runtime_confidence import governed_artifacts


def setup_engine(root):
    eligibility_report, _, evaluator = governed_artifacts(root)
    confidence_report = evaluator.evaluate_confidence(eligibility_report)
    confidence_repository = evaluator.repository
    engine = GovernedDecisionContextEngine(confidence_repository,
        DecisionContextRepository(root / "decision_context"))
    return confidence_report, confidence_repository, engine


def test_accepts_only_three_exact_confidence_artifacts_and_is_advisory(tmp_path):
    report, repository, engine = setup_engine(tmp_path)
    for source in (report.confidence_records[0], report, repository.latest_snapshot()):
        output = engine.construct_context(source)
        assert output.advisory_only is True
        assert output.decision_contexts[0].authority_scope == "ADVISORY_DECISION_CONTEXT_ONLY"
    for invalid in (None, {}, [], report.confidence_records):
        with pytest.raises(DecisionContextError, match="INVALID_CONFIDENCE"):
            engine.construct_context(invalid)
    assert not any(hasattr(engine, name) for name in ("trade", "activate", "publish_decision", "execute"))


def test_replay_duplicate_determinism_canonical_json_and_append_only(tmp_path):
    report, _, engine = setup_engine(tmp_path)
    first = engine.construct_context(report)
    before = tuple(engine.repository.root.glob("*.json"))
    second = engine.construct_context(report)
    assert second.duplicate_count == 1
    assert first.decision_contexts == second.decision_contexts
    assert tuple(engine.repository.root.glob("*.json")) == before
    context = first.decision_contexts[0]
    path = engine.repository.root / f"{context.context_uuid}.json"
    assert path.read_bytes() == canonical_bytes(context.to_dict())
    assert json.loads(path.read_text())["context_state"] == "CONTEXT_PREPARED"


def test_broken_provenance_snapshot_and_repository_mismatches_fail_closed(tmp_path):
    report, repository, engine = setup_engine(tmp_path)
    bad_record = report.confidence_records[0]
    object.__setattr__(bad_record, "confidence_digest", "0" * 64)
    with pytest.raises(DecisionContextError, match="BROKEN_PROVENANCE"):
        engine.construct_context(bad_record)
    bad_snapshot = repository.latest_snapshot()
    object.__setattr__(bad_snapshot, "snapshot_digest", "0" * 64)
    with pytest.raises(DecisionContextError, match="SNAPSHOT_MISMATCH"):
        engine.construct_context(bad_snapshot)
    object.__setattr__(bad_snapshot, "snapshot_digest", report.snapshot_digest)
    bad_report = report
    object.__setattr__(bad_report, "repository_digest", "0" * 64)
    with pytest.raises(DecisionContextError, match="REPOSITORY_MISMATCH"):
        engine.construct_context(bad_report)


def test_policy_and_engine_versions_fail_closed(tmp_path):
    _, repository, _ = setup_engine(tmp_path)
    with pytest.raises(ValueError, match="INVALID_CONTEXT_POLICY"):
        DecisionContextPolicy(context_engine_version="PR999")
    with pytest.raises(DecisionContextError, match="POLICY_MISMATCH"):
        GovernedDecisionContextEngine(repository, policy=object())


def test_snapshot_chain_and_context_replay(tmp_path):
    report, _, engine = setup_engine(tmp_path)
    first = engine.construct_context(report)
    assert engine.repository.latest_snapshot().snapshot_uuid == first.snapshot_uuid
    replay = GovernedDecisionContextEngine(engine.confidence_repository,
        DecisionContextRepository(engine.repository.root)).construct_context(report)
    assert replay.snapshot_uuid == first.snapshot_uuid
    assert replay.repository_digest == first.repository_digest
