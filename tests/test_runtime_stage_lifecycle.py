"""PR243 structured Runtime stage trace coverage."""

import json

import pytest

from runtime.stage_lifecycle import RuntimeStageLifecycle


def events(path):
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]


def test_success_has_complete_stable_stage_identity(tmp_path):
    path = tmp_path / "trace.jsonl"
    values = iter((1000.0, 1000.125))
    lifecycle = RuntimeStageLifecycle(path, clock=lambda: next(values))

    with lifecycle.stage("Decision Publication", "Decision Engine"):
        pass

    entered, succeeded = events(path)
    assert [entered["event"], succeeded["event"]] == ["ENTER", "SUCCESS"]
    assert entered["stage_uuid"] == succeeded["stage_uuid"]
    assert succeeded == {
        "duration_ms": 125.0,
        "end_timestamp": "1970-01-01T00:16:40.125000Z",
        "event": "SUCCESS",
        "exception_message": None,
        "exception_type": None,
        "failure_reason": None,
        "propagation_path": [],
        "stage_name": "Decision Publication",
        "stage_uuid": entered["stage_uuid"],
        "start_timestamp": "1970-01-01T00:16:40Z",
        "upstream_dependency": "Decision Engine",
    }


def test_failure_preserves_originating_exception_and_does_not_swallow(tmp_path):
    path = tmp_path / "trace.jsonl"
    values = iter((1000.0, 1000.01, 1000.02))
    lifecycle = RuntimeStageLifecycle(path, clock=lambda: next(values))

    with pytest.raises(LookupError, match="ACTIVATION_MISSING"):
        try:
            with lifecycle.stage("Decision Engine", "Environment Observation"):
                raise LookupError("ACTIVATION_MISSING")
        except LookupError as exc:
            lifecycle.termination(
                exc, ("Decision Engine", "Environment Observation", "Runtime")
            )
            raise

    entered, failed, terminated = events(path)
    assert entered["event"] == "ENTER"
    assert failed["event"] == "FAIL"
    assert failed["exception_type"] == "LookupError"
    assert failed["exception_message"] == "ACTIVATION_MISSING"
    assert failed["failure_reason"] == "ACTIVATION_MISSING"
    assert failed["propagation_path"] == ["Decision Engine", "Environment Observation"]
    assert terminated["event"] == "RUNTIME_TERMINATED"
    assert terminated["propagation_path"] == [
        "Decision Engine", "Environment Observation", "Runtime"
    ]
