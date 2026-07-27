"""Fail-closed observability for the canonical governed runtime pipeline.

This module is deliberately an observer: it does not construct, persist, select,
or execute governed artifacts.  Owners hand it the identities they actually
produced and it verifies the completed trace before exposing a health summary.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Mapping, Sequence

from learning.pattern_memory.models import valid_digest, valid_timestamp, valid_uuid


class RuntimePipelineDiagnosticError(RuntimeError):
    """A terminal pipeline integrity failure, including operator diagnostics."""


class RuntimeStage(str, Enum):
    MARKET_STATE = "MARKET_STATE_READY"
    DECISION_CONTEXT = "CONTEXT_READY"
    DECISION_INTELLIGENCE = "INTELLIGENCE_READY"
    ACTIVATION = "ACTIVATION_READY"
    DECISION_RECOMMENDATION = "RECOMMENDATION_READY"
    EXECUTION_READINESS = "READINESS_READY"
    EXECUTION_ENVIRONMENT = "ENVIRONMENT_READY"
    EXECUTION_FEASIBILITY = "FEASIBILITY_READY"
    EXECUTION_PACKAGE = "EXECUTION_PACKAGE_READY"


STAGE_ORDER = tuple(RuntimeStage)


@dataclass(frozen=True, slots=True)
class RuntimeStageRecord:
    """One observed invocation of a governed stage."""

    stage: RuntimeStage
    uuid: str
    timestamp: str
    status: str
    previous_uuid: str | None
    repository_digest: str
    snapshot_uuid: str
    reason: str = ""


@dataclass(frozen=True, slots=True)
class RepositoryDiagnostic:
    """Repository facts captured after a stage owner completed its write."""

    repository_digest: str
    latest_snapshot_uuid: str
    immutable_identities: tuple[tuple[str, str], ...]
    activation_count: int | None = None


@dataclass(frozen=True, slots=True)
class ExecutionPackageContents:
    """The mandatory governed identities carried by PR189."""

    readiness_uuid: str
    environment_uuid: str
    feasibility_uuid: str


@dataclass(frozen=True, slots=True)
class RuntimePipelineReport:
    records: tuple[RuntimeStageRecord, ...]

    def diagnostics(self) -> str:
        blocks = []
        for number, record in enumerate(self.records, 1):
            values = [
                f"[STAGE {number:02d}] {record.stage.value}",
                f"uuid={record.uuid}",
                f"timestamp={record.timestamp}",
            ]
            if record.previous_uuid is not None:
                values.append(f"parent_uuid={record.previous_uuid}")
            values.append(f"status={record.status}")
            blocks.append("\n".join(values))
        return "\n\n--------------------------------\n\n".join(blocks)

    def production_summary(self, *, executor_ready: bool = True) -> str:
        labels = (
            "Writer", "Reader", "Context", "Intelligence", "Activation",
            "Recommendation", "Readiness", "Environment", "Feasibility",
            "Execution Package", "Executor",
        )
        states = ("OK",) * 10 + (("READY" if executor_ready else "NOT READY"),)
        overall = "PRODUCTION READY" if executor_ready else "NOT PRODUCTION READY"
        rows = ["===================================", "SYSTEM HEALTH", ""]
        rows.extend(f"{label} {'.' * max(1, 21 - len(label))} {state}" for label, state in zip(labels, states))
        rows.extend(("", "===================================", "", "Overall Status", "", overall))
        return "\n".join(rows)


class RuntimePipelineVerifier:
    """Verify one completed trace without changing any governed subsystem."""

    @staticmethod
    def _fail(record: RuntimeStageRecord | None, reason: str) -> None:
        raise RuntimePipelineDiagnosticError("\n".join((
            f"Stage: {record.stage.value if record else 'PIPELINE'}",
            f"UUID: {record.uuid if record else 'N/A'}",
            f"Parent UUID: {record.previous_uuid if record and record.previous_uuid else 'N/A'}",
            f"Repository Digest: {record.repository_digest if record else 'N/A'}",
            f"Snapshot UUID: {record.snapshot_uuid if record else 'N/A'}",
            f"Reason: {reason}",
        )))

    def verify(
        self,
        records: Sequence[RuntimeStageRecord],
        repositories: Mapping[RuntimeStage, RepositoryDiagnostic],
        package: ExecutionPackageContents,
    ) -> RuntimePipelineReport:
        records = tuple(records)
        if len(records) != len(STAGE_ORDER):
            self._fail(None, "STAGE_COUNT_MISMATCH")
        if tuple(record.stage for record in records) != STAGE_ORDER:
            self._fail(None, "STAGE_ORDER_OR_DUPLICATION")

        seen = set()
        for index, record in enumerate(records):
            if not isinstance(record, RuntimeStageRecord):
                self._fail(None, "INVALID_STAGE_RECORD")
            if not valid_uuid(record.uuid) or not valid_timestamp(record.timestamp):
                self._fail(record, "INVALID_STAGE_IDENTITY")
            if record.uuid in seen:
                self._fail(record, "DUPLICATED_UUID")
            seen.add(record.uuid)
            expected_parent = None if index == 0 else records[index - 1].uuid
            if record.previous_uuid != expected_parent:
                self._fail(record, "LINEAGE_BREAK" if record.previous_uuid else "ORPHAN_UUID")
            if record.status != "OK":
                self._fail(record, record.reason or "STAGE_FAILED")
            if not valid_digest(record.repository_digest) or not valid_uuid(record.snapshot_uuid):
                self._fail(record, "INVALID_REPOSITORY_EVIDENCE")

            repository = repositories.get(record.stage)
            if repository is None:
                self._fail(record, "REPOSITORY_EVIDENCE_MISSING")
            identities = tuple(repository.immutable_identities)
            if (
                not valid_digest(repository.repository_digest)
                or not valid_uuid(repository.latest_snapshot_uuid)
                or len({identity for identity, _ in identities}) != len(identities)
                or any(not valid_uuid(identity) or not valid_digest(digest) for identity, digest in identities)
            ):
                self._fail(record, "REPOSITORY_AMBIGUITY")
            if record.uuid not in {identity for identity, _ in identities}:
                self._fail(record, "ORPHAN_UUID")
            if repository.repository_digest != record.repository_digest:
                self._fail(record, "DIGEST_MISMATCH")
            if repository.latest_snapshot_uuid != record.snapshot_uuid:
                self._fail(record, "SNAPSHOT_MISMATCH")
            if record.stage is RuntimeStage.ACTIVATION and repository.activation_count != 1:
                self._fail(record, "ACTIVATION_COUNT_MISMATCH")

        mandatory = (package.readiness_uuid, package.environment_uuid, package.feasibility_uuid)
        expected = (records[5].uuid, records[6].uuid, records[7].uuid)
        if any(not valid_uuid(value) for value in mandatory) or mandatory != expected:
            self._fail(records[-1], "EXECUTION_PACKAGE_INCOMPLETE")
        return RuntimePipelineReport(records)
