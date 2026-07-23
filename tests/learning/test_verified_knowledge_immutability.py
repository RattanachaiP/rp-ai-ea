"""Regression coverage for deeply immutable verified knowledge."""
from __future__ import annotations

import pytest

from learning.validation import ValidationResult, VerifiedKnowledge


def verified_knowledge(conditions: dict[str, object], statistics: dict[str, object]) -> VerifiedKnowledge:
    return VerifiedKnowledge(
        "pattern-1",
        conditions,
        statistics,  # type: ignore[arg-type]
        ValidationResult(
            "pattern-1",
            "VERIFIED",
            {"sample_size": True},
            {"nested": {"values": [0.65, 1.7]}},  # type: ignore[arg-type]
        ),
    )


def test_verified_knowledge_deep_freezes_nested_values_and_input_aliases() -> None:
    conditions: dict[str, object] = {"filters": {"sessions": ["LONDON"]}}
    statistics: dict[str, object] = {"cohorts": [{"samples": [40]}]}
    knowledge = verified_knowledge(conditions, statistics)

    conditions["filters"]["sessions"].append("NEW_YORK")  # type: ignore[index,union-attr]
    statistics["cohorts"][0]["samples"].append(99)  # type: ignore[index,union-attr]

    assert knowledge.conditions == {"filters": {"sessions": ("LONDON",)}}
    assert knowledge.statistics == {"cohorts": ({"samples": (40,)},)}
    with pytest.raises(TypeError):
        knowledge.conditions["filters"]["sessions"] = ()  # type: ignore[index]
    with pytest.raises(AttributeError):
        knowledge.statistics["cohorts"][0]["samples"].append(99)  # type: ignore[index,union-attr]
    with pytest.raises(TypeError):
        knowledge.validation.metrics["nested"]["values"] = ()  # type: ignore[index]


def test_verified_knowledge_equality_and_serialization_remain_deterministic() -> None:
    first = verified_knowledge(
        {"filters": {"sessions": ["LONDON"]}},
        {"cohorts": [{"samples": [40]}]},
    )
    second = verified_knowledge(
        {"filters": {"sessions": ["LONDON"]}},
        {"cohorts": [{"samples": [40]}]},
    )

    assert first == second
    assert first.to_dict() == {
        "pattern_uuid": "pattern-1",
        "conditions": {"filters": {"sessions": ["LONDON"]}},
        "statistics": {"cohorts": [{"samples": [40]}]},
        "validation": {
            "pattern_uuid": "pattern-1",
            "status": "VERIFIED",
            "checks": {"sample_size": True},
            "metrics": {"nested": {"values": [0.65, 1.7]}},
            "outlier_count": 0,
            "validation_version": "1.0",
        },
    }
