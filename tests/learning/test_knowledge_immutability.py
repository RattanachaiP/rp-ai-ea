"""Regression coverage for the canonical deeply immutable Knowledge record."""
from __future__ import annotations

import pytest

from learning.knowledge import Knowledge


def canonical_knowledge(confidence_placeholder: object) -> Knowledge:
    return Knowledge.create(
        knowledge_uuid="knowledge-1",
        created_timestamp="2026-01-01T00:00:00Z",
        pattern_uuid="pattern-1",
        validation_uuid="validation-1",
        applicable_symbols=("XAUUSD",),
        applicable_sessions=("LONDON",),
        applicable_market_states=("TRENDING",),
        sample_count=40,
        verified_win_rate=0.65,
        average_rr=1.7,
        confidence_placeholder=confidence_placeholder,
    )


def test_knowledge_prevents_nested_mutation_and_source_aliasing() -> None:
    source = {"cohorts": [{"outcomes": ["win"]}]}
    knowledge = canonical_knowledge(source)

    source["cohorts"][0]["outcomes"].append("loss")

    assert knowledge.confidence_placeholder == {"cohorts": ({"outcomes": ("win",)},)}
    with pytest.raises(TypeError):
        knowledge.confidence_placeholder["cohorts"][0]["outcomes"] = ()
    with pytest.raises(AttributeError):
        knowledge.confidence_placeholder["cohorts"][0]["outcomes"].append("loss")


def test_knowledge_serialization_is_detached_and_round_trips() -> None:
    knowledge = canonical_knowledge({"cohorts": [{"outcomes": ["win"]}]})
    serialized = knowledge.to_dict()

    serialized["confidence_placeholder"]["cohorts"][0]["outcomes"].append("loss")

    assert knowledge.confidence_placeholder == {"cohorts": ({"outcomes": ("win",)},)}
    assert Knowledge.from_dict(knowledge.to_dict()) == knowledge
