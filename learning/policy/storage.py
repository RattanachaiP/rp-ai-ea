"""Atomic append-only storage for policy evaluation reports."""
from __future__ import annotations

import json
import os
from pathlib import Path
import tempfile
from uuid import UUID

from .models import PolicyEvaluationReport


class PolicyEvaluationStorage:
    def __init__(self, root="learning_data"):
        self.root = Path(root) / "policy"
        self.root.mkdir(parents=True, exist_ok=True)

    def path_for(self, evaluation_uuid: str) -> Path:
        try:
            canonical = str(UUID(evaluation_uuid))
        except (AttributeError, ValueError) as exc:
            raise ValueError("INVALID_EVALUATION_UUID") from exc
        if canonical != evaluation_uuid.lower():
            raise ValueError("INVALID_EVALUATION_UUID")
        return self.root / f"evaluation_{canonical}.json"

    def _sync_directory(self) -> None:
        if os.name == "nt":
            return
        descriptor = os.open(self.root, os.O_RDONLY)
        try:
            os.fsync(descriptor)
        finally:
            os.close(descriptor)

    def write(self, report: PolicyEvaluationReport) -> Path:
        path = self.path_for(report.evaluation_uuid)
        data = json.dumps(report.to_dict(), sort_keys=True, separators=(",", ":"), allow_nan=False)
        if path.exists():
            if path.read_text(encoding="utf-8") == data:
                return path
            raise FileExistsError("POLICY_EVALUATION_IMMUTABLE")
        fd, name = tempfile.mkstemp(dir=self.root, prefix=f".{path.name}.", suffix=".tmp")
        temp = Path(name)
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as handle:
                handle.write(data)
                handle.flush()
                os.fsync(handle.fileno())
            try:
                os.link(temp, path)
            except FileExistsError as exc:
                if path.exists() and path.read_text(encoding="utf-8") == data:
                    return path
                raise FileExistsError("POLICY_EVALUATION_IMMUTABLE") from exc
            self._sync_directory()
            return path
        finally:
            temp.unlink(missing_ok=True)

    def all(self) -> tuple[PolicyEvaluationReport, ...]:
        reports = []
        for path in sorted(self.root.glob("evaluation_*.json")):
            try:
                payload = json.loads(path.read_text(encoding="utf-8"))
                report = PolicyEvaluationReport(**payload)
                if path != self.path_for(report.evaluation_uuid):
                    raise ValueError("POLICY_EVALUATION_ID_MISMATCH")
            except (OSError, UnicodeError, json.JSONDecodeError, TypeError, ValueError) as exc:
                raise ValueError(f"INVALID_POLICY_EVALUATION_RECORD:{path.name}") from exc
            reports.append(report)
        return tuple(reports)
