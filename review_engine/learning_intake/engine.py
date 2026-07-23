"""RAIP V10 Learning Intake: offline, read-only qualification publication only.

This module intentionally has no imports from the trading runtime and cannot train,
deploy, or mutate any upstream artefact.  It records deterministic policy decisions.
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
POLICY_SCHEMA_VERSION = "1.0"
PRODUCER = "RAIP Learning Intake Domain"
BASELINE_COMMIT = "317e132"
_REQUIRED_LINEAGE_FIELDS = (
    "evidence_ids", "knowledge_ids", "insight_ids", "recommendation_ids",
    "governance_report_ids", "executive_package_ids", "simulation_report_ids",
)
_COMPONENTS = ("evidence", "knowledge", "insight", "recommendation", "governance", "executive", "simulation")


def _canonical(value: object) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)


def _digest(value: object) -> str:
    return sha256(_canonical(value).encode("utf-8")).hexdigest()


def _atomic_write(path: Path, document: Mapping[str, object]) -> Path:
    """Publish a complete JSON document only after flush and fsync."""
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    payload = (json.dumps(document, sort_keys=True, indent=2, allow_nan=False) + "\n").encode("utf-8")
    with temporary.open("wb") as handle:
        handle.write(payload); handle.flush(); os.fsync(handle.fileno())
    os.replace(temporary, path)
    return path


def _write_once(path: Path, document: Mapping[str, object]) -> Path:
    """Atomically create an immutable record; preserve an existing record."""
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        return path
    temporary = path.with_suffix(path.suffix + ".tmp")
    payload = (json.dumps(document, sort_keys=True, indent=2, allow_nan=False) + "\n").encode("utf-8")
    try:
        with temporary.open("xb") as handle:
            handle.write(payload); handle.flush(); os.fsync(handle.fileno())
        try:
            os.link(temporary, path)
        except FileExistsError:
            pass
    finally:
        if temporary.exists(): temporary.unlink()
    return path


def _ids(value: object) -> list[str]:
    return sorted({str(item) for item in value}) if isinstance(value, (list, tuple, set)) else []


def _status(document: Mapping[str, object], *fields: str) -> str:
    for field in fields:
        value = document.get(field)
        if isinstance(value, str): return value
    return "UNKNOWN"


class LearningIntakePolicy:
    """Loads and validates an explicit immutable V10 qualification policy."""
    REQUIRED = {"policy_id", "policy_version", "required_governance_status", "required_validation_status",
                "required_lineage_components", "minimum_replay_coverage", "minimum_validation_confidence",
                "accepted_schema_versions", "accepted_source_schema_versions", "duplicate_policy", "schema_version"}

    def __init__(self, document: Mapping[str, object]):
        missing = self.REQUIRED - document.keys()
        if missing or document.get("policy_id") != "RAIP_LEARNING_INTAKE_POLICY" or document.get("policy_version") != "1.0.0":
            raise ValueError("unsupported or invalid learning intake policy")
        if document.get("duplicate_policy") != "REJECT": raise ValueError("unsupported duplicate policy")
        if not set(document["required_lineage_components"]).issuperset(_COMPONENTS): raise ValueError("incomplete policy lineage requirements")
        self.document = dict(document)

    @classmethod
    def default(cls) -> "LearningIntakePolicy":
        path = Path(__file__).with_name("learning_intake_policy.json")
        return cls(json.loads(path.read_text(encoding="utf-8")))

    @classmethod
    def load(cls, path: Path | str) -> "LearningIntakePolicy":
        try: return cls(json.loads(Path(path).read_text(encoding="utf-8")))
        except (OSError, json.JSONDecodeError) as error: raise ValueError("invalid learning intake policy artifact") from error


class LineageVerificationEngine:
    def verify(self, lineage: Mapping[str, object]) -> dict[str, object]:
        normalized = {field: _ids(lineage.get(field)) for field in _REQUIRED_LINEAGE_FIELDS}
        missing = [field for field in _REQUIRED_LINEAGE_FIELDS if not normalized[field]]
        return {"schema_version": SCHEMA_VERSION, "producer": PRODUCER, "document_type": "lineage_verification",
                "lineage": normalized, "lineage_hash": _digest(normalized), "complete": not missing,
                "missing_lineage": missing, "status": "VERIFIED" if not missing else "REJECTED"}


class DuplicatePreventionEngine:
    """Candidate SHA-256 identity from the approved non-volatile identity fields."""
    def identity(self, evidence_hash: str, validation_report_id: str, lineage_hash: str, policy_version: str, schema_version: str) -> str:
        return _digest({"evidence_hash": evidence_hash, "validation_report_id": validation_report_id,
                        "lineage_hash": lineage_hash, "policy_version": policy_version, "schema_version": schema_version})


class QualificationEngine:
    def __init__(self, policy: LearningIntakePolicy | None = None): self.policy = policy or LearningIntakePolicy.default()

    def qualify(self, candidate: Mapping[str, object], *, duplicate: bool = False) -> dict[str, object]:
        governance = candidate.get("governance", {}) if isinstance(candidate.get("governance"), Mapping) else {}
        executive = candidate.get("executive_package", {}) if isinstance(candidate.get("executive_package"), Mapping) else {}
        validation = candidate.get("simulation_report", {}) if isinstance(candidate.get("simulation_report"), Mapping) else {}
        lineage = candidate.get("lineage", {}) if isinstance(candidate.get("lineage"), Mapping) else {}
        verification = LineageVerificationEngine().verify(lineage)
        policy = self.policy.document
        evidence_hash = str(candidate.get("evidence_hash") or _digest(verification["lineage"]["evidence_ids"]))
        validation_id = str(validation.get("report_id") or validation.get("validation_report_id") or verification["lineage"]["simulation_report_ids"][0] if verification["lineage"]["simulation_report_ids"] else "")
        candidate_id = DuplicatePreventionEngine().identity(evidence_hash, validation_id, str(verification["lineage_hash"]), str(policy["policy_version"]), SCHEMA_VERSION)
        source_versions = policy["accepted_source_schema_versions"]
        schema_ok = (str(governance.get("schema_version")) == str(source_versions["governance"]) and
                     str(executive.get("schema_version")) == str(source_versions["executive"]) and
                     str(validation.get("schema_version")) == str(source_versions["validation"]))
        governance_ok = _status(governance, "status", "overall_status") in (str(policy["required_governance_status"]), "HEALTHY") and governance.get("approved", True) is not False
        executive_ok = executive.get("executive_finalized") is True or executive.get("finalization_status") == "FINALIZED"
        validation_ok = (_status(validation, "validation_status", "status") in (str(policy["required_validation_status"]), "VALID", "SUPPORTED") or validation.get("validation_successful") is True)
        completed = validation.get("completed") is True or validation.get("validation_completed") is True or validation.get("status") == "COMPLETED"
        deferred = not completed or ("replay_coverage" in validation and float(validation["replay_coverage"]) < float(policy["minimum_replay_coverage"]))
        checks = {"GOVERNANCE_APPROVED": governance_ok, "EXECUTIVE_FINALIZED": executive_ok,
                  "SIMULATION_COMPLETED": completed, "VALIDATION_COMPLETED": validation_ok,
                  "LINEAGE_COMPLETE": bool(verification["complete"]), "SCHEMA_COMPATIBLE": schema_ok,
                  "NOT_DUPLICATE": not duplicate}
        failed = [name for name, passed in checks.items() if not passed]
        if duplicate or not verification["complete"] or not governance_ok or not validation_ok: status = "REJECTED"
        elif not schema_ok or deferred or not executive_ok: status = "DEFERRED"
        else: status = "QUALIFIED"
        reasons = (["Candidate satisfies all active learning intake policy requirements."] if status == "QUALIFIED" else
                   ["Duplicate candidate identity is already registered."] if duplicate else
                   ["Required lineage reference is missing: " + ", ".join(verification["missing_lineage"])] if not verification["complete"] else
                   ["Candidate awaits completed executive, simulation, or schema-compatible validation."] if status == "DEFERRED" else
                   ["Candidate does not satisfy the active learning intake policy."])
        return {"candidate_id": candidate_id, "candidate_hash": candidate_id, "qualification_status": status,
                "qualification_reasons": reasons, "passed_checks": [x for x in checks if checks[x]], "failed_checks": failed,
                "governance_status": _status(governance, "status", "overall_status"), "validation_status": _status(validation, "validation_status", "status"),
                "lineage_status": verification["status"], "schema_compatibility": schema_ok, "duplicate_status": "DUPLICATE" if duplicate else "NOT_DUPLICATE",
                "policy_version": policy["policy_version"], "schema_version": SCHEMA_VERSION, "validation_report_id": validation_id,
                "evidence_hash": evidence_hash, "lineage_hash": verification["lineage_hash"], "lineage_verification": verification}


class CandidateRegistry:
    """Append-only immutable catalog; it is not a scheduler or executable queue."""
    def __init__(self, root: Path | str): self.root = Path(root)
    @property
    def records(self) -> Path: return self.root / "learning_intake" / "candidate_registry" / "records"
    @property
    def index(self) -> Path: return self.root / "learning_intake" / "candidate_registry" / "learning_candidate_registry.json"
    def contains(self, candidate_id: str) -> bool: return (self.records / candidate_id / "learning_candidate.json").exists()
    def register(self, report: Mapping[str, object], created_at: str) -> Path:
        record = {key: report[key] for key in ("candidate_id", "candidate_hash", "qualification_status", "qualification_report_id", "validation_report_id", "evidence_hash", "lineage_hash", "policy_version", "schema_version")}
        record.update({"created_at": created_at, "producer": PRODUCER, "baseline_commit": BASELINE_COMMIT, "document_type": "learning_candidate"})
        path = _write_once(self.records / str(report["candidate_id"]) / "learning_candidate.json", record)
        rows = []
        for item in sorted(self.records.glob("*/learning_candidate.json")):
            try: rows.append(json.loads(item.read_text(encoding="utf-8")))
            except (OSError, json.JSONDecodeError): continue
        _atomic_write(self.index, {"schema_version": SCHEMA_VERSION, "producer": PRODUCER, "document_type": "learning_candidate_registry", "append_only": True, "candidates": rows, "candidate_count": len(rows)})
        return path


class LearningReadinessReport:
    def build(self, reports: Sequence[Mapping[str, object]]) -> dict[str, object]:
        statuses = {status: [str(x["candidate_id"]) for x in reports if x["qualification_status"] == status] for status in ("QUALIFIED", "DEFERRED", "REJECTED")}
        total = len(reports)
        return {"schema_version": SCHEMA_VERSION, "producer": PRODUCER, "document_type": "learning_readiness", "qualified_candidates": statuses["QUALIFIED"], "deferred_candidates": statuses["DEFERRED"], "rejected_candidates": statuses["REJECTED"], "missing_lineage": {str(x["candidate_id"]): x["failed_checks"] for x in reports if "LINEAGE_COMPLETE" in x["failed_checks"]}, "schema_mismatch": [str(x["candidate_id"]) for x in reports if not x["schema_compatibility"]], "validation_coverage": {"validated": sum("VALIDATION_COMPLETED" not in x["failed_checks"] for x in reports), "total": total}, "executive_approval_coverage": {"finalized": sum("EXECUTIVE_FINALIZED" not in x["failed_checks"] for x in reports), "total": total}}


class LearningIntakeCoordinator:
    """Single-worker post-validation publisher; writes exclusively under learning_intake/."""
    def __init__(self, root: Path | str, *, policy: LearningIntakePolicy | None = None, clock: Callable[[], datetime] | None = None):
        self.root = Path(root); self.clock = clock or (lambda: datetime.now(timezone.utc)); self.registry = CandidateRegistry(root)
        self.qualifier = QualificationEngine(policy); self.readiness = LearningReadinessReport(); self.log = logging.getLogger(__name__)
        self._executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="raip-learning-intake")
    def intake(self, candidate: Mapping[str, object]) -> Path:
        preview = self.qualifier.qualify(candidate)
        report = self.qualifier.qualify(candidate, duplicate=self.registry.contains(str(preview["candidate_id"])))
        created_at = self.clock().astimezone(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")
        report_id = _digest({"candidate_id": report["candidate_id"], "policy_version": report["policy_version"], "schema_version": SCHEMA_VERSION})
        report.update({"report_id": report_id, "created_at": created_at, "producer": PRODUCER, "baseline_commit": BASELINE_COMMIT, "document_type": "learning_intake_report"})
        base = self.root / "learning_intake"; candidate_id = str(report["candidate_id"])
        _write_once(base / "lineage" / candidate_id / "lineage_verification.json", report["lineage_verification"])
        if report["duplicate_status"] == "DUPLICATE":
            # A duplicate cannot mutate its historical decision report or registry record;
            # retain a separate immutable audit event for this evaluation instead.
            _write_once(base / "duplicate_detection" / candidate_id / "duplicate_detection.json", report)
            return self.registry.records / candidate_id / "learning_candidate.json"
        _write_once(base / "qualification" / candidate_id / "learning_intake_report.json", report)
        _write_once(base / "qualification" / candidate_id / "qualification_report.json", report)
        report["qualification_report_id"] = report_id
        path = self.registry.register(report, created_at)
        reports = list(self._reports())
        _atomic_write(base / "readiness" / "learning_readiness.json", self.readiness.build(reports))
        return path
    def intake_async(self, candidate: Mapping[str, object]) -> Future: return self._executor.submit(self.intake, candidate)
    def shutdown(self) -> None: self._executor.shutdown(wait=True)
    def _reports(self):
        for path in sorted((self.root / "learning_intake" / "qualification").glob("*/learning_intake_report.json")):
            try: yield json.loads(path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError): self.log.warning("unreadable learning intake report: %s", path)

# Compatibility aliases retained only for callers of the pre-addendum API.
CandidateQueue = CandidateRegistry
