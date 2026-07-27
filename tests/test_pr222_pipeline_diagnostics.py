"""PR222 canonical runtime trace and production visibility coverage."""

from dataclasses import replace
from pathlib import Path
import sys
from uuid import UUID

import pytest

sys.path.insert(0, str(Path(__file__).parents[1]))

from runtime.pipeline_diagnostics import (
    ExecutionPackageContents,
    RepositoryDiagnostic,
    RuntimePipelineDiagnosticError,
    RuntimePipelineVerifier,
    RuntimeStage,
    RuntimeStageRecord,
    STAGE_ORDER,
)


DIGEST = "a" * 64
TIMESTAMP = "2026-07-27T12:00:00+00:00"


def uid(number):
    return str(UUID(int=number))


def valid_trace():
    records = tuple(
        RuntimeStageRecord(
            stage=stage,
            uuid=uid(number),
            timestamp=TIMESTAMP,
            status="OK",
            previous_uuid=None if number == 1 else uid(number - 1),
            repository_digest=DIGEST,
            snapshot_uuid=uid(number + 100),
        )
        for number, stage in enumerate(STAGE_ORDER, 1)
    )
    repositories = {
        record.stage: RepositoryDiagnostic(
            repository_digest=DIGEST,
            latest_snapshot_uuid=record.snapshot_uuid,
            immutable_identities=((record.uuid, DIGEST),),
            activation_count=1 if record.stage is RuntimeStage.ACTIVATION else None,
        )
        for record in records
    }
    package = ExecutionPackageContents(records[5].uuid, records[6].uuid, records[7].uuid)
    return records, repositories, package


def test_complete_trace_produces_stage_diagnostics_and_production_summary():
    records, repositories, package = valid_trace()

    report = RuntimePipelineVerifier().verify(records, repositories, package)

    diagnostics = report.diagnostics()
    assert diagnostics.count("[STAGE ") == 9
    assert "[STAGE 01] MARKET_STATE_READY" in diagnostics
    assert f"parent_uuid={records[0].uuid}" in diagnostics
    assert "[STAGE 09] EXECUTION_PACKAGE_READY" in diagnostics
    assert diagnostics.count("status=OK") == 9
    summary = report.production_summary()
    assert "Execution Package .... OK" in summary
    assert "Executor ............. READY" in summary
    assert summary.endswith("PRODUCTION READY")


@pytest.mark.parametrize(
    ("index", "change", "reason"),
    (
        (4, {"previous_uuid": None}, "ORPHAN_UUID"),
        (4, {"previous_uuid": uid(99)}, "LINEAGE_BREAK"),
        (4, {"uuid": uid(4)}, "DUPLICATED_UUID"),
        (4, {"status": "FAILED", "reason": "CORRUPTED_STATE"}, "CORRUPTED_STATE"),
    ),
)
def test_lineage_or_stage_failure_fails_closed_with_operator_context(index, change, reason):
    records, repositories, package = valid_trace()
    failed = replace(records[index], **change)
    records = records[:index] + (failed,) + records[index + 1:]

    with pytest.raises(RuntimePipelineDiagnosticError) as captured:
        RuntimePipelineVerifier().verify(records, repositories, package)

    message = str(captured.value)
    assert f"Stage: {failed.stage.value}" in message
    assert "UUID:" in message
    assert "Parent UUID:" in message
    assert "Repository Digest:" in message
    assert "Snapshot UUID:" in message
    assert f"Reason: {reason}" in message


def test_rejects_duplicate_stage_invocation_before_any_summary():
    records, repositories, package = valid_trace()
    records = records[:3] + (records[2],) + records[3:]

    with pytest.raises(RuntimePipelineDiagnosticError, match="STAGE_COUNT_MISMATCH"):
        RuntimePipelineVerifier().verify(records, repositories, package)


@pytest.mark.parametrize(
    ("repository_change", "reason"),
    (
        ({"repository_digest": "b" * 64}, "DIGEST_MISMATCH"),
        ({"latest_snapshot_uuid": uid(999)}, "SNAPSHOT_MISMATCH"),
        ({"immutable_identities": ()}, "ORPHAN_UUID"),
        ({"activation_count": 2}, "ACTIVATION_COUNT_MISMATCH"),
    ),
)
def test_rejects_repository_inconsistency(repository_change, reason):
    records, repositories, package = valid_trace()
    stage = RuntimeStage.ACTIVATION
    repositories[stage] = replace(repositories[stage], **repository_change)

    with pytest.raises(RuntimePipelineDiagnosticError, match=reason):
        RuntimePipelineVerifier().verify(records, repositories, package)


def test_rejects_execution_package_missing_or_wrong_mandatory_artifact():
    records, repositories, package = valid_trace()
    package = replace(package, feasibility_uuid=uid(999))

    with pytest.raises(RuntimePipelineDiagnosticError, match="EXECUTION_PACKAGE_INCOMPLETE"):
        RuntimePipelineVerifier().verify(records, repositories, package)
