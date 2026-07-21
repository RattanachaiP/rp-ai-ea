"""Contract tests for the decision-publication-to-executor writer bridge."""
from __future__ import annotations

import ast
import json
from pathlib import Path

import pytest

from bridge.decision_writer import DecisionWriter

NOW = 1_784_644_280.0


def document(**changes):
    value = {
        "schema_version": "2.0", "brain_version": "27.4", "runtime_version": "27.5", "sequence_id": 1,
        "heartbeat_unix": int(NOW), "published_at": "2026-07-21T14:31:20Z", "decision": "BUY", "direction": "BUY",
        "entry_permission": True, "entry_state": "ENTRY_ALLOWED", "construction_action": "ALLOW_START",
        "confidence": 80.0, "probability": .65, "expected_value": .25, "location_score": 75.0,
        "position_budget_total": .05, "position_budget_used": 0.0, "position_budget_remaining": .05,
        "decision_reasons": [], "decision_trace": [], "fail_safe": False, "executable": True,
    }
    value.update(changes)
    return value


def write(path, value): path.write_text(json.dumps(value), encoding="utf-8")
def reader(path, **kwargs): return DecisionWriter(path, clock=lambda: NOW, **kwargs)


def test_valid_runtime_payload_and_legacy_mapping(tmp_path):
    path = tmp_path / "decision.json"; write(path, document())
    result = reader(path).read()
    assert result.accepted and result.payload["decision"] == "BUY" and result.payload["executable"] is True
    assert result.legacy_payload == {"decision": "BUY", "bias": "BUY", "allowed": True, "executable": True, "fail_safe": False, "confidence": 80.0, "sequence_id": 1, "heartbeat_unix": int(NOW)}

@pytest.mark.parametrize(("content", "reason"), [("{", "MALFORMED_JSON"), (json.dumps(document(schema_version="99")), "UNSUPPORTED_SCHEMA_VERSION")])
def test_json_and_schema_fail_independently(tmp_path, content, reason):
    path = tmp_path / "decision.json"; path.write_text(content, encoding="utf-8")
    result = reader(path).read()
    assert not result.accepted and result.payload["decision"] == "WAIT" and result.payload["fail_safe"] and result.reason == reason


def test_stale_heartbeat_fails_safe(tmp_path):
    path = tmp_path / "decision.json"; write(path, document(heartbeat_unix=int(NOW - 31)))
    assert reader(path, heartbeat_max_age_seconds=30).read().reason == "STALE_HEARTBEAT"


def test_duplicate_and_decreasing_sequences_are_not_forwarded(tmp_path):
    path = tmp_path / "decision.json"; bridge = reader(path)
    write(path, document(sequence_id=2)); assert bridge.read().accepted
    write(path, document(sequence_id=2)); duplicate = bridge.read()
    assert duplicate.ignored_duplicate and not duplicate.payload["executable"]
    write(path, document(sequence_id=1)); assert bridge.read().reason == "STALE_SEQUENCE"

@pytest.mark.parametrize(("decision", "executable"), [("BUY", True), ("WAIT", False), ("BLOCK", False), ("HOLD_EXISTING", False)])
def test_published_executable_flag_and_intent_are_forwarded_verbatim(tmp_path, decision, executable):
    path = tmp_path / "decision.json"; write(path, document(decision=decision, executable=executable))
    result = reader(path).read()
    assert result.accepted and result.payload["decision"] == decision and result.payload["executable"] is executable


def test_published_fail_safe_payload_is_forwarded_without_reinterpretation(tmp_path):
    path = tmp_path / "decision.json"; write(path, document(decision="WAIT", direction="NONE", entry_permission=False, entry_state="FAIL_SAFE", construction_action="NO_ACTION", fail_safe=True, executable=False))
    result = reader(path).read()
    assert result.accepted and result.payload["fail_safe"] is True and not result.payload["executable"]


def test_deterministic_behavior_and_no_brain_imports(tmp_path):
    path = tmp_path / "decision.json"; write(path, document())
    assert reader(path).read() == reader(path).read()
    source = (Path(__file__).parents[1] / "bridge" / "decision_writer.py").read_text(encoding="utf-8")
    imports = [node.module or "" for node in ast.walk(ast.parse(source)) if isinstance(node, ast.ImportFrom)]
    assert not any(name == "brain" or name.startswith("brain.") for name in imports)
