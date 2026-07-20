"""Static contract checks for the frozen, private Brain V1 architecture."""

from __future__ import annotations

import ast
import dataclasses
import importlib
import inspect
from pathlib import Path
from typing import get_type_hints

import pytest


ROOT = Path(__file__).parents[1]
BRAIN = ROOT / "brain"
MODULES = {
    "market_perception": set(),
    "market_understanding": {"brain.market_perception"},
    "market_reasoning": {"brain.market_understanding"},
    "probability_engine": {"brain.market_reasoning", "brain.market_understanding"},
    "expected_value_engine": {"brain.market_reasoning", "brain.market_understanding", "brain.probability_engine"},
    "position_intelligence": {"brain.expected_value_engine", "brain.market_reasoning", "brain.market_understanding", "brain.probability_engine"},
}
FORBIDDEN_TERMS = ("bridge", "mt5", "dashboard", "executor", "writer", "decision")


def _brain_imports(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    imports: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module:
            imports.add(node.module)
        elif isinstance(node, ast.Import):
            imports.update(alias.name for alias in node.names)
    return imports


def test_all_brain_dataclasses_are_frozen():
    discovered = []
    for module_name in MODULES:
        module = importlib.import_module(f"brain.{module_name}")
        for _, value in inspect.getmembers(module, inspect.isclass):
            if value.__module__ == module.__name__ and dataclasses.is_dataclass(value):
                discovered.append(value)
                assert value.__dataclass_params__.frozen, value.__name__
    assert {item.__name__ for item in discovered} == {
        "MarketPerception", "MarketUnderstanding", "MarketReasoning",
        "MarketStateProbability", "ProbabilityAssessment", "ConfidenceInterval",
        "ExpectedValueAssessment", "PositionIntelligenceAssessment",
    }


def test_typed_layers_only_import_their_direct_predecessors_and_no_runtime_owners():
    for module_name, allowed_brain_imports in MODULES.items():
        imports = _brain_imports(BRAIN / f"{module_name}.py")
        brain_imports = {name for name in imports if name == "brain" or name.startswith("brain.")}
        assert brain_imports <= allowed_brain_imports
        assert not any(term in name.lower() for name in imports for term in FORBIDDEN_TERMS)


def test_public_typed_functions_have_frozen_v1_input_output_signatures():
    from brain.market_perception import MarketPerception, extract_market_perception
    from brain.market_reasoning import MarketReasoning, reason_about_market
    from brain.market_understanding import MarketUnderstanding, interpret_market_understanding
    from brain.probability_engine import ProbabilityAssessment, estimate_market_probabilities
    from brain.expected_value_engine import ExpectedValueAssessment, evaluate_expected_value
    from brain.position_intelligence import PositionIntelligenceAssessment, assess_position_intelligence

    assert list(inspect.signature(extract_market_perception).parameters) == ["market_state"]
    assert list(inspect.signature(interpret_market_understanding).parameters) == ["perception"]
    assert list(inspect.signature(reason_about_market).parameters) == ["understanding"]
    assert list(inspect.signature(estimate_market_probabilities).parameters) == ["understanding", "reasoning"]
    assert list(inspect.signature(evaluate_expected_value).parameters) == ["understanding", "reasoning", "probability_assessment"]
    assert list(inspect.signature(assess_position_intelligence).parameters) == ["understanding", "reasoning", "probability_assessment", "expected_value_assessment"]
    assert get_type_hints(extract_market_perception)["return"] is MarketPerception
    assert get_type_hints(interpret_market_understanding)["return"] is MarketUnderstanding
    assert get_type_hints(reason_about_market)["return"] is MarketReasoning
    assert get_type_hints(estimate_market_probabilities)["return"] is ProbabilityAssessment
    assert get_type_hints(evaluate_expected_value)["return"] is ExpectedValueAssessment
    assert get_type_hints(assess_position_intelligence)["return"] is PositionIntelligenceAssessment


def test_layer_type_boundaries_reject_wrong_predecessor_objects():
    from brain.market_perception import extract_market_perception
    from brain.market_reasoning import reason_about_market
    from brain.market_understanding import interpret_market_understanding
    from brain.probability_engine import estimate_market_probabilities

    perception = extract_market_perception({"bid": 1.0})
    understanding = interpret_market_understanding(perception)
    reasoning = reason_about_market(understanding)
    with pytest.raises(TypeError):
        interpret_market_understanding({})
    with pytest.raises(TypeError):
        reason_about_market(perception)
    with pytest.raises(TypeError):
        estimate_market_probabilities(perception, reasoning)
    other_understanding = interpret_market_understanding(extract_market_perception({"bid": 2.0}))
    with pytest.raises(ValueError):
        estimate_market_probabilities(other_understanding, reasoning)
