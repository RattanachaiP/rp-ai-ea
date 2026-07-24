"""PR161 regression coverage for passive Decision Knowledge observations."""
from dataclasses import replace
from datetime import datetime, timezone
from math import nan
from uuid import uuid4

import pytest

from runtime.decision_knowledge_interface import DecisionKnowledgeInterface
from runtime.decision_knowledge_observation import (
    DecisionKnowledgeObservationError,
    DecisionKnowledgeObservationRepository,
    DecisionKnowledgeObserver,
)
from runtime.knowledge_applicability import KnowledgeApplicabilityEngine
from tests.learning.test_knowledge_applicability import context, descriptor, snapshot


def dki(identifier="knowledge-a"):
    report = KnowledgeApplicabilityEngine().evaluate(snapshot((descriptor(identifier),)), context())
    return DecisionKnowledgeInterface.load(report)


def observe(source, **changes):
    values = {"decision_uuid": str(uuid4()), "decision_cycle_uuid": str(uuid4()), "decision_digest": "a" * 64,
              "observation_timestamp": "2026-01-01T00:00:00.000000Z"}
    values.update(changes)
    return DecisionKnowledgeObserver().observe(source, **values)


def test_observation_is_immutable_deterministic_and_uses_only_dki_projection():
    source = dki()
    values = {"decision_uuid": str(uuid4()), "decision_cycle_uuid": str(uuid4()), "decision_digest": "a" * 64,
              "observation_timestamp": "2026-01-01T00:00:00.000000Z"}
    first = DecisionKnowledgeObserver().observe(source, **values)
    second = DecisionKnowledgeObserver().observe(source, **values)
    assert first == second
    assert first.observation_uuid == second.observation_uuid
    assert first.knowledge_observation.observation_status == "OBSERVED"
    assert first.knowledge_observation.applicable_knowledge == first.knowledge_observation.resolved_knowledge
    with pytest.raises(Exception):
        first.observation_digest = "b" * 64


def test_empty_dki_snapshot_is_observed_and_persisted_append_only(tmp_path):
    report = KnowledgeApplicabilityEngine().evaluate(snapshot(()), context())
    observer = DecisionKnowledgeObserver(DecisionKnowledgeObservationRepository(tmp_path))
    values = {"decision_uuid": str(uuid4()), "decision_cycle_uuid": str(uuid4()), "decision_digest": "a" * 64,
              "observation_timestamp": "2026-01-01T00:00:00.000000Z"}
    record = observer.observe(DecisionKnowledgeInterface.load(report), **values)
    path = tmp_path / "decision_knowledge_observations" / f"observation_{record.observation_uuid}.json"
    assert record.knowledge_observation.observation_status == "EMPTY"
    assert path.exists() and observer.observe(DecisionKnowledgeInterface.load(report), **values) == record


def test_fail_closed_for_missing_or_corrupted_dki_and_invalid_record_values():
    with pytest.raises(DecisionKnowledgeObservationError, match="MISSING_DKI"):
        observe(None)
    source = dki()
    object.__setattr__(source._snapshot, "report_digest", "x" * 64)
    with pytest.raises(DecisionKnowledgeObservationError, match="CORRUPTED_DKI"):
        observe(source)
    valid = observe(dki()).knowledge_observation.applicable_knowledge[0]
    with pytest.raises(DecisionKnowledgeObservationError, match="INVALID_CONFIDENCE"):
        replace(valid, confidence=nan)
    with pytest.raises(DecisionKnowledgeObservationError, match="INVALID_APPLICABILITY"):
        replace(valid, applicability_score=2.0)


def test_repository_rejects_existing_non_matching_file(tmp_path):
    record = observe(dki())
    repo = DecisionKnowledgeObservationRepository(tmp_path)
    path = repo.append(record)
    path.write_text("tampered\n", encoding="utf-8")
    with pytest.raises(FileExistsError, match="APPEND_ONLY"):
        repo.append(record)


def test_clock_normalizes_utc_without_touching_a_decision_object():
    observer = DecisionKnowledgeObserver(clock=lambda: datetime(2026, 1, 1, tzinfo=timezone.utc))
    record = observer.observe(dki(), decision_uuid=str(uuid4()), decision_cycle_uuid=str(uuid4()), decision_digest="a" * 64)
    assert record.observation_timestamp == "2026-01-01T00:00:00.000000Z"
