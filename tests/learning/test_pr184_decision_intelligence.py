"""PR184 governed advisory Decision Intelligence tests."""
import json
from pathlib import Path
import sys
from uuid import uuid4

import pytest

sys.path.insert(0, str(Path(__file__).parents[2]))
sys.path.insert(1, str(Path(__file__).parent))

from learning.decision_context import DecisionContextRepository, GovernedDecisionContextEngine
from learning.decision_intelligence import (
    DecisionIntelligenceError, DecisionIntelligencePolicy,
    DecisionIntelligenceRepository, GovernedDecisionIntelligenceEngine,
)
from learning.decision_intelligence.identity import canonical_bytes
from test_pr183_decision_context import setup_engine as setup_context_engine


def setup_engine(root):
    confidence_report, _, context_engine = setup_context_engine(root)
    context_report = context_engine.construct_context(confidence_report)
    engine = GovernedDecisionIntelligenceEngine(
        context_engine.repository,
        DecisionIntelligenceRepository(root / "decision_intelligence"),
    )
    return context_report, context_engine.repository, engine


def test_accepts_exact_context_types_and_remains_advisory(tmp_path):
    report, repository, engine = setup_engine(tmp_path)
    for source in (report.decision_contexts[0], report, repository.latest_snapshot()):
        result = engine.construct_intelligence(source)
        item = result.decision_intelligences[0]
        assert result.advisory_only is item.advisory_only is True
        assert item.intelligence_state == "DECISION_INTELLIGENCE_READY"
        assert item.decision_recommendation == "RECOMMENDATION_REVIEW_ELIGIBLE"
        assert item.authority_scope == "ADVISORY_DECISION_INTELLIGENCE_ONLY"
    for invalid in (None, {}, [], report.decision_contexts):
        with pytest.raises(DecisionIntelligenceError, match="INVALID_CONTEXT"):
            engine.construct_intelligence(invalid)
    assert not any(hasattr(engine, name) for name in ("trade", "activate", "publish_decision", "execute"))


def test_replay_deterministic_canonical_and_append_only(tmp_path):
    report, _, engine = setup_engine(tmp_path)
    first = engine.construct_intelligence(report)
    paths = tuple(engine.repository.root.glob("*.json"))
    second = engine.construct_intelligence(report)
    assert second.duplicate_count == 1
    assert first.decision_intelligences == second.decision_intelligences
    assert first.snapshot_uuid == second.snapshot_uuid
    assert tuple(engine.repository.root.glob("*.json")) == paths
    item = first.decision_intelligences[0]
    path = engine.repository.root / f"{item.intelligence_uuid}.json"
    assert path.read_bytes() == canonical_bytes(item.to_dict())
    assert json.loads(path.read_text())["decision_recommendation"] not in {"BUY", "SELL", "HOLD"}
    assert engine.repository.activations() == ()
    engine.repository.activate(
        item, engine.repository.snapshots()[0],
        authority_owner="PR184_DECISION_INTELLIGENCE_OWNER",
        activated_at=item.created_at,
    )
    activations = engine.repository.activations()
    assert len(activations) == 1
    activation_path = engine.repository.activation_root / f"{activations[0].activation_uuid}.json"
    assert activation_path.read_bytes() == canonical_bytes(activations[0].to_dict())
    assert activations[0].intelligence_uuid == item.intelligence_uuid
    assert activations[0].snapshot_uuid == first.snapshot_uuid
    assert engine.repository.activate(
        item, engine.repository.snapshots()[0],
        authority_owner="PR184_DECISION_INTELLIGENCE_OWNER",
        activated_at=item.created_at,
    ) == activations[0]


def test_broken_provenance_snapshot_and_repository_fail_closed(tmp_path):
    report, repository, engine = setup_engine(tmp_path)
    record = report.decision_contexts[0]
    object.__setattr__(record, "context_digest", "0" * 64)
    with pytest.raises(DecisionIntelligenceError, match="BROKEN_PROVENANCE"):
        engine.construct_intelligence(record)
    snapshot = repository.latest_snapshot()
    object.__setattr__(snapshot, "snapshot_digest", "0" * 64)
    with pytest.raises(DecisionIntelligenceError, match="SNAPSHOT_MISMATCH"):
        engine.construct_intelligence(snapshot)
    object.__setattr__(snapshot, "snapshot_digest", report.snapshot_digest)
    object.__setattr__(report, "repository_digest", "0" * 64)
    with pytest.raises(DecisionIntelligenceError, match="REPOSITORY_MISMATCH"):
        engine.construct_intelligence(report)


def test_policy_duplicate_collision_and_snapshot_chain(tmp_path):
    report, _, engine = setup_engine(tmp_path)
    with pytest.raises(ValueError, match="INVALID_INTELLIGENCE_POLICY"):
        DecisionIntelligencePolicy(intelligence_engine_version="PR999")
    with pytest.raises(DecisionIntelligenceError, match="POLICY_MISMATCH"):
        GovernedDecisionIntelligenceEngine(engine.context_repository, policy=object())
    first = engine.construct_intelligence(report)
    item = first.decision_intelligences[0]
    path = engine.repository.root / f"{item.intelligence_uuid}.json"
    path.write_bytes(b"{}")
    with pytest.raises(DecisionIntelligenceError, match="REPLAY_COLLISION"):
        engine.repository.save(item)


def test_repository_replay_and_noncanonical_storage_rejected(tmp_path):
    report, context_repository, engine = setup_engine(tmp_path)
    first = engine.construct_intelligence(report)
    replay = GovernedDecisionIntelligenceEngine(
        DecisionContextRepository(context_repository.root),
        DecisionIntelligenceRepository(engine.repository.root),
    ).construct_intelligence(report)
    assert replay.repository_digest == first.repository_digest
    item = first.decision_intelligences[0]
    path = engine.repository.root / f"{item.intelligence_uuid}.json"
    path.write_text(json.dumps(item.to_dict(), indent=2))
    with pytest.raises(DecisionIntelligenceError, match="NONCANONICAL_DECISION_INTELLIGENCE_JSON"):
        engine.repository.records()
