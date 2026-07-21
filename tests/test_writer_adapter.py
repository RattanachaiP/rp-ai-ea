"""Contract tests for the Brain-to-runtime Writer Adapter boundary."""
from __future__ import annotations

import ast
import dataclasses
import math
from dataclasses import replace
from pathlib import Path

import pytest

from brain.decision_pipeline import DecisionPackage
from runtime.writer_adapter import RuntimeDecisionPayload, WriterAdapter


def package(**changes: object) -> DecisionPackage:
    base = DecisionPackage(
        direction="BUY", confidence=80.0, probability=0.65, expected_value=0.25,
        location_score=75.0, entry_permission=True, entry_state="ENTRY_ALLOWED",
        construction_action="ALLOW_START", position_budget_total=0.05,
        position_budget_used=0.0, position_budget_remaining=0.05, decision="BUY",
        decision_trace=("Probability=0.6500", "ExpectedValue=0.2500", "ELI=ENTRY_ALLOWED"),
        symbol="XAUUSD", volume=0.01, entry_price=2300.0, stop_loss=2290.0, take_profit=2320.0,
    )
    return replace(base, **changes)


def assert_fail_safe(payload: RuntimeDecisionPayload) -> None:
    assert payload.decision == "WAIT"
    assert payload.direction == "NONE"
    assert not payload.entry_permission and payload.entry_state == "FAIL_SAFE"
    assert payload.construction_action == "NO_ACTION"
    assert payload.fail_safe and not payload.executable
    assert payload.decision_reasons[0] == "WRITER_ADAPTER_FAIL_SAFE"


def test_valid_buy_package_is_executable_and_immutable():
    result = WriterAdapter().adapt(package())
    assert dataclasses.is_dataclass(result) and result.__dataclass_params__.frozen
    assert result.decision == "BUY" and result.direction == "BUY"
    assert result.entry_permission and result.executable and not result.fail_safe
    assert result.decision_trace[-1] == "WriterAdapter=VALID"


def test_valid_sell_package_converts_correctly():
    result = WriterAdapter().adapt(package(direction="SELL", decision="SELL"))
    assert result.decision == result.direction == "SELL"
    assert result.executable


def test_legacy_brain_trade_decision_normalizes_to_evaluated_direction():
    result = WriterAdapter().adapt(package(decision="TRADE"))
    assert result.decision == "BUY" and result.executable


@pytest.mark.parametrize(("decision", "state", "action"), [
    ("WAIT", "WAIT_PULLBACK", "WAIT_LOCATION"),
    ("BLOCK", "BLOCK_POOR_RR", "BLOCK_LOCATION"),
    ("HOLD_EXISTING", "ENTRY_ALLOWED", "HOLD_EXISTING"),
    ("NO_ACTION", "ENTRY_ALLOWED", "NO_ACTION"),
])
def test_non_executable_decisions_remain_non_executable(decision, state, action):
    result = WriterAdapter().adapt(package(decision=decision, entry_permission=False, entry_state=state, construction_action=action))
    assert result.decision == decision
    assert not result.executable and not result.fail_safe


@pytest.mark.parametrize("decision", ["BUY", "SELL"])
def test_missing_permission_cannot_produce_executable_directional_decision(decision):
    result = WriterAdapter().adapt(package(decision=decision, direction=decision, entry_permission=False))
    assert_fail_safe(result)


@pytest.mark.parametrize("changes", [
    {"entry_state": "WAIT_PULLBACK", "construction_action": "ALLOW_START"},
    {"entry_state": "BLOCK_POOR_RR", "construction_action": "ALLOW_SCALE"},
    {"decision": "WAIT", "entry_permission": True, "entry_state": "WAIT_CONFIRMATION", "construction_action": "WAIT_LOCATION"},
    {"construction_action": "BLOCK_LOCATION"},
])
def test_contradictory_permission_contracts_fail_safe(changes):
    assert_fail_safe(WriterAdapter().adapt(package(**changes)))


@pytest.mark.parametrize("changes", [
    {"decision": "UNKNOWN"}, {"direction": "NONE"}, {"entry_state": "UNKNOWN"},
    {"construction_action": "UNKNOWN"}, {"entry_permission": 1}, {"confidence": 101.0}, {"probability": 1.1},
    {"confidence": math.nan}, {"probability": math.inf}, {"expected_value": math.nan}, {"location_score": -1.0},
    {"position_budget_total": -0.05}, {"position_budget_used": 0.06},
    {"position_budget_remaining": 0.06}, {"position_budget_remaining": 0.04},
    {"decision_trace": ("valid", 1)},
])
def test_invalid_contract_values_fail_safe(changes):
    assert_fail_safe(WriterAdapter().adapt(package(**changes)))


def test_missing_decision_package_fails_safe():
    assert_fail_safe(WriterAdapter().adapt(None))


def test_trace_order_is_preserved_and_adaptation_is_deterministic():
    source = package(decision_trace=("first", "second", "third"))
    first, second = WriterAdapter().adapt(source), WriterAdapter().adapt(source)
    assert first == second
    assert first.decision_trace == ("first", "second", "third", "WriterAdapter=VALID")


def test_adapter_has_no_publication_or_execution_imports():
    path = Path(__file__).parents[1] / "runtime" / "writer_adapter.py"
    tree = ast.parse(path.read_text(encoding="utf-8"))
    imports = {
        alias.name.lower()
        for node in ast.walk(tree)
        if isinstance(node, (ast.Import, ast.ImportFrom))
        for alias in (node.names if isinstance(node, ast.Import) else [ast.alias(name=node.module or "")])
    }
    prohibited = ("metatrader5", "mt5", "executor", "broker", "writer", "json", "pathlib", "os", "filesystem")
    assert not any(term in imported for imported in imports for term in prohibited)
    source = path.read_text(encoding="utf-8")
    assert "open(" not in source and "write(" not in source and "json.dump" not in source
