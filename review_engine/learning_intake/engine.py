"""RAIP V10 Learning Intake: qualification only, never model learning.

The module deliberately imports neither runtime nor intelligence producers.  It consumes
immutable artefacts after governance, executive preparation, and historical validation.
"""
from __future__ import annotations

from concurrent.futures import Future, ThreadPoolExecutor
from datetime import datetime, timezone
from hashlib import sha256
import json
import logging
import os
from pathlib import Path
from typing import Callable, Mapping, Sequence

SCHEMA_VERSION = "10.0.0"
PRODUCER = "RAIP Learning Intake Domain"
_REQUIRED_LINEAGE = ("evidence_ids", "knowledge_ids", "insight_ids", "recommendation_ids",
                     "governance_report_ids", "executive_package_ids", "simulation_report_ids")
_SUPPORTED = {"governance": "6", "executive": "7", "simulation": "9"}


def _canonical(value: object) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)


def _digest(value: object) -> str:
    return sha256(_canonical(value).encode("utf-8")).hexdigest()


def _iso(clock: Callable[[], datetime]) -> str:
    return clock().astimezone(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")


def _atomic_write(path: Path, document: Mapping[str, object]) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    with temporary.open("wb") as handle:
        handle.write((json.dumps(document, sort_keys=True, indent=2, allow_nan=False) + "\n").encode("utf-8"))
        handle.flush(); os.fsync(handle.fileno())
    os.replace(temporary, path)
    return path


def _write_once(path: Path, document: Mapping[str, object]) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists(): return path
    temporary = path.with_suffix(path.suffix + ".tmp")
    try:
        with temporary.open("xb") as handle:
            handle.write((json.dumps(document, sort_keys=True, indent=2, allow_nan=False) + "\n").encode("utf-8"))
            handle.flush(); os.fsync(handle.fileno())
        try: os.link(temporary, path)
        except FileExistsError: pass
    finally:
        if temporary.exists(): temporary.unlink()
    return path


def _ids(value: object) -> list[str]:
    return sorted({str(item) for item in value}) if isinstance(value, (list, tuple, set)) else []


class LineageVerificationEngine:
    """Rejects candidates that cannot trace every required upstream authority."""
    def verify(self, lineage: Mapping[str, object]) -> dict[str, object]:
        normalized = {field: _ids(lineage.get(field)) for field in _REQUIRED_LINEAGE}
        missing = [field for field in _REQUIRED_LINEAGE if not normalized[field]]
        lineage_hash = _digest(normalized)
        return {"schema_version": SCHEMA_VERSION, "producer": PRODUCER,
                "document_type": "lineage_verification", "lineage": normalized,
                "lineage_hash": lineage_hash, "complete": not missing,
                "missing_lineage": missing, "status": "VERIFIED" if not missing else "REJECTED"}


class DuplicatePreventionEngine:
    """Stable candidate identity: canonical lineage SHA-256 plus schema version."""
    def identity(self, lineage_hash: str, schema_version: str = SCHEMA_VERSION) -> str:
        return _digest({"lineage_hash": lineage_hash, "schema_version": schema_version})


class QualificationEngine:
    """Deterministically applies Rule #024 without changing upstream documents."""
    def qualify(self, candidate: Mapping[str, object]) -> dict[str, object]:
        governance = candidate.get("governance", {}) if isinstance(candidate.get("governance"), Mapping) else {}
        executive = candidate.get("executive_package", {}) if isinstance(candidate.get("executive_package"), Mapping) else {}
        simulation = candidate.get("simulation_report", {}) if isinstance(candidate.get("simulation_report"), Mapping) else {}
        lineage = candidate.get("lineage", {}) if isinstance(candidate.get("lineage"), Mapping) else {}
        verification = LineageVerificationEngine().verify(lineage)
        compatible = all(str(document.get("schema_version", "")).split(".", 1)[0] == major
                         for document, major in ((governance, _SUPPORTED["governance"]), (executive, _SUPPORTED["executive"]), (simulation, _SUPPORTED["simulation"])))
        checks = {
            "governance_passed": governance.get("overall_status") == "HEALTHY" and governance.get("approved", True) is not False,
            "executive_finalized": executive.get("executive_finalized") is True or executive.get("finalization_status") == "FINALIZED",
            "simulation_completed": simulation.get("completed") is True or simulation.get("status") == "COMPLETED" or bool(simulation.get("validation_completed")),
            "validation_successful": simulation.get("validation_successful") is True or simulation.get("validation_status") in ("VALID", "SUPPORTED") or simulation.get("recommendation_quality", {}).get("status") == "SUPPORTED",
            "evidence_lineage_complete": verification["complete"],
            "schema_compatible": compatible,
        }
        failed = [name for name, passed in checks.items() if not passed]
        if not verification["complete"]: state = "Rejected"
        elif not compatible: state = "Deferred"
        elif not checks["governance_passed"]: state = "Rejected"
        elif not checks["executive_finalized"] or not checks["simulation_completed"]: state = "Waiting"
        elif not checks["validation_successful"]: state = "Rejected"
        else: state = "Qualified"
        identity = DuplicatePreventionEngine().identity(str(verification["lineage_hash"]), SCHEMA_VERSION)
        return {"schema_version": SCHEMA_VERSION, "producer": PRODUCER, "document_type": "qualification_report",
                "candidate_identity": identity, "decision_id": executive.get("decision_id"), "qualification_state": state,
                "qualified": state == "Qualified", "checks": checks, "failed_checks": failed,
                "lineage_hash": verification["lineage_hash"], "schema_compatibility": compatible}


class CandidateQueue:
    """Append-only logical queue backed by immutable per-candidate records.

    The JSON queue is a reconstructed atomic index. Existing candidate records are never
    replaced, so restarts and duplicate submissions cannot alter prior queue entries.
    """
    def __init__(self, root: Path | str): self.root = Path(root)
    @property
    def records(self) -> Path: return self.root / "learning_intake" / "candidate_queue" / "candidates"
    @property
    def index(self) -> Path: return self.root / "learning_intake" / "candidate_queue" / "learning_candidate_queue.json"
    def enqueue(self, qualification: Mapping[str, object], lineage: Mapping[str, object]) -> Path:
        identity = str(qualification["candidate_identity"])
        record = {"schema_version": SCHEMA_VERSION, "producer": PRODUCER, "document_type": "learning_candidate",
                  "candidate_identity": identity, "state": qualification["qualification_state"],
                  "decision_id": qualification.get("decision_id"), "lineage_hash": qualification["lineage_hash"],
                  "qualification_report": dict(qualification), "lineage": dict(lineage)}
        path = _write_once(self.records / identity / "learning_candidate.json", record)
        rows = []
        for item in sorted(self.records.glob("*/learning_candidate.json")):
            try: rows.append(json.loads(item.read_text(encoding="utf-8")))
            except (OSError, json.JSONDecodeError): continue
        _atomic_write(self.index, {"schema_version": SCHEMA_VERSION, "producer": PRODUCER,
                                   "document_type": "learning_candidate_queue", "append_only": True,
                                   "candidates": rows, "candidate_count": len(rows)})
        return path


class LearningReadinessReport:
    def build(self, qualifications: Sequence[Mapping[str, object]]) -> dict[str, object]:
        states = {state: [item["candidate_identity"] for item in qualifications if item["qualification_state"] == state]
                  for state in ("Qualified", "Deferred", "Rejected", "Waiting")}
        missing = {item["candidate_identity"]: item["failed_checks"] for item in qualifications if "evidence_lineage_complete" in item["failed_checks"]}
        mismatch = [item["candidate_identity"] for item in qualifications if "schema_compatible" in item["failed_checks"]]
        count = len(qualifications)
        return {"schema_version": SCHEMA_VERSION, "producer": PRODUCER, "document_type": "learning_readiness",
                "qualified_candidates": states["Qualified"], "deferred_candidates": states["Deferred"],
                "rejected_candidates": states["Rejected"], "waiting_candidates": states["Waiting"],
                "missing_lineage": missing, "schema_mismatch": mismatch,
                "validation_coverage": {"validated": sum("validation_successful" not in x["failed_checks"] for x in qualifications), "total": count},
                "executive_approval_coverage": {"finalized": sum("executive_finalized" not in x["failed_checks"] for x in qualifications), "total": count}}


class LearningIntakeCoordinator:
    """Async post-validation intake coordinator; it is isolated from live execution."""
    def __init__(self, root: Path | str, *, clock: Callable[[], datetime] | None = None):
        self.root = Path(root); self.clock = clock or (lambda: datetime.now(timezone.utc)); self.queue = CandidateQueue(root)
        self.qualifier = QualificationEngine(); self.lineage = LineageVerificationEngine(); self.readiness = LearningReadinessReport()
        self._executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="raip-learning-intake"); self.log = logging.getLogger(__name__)
    def intake(self, candidate: Mapping[str, object]) -> Path:
        verification = self.lineage.verify(candidate.get("lineage", {}) if isinstance(candidate.get("lineage"), Mapping) else {})
        report = self.qualifier.qualify(candidate)
        identity = str(report["candidate_identity"])
        base = self.root / "learning_intake"
        _write_once(base / "lineage" / identity / "lineage_verification.json", verification)
        _write_once(base / "qualification" / identity / "qualification_report.json", report)
        path = self.queue.enqueue(report, verification)
        qualifications = [row.get("qualification_report", {}) for row in self._queue_rows()]
        _atomic_write(base / "readiness" / "learning_readiness.json", self.readiness.build(qualifications))
        return path
    def intake_async(self, candidate: Mapping[str, object]) -> Future: return self._executor.submit(self.intake, candidate)
    def shutdown(self) -> None: self._executor.shutdown(wait=True)
    def _queue_rows(self):
        for path in sorted(self.queue.records.glob("*/learning_candidate.json")):
            try: yield json.loads(path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError): self.log.warning("unreadable learning candidate: %s", path)
