"""PR193 governed ExecutionContext publication tests."""
from datetime import datetime, timezone
from hashlib import sha256
import json
from pathlib import Path
import stat

import pytest

from runtime.execution_context_publication import (
    PUBLICATION_VERSION,
    ExecutionContextPublicationError,
    ExecutionContextPublisher,
)


ENGINE_VERSION = "V26.6.2A"
FIELDS = {
    "execution_uuid": "10000000-0000-4000-8000-000000000001",
    "decision_uuid": "20000000-0000-4000-8000-000000000002",
    "package_uuid": "30000000-0000-4000-8000-000000000003",
    "replay_uuid": "40000000-0000-4000-8000-000000000004",
    "execution_confidence": 0.75,
    "readiness_state": "EXECUTION_READY_FOR_ENVIRONMENT_CHECK",
    "environment_state": "ENVIRONMENT_READY_FOR_FEASIBILITY",
    "feasibility_state": "EXECUTION_FEASIBLE",
    "policy_version": "PR192-POLICY.1",
    "engine_version": ENGINE_VERSION,
    "advisory_only": True,
}
NOW = datetime(2026, 7, 26, 12, 30, 45, 123456, tzinfo=timezone.utc)


def publisher(tmp_path):
    return ExecutionContextPublisher(
        tmp_path / "execution_context.json",
        expected_engine_version=ENGINE_VERSION,
        clock=lambda: NOW,
    )


def test_successful_publication_stamps_version_timestamp_and_is_read_only(tmp_path):
    context = publisher(tmp_path).create_and_publish(FIELDS)
    output = tmp_path / "execution_context.json"
    assert json.loads(output.read_bytes()) == context.to_dict()
    assert context.timestamp == "2026-07-26T12:30:45.123456Z"
    assert context.contract_version == "PR192-EXECUTION-CONTEXT.1"
    assert PUBLICATION_VERSION == "PR193-EXECUTION-CONTEXT-PUBLICATION.1"
    assert stat.S_IMODE(output.stat().st_mode) == 0o444


def test_digest_verifies_exact_unsigned_canonical_payload(tmp_path):
    context = publisher(tmp_path).create_and_publish(FIELDS)
    unsigned = json.dumps(
        context.unsigned_payload(), sort_keys=True, separators=(",", ":"),
        ensure_ascii=False, allow_nan=False,
    ).encode("utf-8")
    assert context.payload_digest == sha256(unsigned).hexdigest()


def test_atomic_replacement_exposes_only_complete_payload(tmp_path, monkeypatch):
    owner = publisher(tmp_path)
    first = owner.create_and_publish(FIELDS)
    previous = owner.output_path.read_bytes()
    observed = []
    original_replace = __import__("runtime.execution_context_publication", fromlist=["os"]).os.replace

    def replace(source, destination):
        observed.append((Path(source).read_bytes(), Path(destination).read_bytes()))
        return original_replace(source, destination)

    monkeypatch.setattr("runtime.execution_context_publication.os.replace", replace)
    second = owner.create_and_publish({**FIELDS, "execution_confidence": 0.8})
    assert observed == [(json.dumps(second.to_dict(), sort_keys=True, separators=(",", ":")).encode(), previous)]
    assert json.loads(owner.output_path.read_bytes()) == second.to_dict()
    assert first != second


def test_atomic_write_failure_preserves_previous_publication(tmp_path, monkeypatch):
    owner = publisher(tmp_path)
    owner.create_and_publish(FIELDS)
    previous = owner.output_path.read_bytes()
    monkeypatch.setattr("runtime.execution_context_publication.os.replace", lambda *_: (_ for _ in ()).throw(OSError("disk")))
    with pytest.raises(ExecutionContextPublicationError, match="ATOMIC_PUBLICATION_FAILED"):
        owner.create_and_publish({**FIELDS, "execution_confidence": 0.8})
    assert owner.output_path.read_bytes() == previous
    assert not list(tmp_path.glob("*.tmp"))


@pytest.mark.parametrize("changes", [
    {"engine_version": "V27"},
    {"execution_uuid": "invalid"},
    {"execution_confidence": float("nan")},
])
def test_invalid_or_incompatible_payload_is_rejected_without_publication(tmp_path, changes):
    with pytest.raises(ExecutionContextPublicationError):
        publisher(tmp_path).create_and_publish({**FIELDS, **changes})
    assert not (tmp_path / "execution_context.json").exists()


def test_fail_closed_serialization_has_no_fallback_or_partial_file(tmp_path):
    values = {**FIELDS, "policy_version": object()}
    with pytest.raises(ExecutionContextPublicationError, match="CONTEXT_CREATION_FAILED"):
        publisher(tmp_path).create_and_publish(values)
    assert list(tmp_path.iterdir()) == []
