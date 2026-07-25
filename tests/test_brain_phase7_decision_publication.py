"""Decision Publication preserves the frozen V26 writer boundary."""

from __future__ import annotations

import ast
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path
import sys


ROOT = Path(__file__).parents[1]
ENGINE_PATH = ROOT / "bridge" / "ai_decision_engine_xauusd_v26_execution_confidence_engine.py"
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ENGINE_PATH.parent))
SPEC = spec_from_file_location("v26_brain_phase7_engine", ENGINE_PATH)
ENGINE = module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(ENGINE)


def test_decision_publication_returns_the_exact_unmodified_payload_object():
    nested = {"legacy_alias": ["decision", "action", "bias"]}
    payload = {
        "decision": "TRADE",
        "action": "BUY",
        "entry_price": 2350.25,
        "sl": 2345.25,
        "tp": 2360.25,
        "nested": nested,
    }

    published = ENGINE.brain_decision_publication(payload)

    assert published is payload
    assert published["nested"] is nested
    assert published == payload


def test_every_runtime_write_decision_call_uses_the_publication_boundary():
    tree = ast.parse(ENGINE_PATH.read_text(encoding="utf-8"))
    run_function = next(
        node for node in tree.body
        if isinstance(node, ast.FunctionDef) and node.name == "run"
    )
    writes = [
        node for node in ast.walk(run_function)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and node.func.id == "write_decision"
    ]

    assert writes
    for write in writes:
        assert len(write.args) == 1
        boundary = write.args[0]
        assert isinstance(boundary, ast.Call)
        assert isinstance(boundary.func, ast.Name)
        assert boundary.func.id == "brain_decision_publication"
