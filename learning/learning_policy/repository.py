"""Append-only, atomic persistence for governed learning-policy reports."""
from __future__ import annotations

import json
import os
from pathlib import Path
import tempfile

from .models import GovernedLearningPolicyReport


class GovernedLearningPolicyRepository:
    """Stores canonical reports only; existing differing content is rejected."""

    def __init__(self, root: str | Path = "learning_data") -> None:
        self.root = Path(root) / "learning_policy"
        self.root.mkdir(parents=True, exist_ok=True)

    def path_for(self, policy_uuid: str) -> Path:
        return self.root / f"report_{policy_uuid}.json"

    def save(self, report: GovernedLearningPolicyReport) -> Path:
        if not isinstance(report, GovernedLearningPolicyReport):
            raise TypeError("INVALID_GOVERNED_LEARNING_POLICY_REPORT")
        data = json.dumps(report.to_dict(), sort_keys=True, separators=(",", ":"), allow_nan=False).encode()
        path = self.path_for(report.policy_uuid)
        if path.exists():
            if path.read_bytes() == data:
                return path
            raise FileExistsError("APPEND_ONLY_REPORT_COLLISION")
        fd, temporary = tempfile.mkstemp(prefix=".report_", suffix=".tmp", dir=self.root)
        try:
            with os.fdopen(fd, "wb") as handle:
                handle.write(data)
                handle.flush()
                os.fsync(handle.fileno())
            try:
                os.link(temporary, path)
            except FileExistsError:
                if path.read_bytes() != data:
                    raise FileExistsError("APPEND_ONLY_REPORT_COLLISION")
        finally:
            if os.path.exists(temporary):
                os.unlink(temporary)
        return path
