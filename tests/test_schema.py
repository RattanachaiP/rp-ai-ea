import copy
import json
import pytest
from bridge.v28.decision_contract import build_decision, validate_pr_a_decision
from bridge.v28.runtime_context import construct_runtime_context
from bridge.decision_writer import DecisionWriter
from tests.test_market_reader import state


def decision():
    return build_decision(construct_runtime_context(state(), now=101), now=101)


def test_hold_only_contract_has_no_action_input_and_matches_executor(tmp_path):
    value = decision()
    with pytest.raises(TypeError):
        build_decision(construct_runtime_context(state(), now=101), "BUY", now=101)
    assert (value["decision"], value["direction"], value["entry_permission"], value["entry_state"],
            value["construction_action"], value["executable"], value["volume"]) == (
            "HOLD", "NONE", False, "HOLD", "NO_ACTION", False, 0.0)
    assert value["fail_safe"] is False  # unchanged Executor reserves true for WAIT/FAIL_SAFE
    path = tmp_path / "decision.json"; path.write_text(json.dumps(value))
    assert DecisionWriter(path, clock=lambda: 101).read().accepted

@pytest.mark.parametrize(("field", "invalid"), [("decision", "BUY"), ("direction", "SELL"),
    ("entry_permission", True), ("executable", True), ("volume", 0.01), ("published_at", "not-a-time"),
    ("extra", 1)])
def test_internal_schema_validator_enforces_consts_types_and_no_extras(field, invalid):
    value = decision(); value[field] = invalid
    with pytest.raises(ValueError): validate_pr_a_decision(value)


def test_json_schema_uses_hold_only_safety_consts():
    schema = json.load(open("schemas/decision_v28_schema.json", encoding="utf-8"))["properties"]
    expected = {"decision":"HOLD", "direction":"NONE", "entry_permission":False, "entry_state":"HOLD",
                "construction_action":"NO_ACTION", "fail_safe":False, "executable":False, "volume":0.0}
    assert {key: schema[key]["const"] for key in expected} == expected


def test_runtime_context_deep_freezes_nested_market():
    raw = state(); context = construct_runtime_context(raw, now=101)
    raw["nested"]["ticks"].append(3)
    assert context.market["nested"]["ticks"] == (1, 2)
    with pytest.raises(TypeError): context.market["nested"]["new"] = 1
