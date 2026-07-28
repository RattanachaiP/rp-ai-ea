"""Append-only canonical raw outcome-evidence repository."""
from __future__ import annotations

from hashlib import sha256
import json
import os
from pathlib import Path
import tempfile
from typing import Any
from uuid import UUID, uuid5

from .models import (OutcomeEvidenceError, OutcomeEvidenceManifest, RECORD_NAMESPACE,
                     canonical_json)


class OutcomeEvidenceRepository:
    def __init__(self, root: str | Path = "learning_data"):
        self.root = Path(root) / "outcome_evidence"

    def path_for(self, evidence_uuid: str) -> Path:
        return self.root / f"evidence_{evidence_uuid}.json"

    def make_record(self, manifest: OutcomeEvidenceManifest, source_digest: str,
                    replay_digest: str) -> dict[str, Any]:
        evidence_uuid = str(uuid5(RECORD_NAMESPACE, manifest.manifest_digest))
        payload = {"evidence_uuid": evidence_uuid, "manifest": manifest.to_dict(),
                   "source_digest": source_digest, "replay_digest": replay_digest}
        return {**payload, "record_digest": sha256(canonical_json(payload)).hexdigest()}

    def save(self, record: dict[str, Any]) -> tuple[Path, bool]:
        data = canonical_json(record)
        path = self.path_for(record["evidence_uuid"])
        self.root.mkdir(parents=True, exist_ok=True)
        if path.exists():
            if path.read_bytes() == data:
                self.load(record["evidence_uuid"])
                return path, False
            raise OutcomeEvidenceError("AMBIGUOUS_EVIDENCE_IDENTITY",
                                       "audit the identity collision; never overwrite canonical evidence")
        fd, temporary = tempfile.mkstemp(prefix=".evidence_", suffix=".tmp", dir=self.root)
        try:
            with os.fdopen(fd, "wb") as stream:
                stream.write(data); stream.flush(); os.fsync(stream.fileno())
            try:
                os.link(temporary, path)
            except FileExistsError:
                if path.read_bytes() != data:
                    raise OutcomeEvidenceError("AMBIGUOUS_EVIDENCE_IDENTITY",
                                               "audit the concurrent identity collision; never overwrite")
        finally:
            if os.path.exists(temporary):
                os.unlink(temporary)
        return path, True

    def load(self, evidence_uuid: str) -> dict[str, Any]:
        try:
            normalized_uuid = str(UUID(evidence_uuid))
        except (ValueError, TypeError, AttributeError) as exc:
            raise OutcomeEvidenceError("OUTCOME_EVIDENCE_IDENTITY_MISMATCH",
                                       "pass one exact evidence UUID returned by import") from exc
        path = self.path_for(normalized_uuid)
        if not path.is_file():
            raise OutcomeEvidenceError("OUTCOME_EVIDENCE_FILE_MISSING",
                                       "import the exact governed evidence file first")
        try:
            data = path.read_bytes()
            value = json.loads(data)
            if canonical_json(value) != data:
                raise ValueError("non-canonical bytes")
            manifest = OutcomeEvidenceManifest.from_dict(value["manifest"])
            expected_uuid = str(uuid5(RECORD_NAMESPACE, manifest.manifest_digest))
            payload = {key: value[key] for key in ("evidence_uuid", "manifest", "source_digest", "replay_digest")}
            expected_digest = sha256(canonical_json(payload)).hexdigest()
            if value["evidence_uuid"] != normalized_uuid or expected_uuid != normalized_uuid or value["record_digest"] != expected_digest:
                raise ValueError("identity or integrity mismatch")
        except (OSError, KeyError, TypeError, json.JSONDecodeError, ValueError, OutcomeEvidenceError) as exc:
            raise OutcomeEvidenceError("EVIDENCE_REPOSITORY_CORRUPT",
                                       "restore the exact canonical record from governed source and audit the repository") from exc
        return value

    def inspect(self) -> list[dict[str, Any]]:
        if not self.root.exists():
            return []
        result = []
        for path in sorted(self.root.glob("evidence_*.json")):
            identity = path.stem.removeprefix("evidence_")
            record = self.load(identity)
            result.append({"evidence_uuid": identity, "integrity_status": "VALID",
                           "source_digest": record["source_digest"],
                           "replay_digest": record["replay_digest"],
                           "manifest_digest": record["manifest"]["manifest_digest"]})
        return result
