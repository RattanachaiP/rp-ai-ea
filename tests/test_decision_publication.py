"""Tests for the runtime-only Decision Publication boundary."""
from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timezone
import json
import math
from pathlib import Path

import pytest

from brain.decision_pipeline import DecisionPackage
from runtime.decision_publication import DecisionPublisher
from runtime.writer_adapter import WriterAdapter


NOW = datetime(2026, 7, 21, 14, 31, 20, tzinfo=timezone.utc)


def payload():
    package = DecisionPackage("BUY", 80.0, 0.65, 0.25, 75.0, True, "ENTRY_ALLOWED", "ALLOW_START",
                              0.05, 0.0, 0.05, "BUY", ("first", "second"))
    return WriterAdapter().adapt(package)


def publisher(path: Path) -> DecisionPublisher:
    return DecisionPublisher(path, clock=lambda: NOW)


def test_valid_serialization_schema_and_trace_preservation(tmp_path):
    result = publisher(tmp_path / "decision.json").publish(payload())
    saved = json.loads((tmp_path / "decision.json").read_text(encoding="utf-8"))
    assert saved == result
    assert result["schema_version"] == "2.0"
    assert result["brain_version"] == "27.4" and result["runtime_version"] == "27.5"
    assert result["decision_trace"] == ["first", "second", "WriterAdapter=VALID"]
    assert result["executable"] is True


def test_atomic_write_replaces_only_complete_tmp_file(tmp_path, monkeypatch):
    target = tmp_path / "decision.json"
    target.write_text('{"old": true}', encoding="utf-8")
    calls = []
    import runtime.decision_publication as publication
    original_replace = publication.os.replace
    monkeypatch.setattr(publication.os, "replace", lambda source, destination: (calls.append((Path(source), Path(destination))), original_replace(source, destination))[1])
    publisher(target).publish(payload())
    assert calls == [(tmp_path / "decision.tmp", target)]
    assert not (tmp_path / "decision.tmp").exists()
    assert json.loads(target.read_text(encoding="utf-8"))["decision"] == "BUY"


def test_sequence_increments_and_existing_file_is_respected(tmp_path):
    target = tmp_path / "decision.json"
    first = publisher(target).publish(payload())
    second = publisher(target).publish(payload())
    restarted = publisher(target).publish(payload())
    assert [first["sequence_id"], second["sequence_id"], restarted["sequence_id"]] == [1, 2, 3]


def test_heartbeat_and_utc_timestamp_are_generated(tmp_path):
    result = publisher(tmp_path / "decision.json").publish(payload())
    assert result["heartbeat_unix"] == 1784644280
    assert result["published_at"] == "2026-07-21T14:31:20Z"


@pytest.mark.parametrize("change", [
    {"confidence": math.nan}, {"expected_value": math.inf},
    {"schema_version": "wrong"}, {"decision_trace": ("valid", object())},
    {"decision": "WAIT", "executable": True},
])
def test_malformed_payloads_publish_valid_fail_safe(tmp_path, change):
    result = publisher(tmp_path / "decision.json").publish(replace(payload(), **change))
    assert result["decision"] == "WAIT" and result["direction"] == "NONE"
    assert result["fail_safe"] is True and result["executable"] is False
    assert json.loads((tmp_path / "decision.json").read_text(encoding="utf-8")) == result


def test_unserializable_payload_is_rejected_as_fail_safe(tmp_path):
    result = publisher(tmp_path / "decision.json").publish(object())
    assert result["fail_safe"] is True
    assert result["decision_reasons"][0] == "DECISION_PUBLICATION_FAIL_SAFE"


def test_output_is_deterministic_for_fixed_clock_and_payload(tmp_path):
    first = publisher(tmp_path / "one" / "decision.json").publish(payload())
    second = publisher(tmp_path / "two" / "decision.json").publish(payload())
    assert first == second


def test_only_decision_json_may_be_published(tmp_path):
    with pytest.raises(ValueError, match="DECISION_OUTPUT_MUST_BE_DECISION_JSON"):
        publisher(tmp_path / "debug.json")
