"""RAIP V14.1 learning-engine core: offline immutable materialization only.

The core accepts only V10-qualified registry records and emits auditable learning
material.  It intentionally does not train a model, alter a threshold, or import a
runtime module; any later training or deployment domain must be separately approved.
"""
from __future__ import annotations

from concurrent.futures import Future, ThreadPoolExecutor
from datetime import datetime, timezone
from hashlib import sha256
import json
import os
from pathlib import Path
from typing import Callable, Mapping

SCHEMA_VERSION = "14.1.0"
PRODUCER = "RAIP Learning Engine Core"
BASELINE_COMMIT = "da668b2"


def _canonical(value: object) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)


def _digest(value: object) -> str:
    return sha256(_canonical(value).encode("utf-8")).hexdigest()


def _write_once(path: Path, document: Mapping[str, object]) -> Path:
    """Atomically create an immutable document without replacing an existing one."""
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    payload = (json.dumps(document, sort_keys=True, indent=2, allow_nan=False) + "\n").encode("utf-8")
    try:
        with temporary.open("xb") as handle:
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
        try:
            os.link(temporary, path)
        except FileExistsError:
            pass
    finally:
        if temporary.exists():
            temporary.unlink()
    return path


class LearningEnginePolicy:
    """Explicit policy gate for materializing a V10 candidate into learning material."""

    REQUIRED = {"policy_id", "policy_version", "schema_version", "accepted_candidate_schema_version",
                "accepted_qualification_status", "publication_mode", "runtime_mutation_permitted", "training_permitted"}

    def __init__(self, document: Mapping[str, object]):
        if self.REQUIRED - document.keys() or document.get("policy_id") != "RAIP_LEARNING_ENGINE_POLICY":
            raise ValueError("invalid learning engine policy")
        if document.get("policy_version") != SCHEMA_VERSION or document.get("schema_version") != SCHEMA_VERSION:
            raise ValueError("unsupported learning engine policy version")
        if document.get("publication_mode") != "IMMUTABLE_MATERIALIZATION_ONLY":
            raise ValueError("unsupported learning engine publication mode")
        if document.get("runtime_mutation_permitted") is not False or document.get("training_permitted") is not False:
            raise ValueError("learning engine policy must prohibit training and runtime mutation")
        self.document = dict(document)

    @classmethod
    def default(cls) -> "LearningEnginePolicy":
        return cls(json.loads(Path(__file__).with_name("learning_engine_policy.json").read_text(encoding="utf-8")))


class LearningMaterializationEngine:
    """Deterministically turns one qualified candidate record into passive learning material."""

    REQUIRED_CANDIDATE_FIELDS = {"candidate_id", "candidate_hash", "qualification_status", "qualification_report_id",
                                 "validation_report_id", "evidence_hash", "lineage_hash", "policy_version", "schema_version"}

    def __init__(self, policy: LearningEnginePolicy | None = None):
        self.policy = policy or LearningEnginePolicy.default()

    def materialize(self, candidate: Mapping[str, object]) -> dict[str, object]:
        missing = sorted(self.REQUIRED_CANDIDATE_FIELDS - candidate.keys())
        missing.extend(sorted(field for field in self.REQUIRED_CANDIDATE_FIELDS
                              if field in candidate and (not isinstance(candidate[field], str) or not candidate[field].strip())))
        expected_schema = str(self.policy.document["accepted_candidate_schema_version"])
        status = str(candidate.get("qualification_status", ""))
        schema_version = str(candidate.get("schema_version", ""))
        accepted = not missing and status == self.policy.document["accepted_qualification_status"] and schema_version == expected_schema
        candidate_id = str(candidate.get("candidate_id", ""))
        material_id = _digest({"candidate_id": candidate_id, "candidate_hash": candidate.get("candidate_hash"),
                               "learning_engine_policy_version": self.policy.document["policy_version"], "schema_version": SCHEMA_VERSION})
        reasons = ([] if accepted else (["Missing required candidate fields: " + ", ".join(missing)] if missing else
                   ["Candidate is not a schema-compatible qualified V10 record."]))
        return {
            "schema_version": SCHEMA_VERSION,
            "producer": PRODUCER,
            "document_type": "learning_material",
            "material_id": material_id,
            "source_candidate_id": candidate_id,
            "source_candidate_hash": str(candidate.get("candidate_hash", "")),
            "source_qualification_report_id": str(candidate.get("qualification_report_id", "")),
            "source_validation_report_id": str(candidate.get("validation_report_id", "")),
            "evidence_hash": str(candidate.get("evidence_hash", "")),
            "lineage_hash": str(candidate.get("lineage_hash", "")),
            "materialization_status": "MATERIALIZED" if accepted else "REJECTED",
            "rejection_reasons": reasons,
            "learning_engine_policy_version": self.policy.document["policy_version"],
            "training_performed": False,
            "runtime_mutation_performed": False,
        }


class LearningEngineCoordinator:
    """Single-worker, offline publisher that reads V10 registry records and writes V14.1 only."""

    def __init__(self, root: Path | str, *, policy: LearningEnginePolicy | None = None,
                 clock: Callable[[], datetime] | None = None):
        self.root = Path(root)
        self.engine = LearningMaterializationEngine(policy)
        self.clock = clock or (lambda: datetime.now(timezone.utc))
        self._executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="raip-learning-engine")

    @property
    def registry_path(self) -> Path:
        return self.root / "learning_intake" / "candidate_registry" / "learning_candidate_registry.json"

    def materialize_candidate(self, candidate: Mapping[str, object]) -> Path:
        document = self.engine.materialize(candidate)
        created_at = self.clock().astimezone(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")
        document.update({"created_at": created_at, "baseline_commit": BASELINE_COMMIT})
        return _write_once(self.root / "learning_engine" / "materials" / str(document["material_id"]) / "learning_material.json", document)

    def materialize_registry(self) -> list[Path]:
        try:
            registry = json.loads(self.registry_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as error:
            raise ValueError("invalid or unavailable V10 candidate registry") from error
        if registry.get("schema_version") != "10.0.0" or registry.get("document_type") != "learning_candidate_registry":
            raise ValueError("unsupported V10 candidate registry")
        candidates = registry.get("candidates")
        if not isinstance(candidates, list):
            raise ValueError("invalid V10 candidate registry candidates")
        return [self.materialize_candidate(candidate) for candidate in candidates if isinstance(candidate, Mapping)]

    def materialize_registry_async(self) -> Future:
        return self._executor.submit(self.materialize_registry)

    def shutdown(self) -> None:
        self._executor.shutdown(wait=True)
