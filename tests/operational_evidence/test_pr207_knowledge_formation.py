from dataclasses import replace
import runpy

import pytest

from operational_evidence.knowledge_formation import (
    KnowledgeFormationEngine, KnowledgeFormationError,
    KnowledgeQualificationPolicy, KnowledgeRepository,
)
from operational_evidence.pattern_discovery import (
    PatternDiscoveryConfig, PatternDiscoveryEngine,
)


_batch = runpy.run_path(
    "tests/operational_evidence/test_pr206_pattern_discovery.py")["evidence_batch"]


def inputs(count=10, confidence=0.95):
    sources = _batch(count=count)
    patterns = PatternDiscoveryEngine(PatternDiscoveryConfig(
        minimum_sample_count=2, confidence_level=confidence)).discover(*sources)
    pattern = next(item for item in patterns if item.pattern_type == "ENTRY_TIMING_CLUSTER")
    return pattern, *sources


def test_qualification_and_replay_are_deterministic():
    source = inputs()
    engine = KnowledgeFormationEngine()
    first = engine.form(*source)
    replayed = engine.form(*source)
    assert first == replayed
    assert first.qualification_status == "QUALIFIED"
    assert first.parent_pattern_uuid == source[0].pattern_uuid
    assert first.evidence_references.pattern_uuid == source[0].pattern_uuid
    assert len(first.evidence_references.attribution_uuids) == 10
    assert len(first.canonical_bytes()) > 0
    assert len(first.sha256_digest) == 64
    assert first.passive_evidence_only


def test_declared_rules_produce_candidate_and_rejected_without_inference():
    candidate = KnowledgeFormationEngine().form(*inputs(count=2))
    assert candidate.qualification_status == "CANDIDATE"
    assert "SAMPLE_COUNT_BELOW_QUALIFIED_THRESHOLD" in candidate.qualification_rationale
    assert "MINIMUM_QUALIFIED_SAMPLE_COUNT=10" in candidate.qualification_rationale

    rejected = KnowledgeFormationEngine(KnowledgeQualificationPolicy(
        minimum_qualified_sample_count=10,
        minimum_configured_confidence_level=0.95,
        minimum_candidate_confidence_level=0.8,
    )).form(*inputs(count=2, confidence=0.75))
    assert rejected.qualification_status == "REJECTED"
    assert "CONFIGURED_CONFIDENCE_BELOW_CANDIDATE_THRESHOLD" in rejected.qualification_rationale


def test_integrity_completeness_replay_and_duplicates_fail_closed():
    pattern, attributions, events, outcomes = inputs(count=2)
    engine = KnowledgeFormationEngine()
    with pytest.raises(KnowledgeFormationError, match="SOURCE_COMPLETENESS_FAILURE"):
        engine.form(pattern, attributions[:1], events, outcomes)
    with pytest.raises(KnowledgeFormationError, match="DUPLICATE_OR_EMPTY_SOURCE_EVIDENCE"):
        engine.form(pattern, attributions, [events[0], events[0]], outcomes)
    object.__setattr__(pattern, "sha256_digest", "0" * 64)
    with pytest.raises(KnowledgeFormationError, match="PATTERN_INTEGRITY_FAILURE"):
        engine.form(pattern, attributions, events, outcomes)


def test_repository_is_atomic_append_only_and_duplicate_rejecting(tmp_path):
    knowledge = KnowledgeFormationEngine().form(*inputs(count=2))
    repository = KnowledgeRepository(tmp_path)
    path = repository.append(knowledge)
    assert path.read_bytes() == knowledge.canonical_bytes() + b"\n"
    with pytest.raises(KnowledgeFormationError, match="DUPLICATE_KNOWLEDGE_IDENTITY"):
        repository.append(knowledge)
    with pytest.raises(KnowledgeFormationError, match="KNOWLEDGE_DIGEST_MISMATCH"):
        replace(knowledge, sha256_digest="0" * 64)
