"""Atomic append-only JSON persistence for governance metadata."""
from __future__ import annotations

import json
import os
from pathlib import Path

from .models import KnowledgeGovernance


class GovernanceStorage:
    def __init__(self, root: str | Path = "learning_data") -> None:
        self.root = Path(root)

    @property
    def directory(self) -> Path:
        return self.root / "governance"

    def path_for(self, knowledge_uuid: str, record_version: int) -> Path:
        if not knowledge_uuid or any(part in knowledge_uuid for part in ("/", "\\", "..")):
            raise ValueError("INVALID_KNOWLEDGE_UUID")
        if record_version < 1:
            raise ValueError("INVALID_RECORD_VERSION")
        return self.directory / f"governance_{knowledge_uuid}_{record_version}.json"

    def write(self, governance: KnowledgeGovernance) -> Path:
        path = self.path_for(governance.knowledge_uuid, governance.record_version)
        path.parent.mkdir(parents=True, exist_ok=True)
        payload = (json.dumps(governance.to_dict(), sort_keys=True, indent=2, allow_nan=False) + "\n").encode()
        if path.exists():
            if path.read_bytes() == payload:
                return path
            raise FileExistsError("GOVERNANCE_IMMUTABLE")
        temporary = path.with_suffix(".json.tmp")
        try:
            with temporary.open("xb") as handle:
                handle.write(payload)
                handle.flush()
                os.fsync(handle.fileno())
            os.link(temporary, path)
        except FileExistsError as exc:
            raise FileExistsError("GOVERNANCE_IMMUTABLE") from exc
        finally:
            if temporary.exists():
                temporary.unlink()
        return path

    def all(self) -> list[KnowledgeGovernance]:
        if not self.directory.exists():
            return []
        records: list[KnowledgeGovernance] = []
        for path in sorted(self.directory.glob("governance_*.json")):
            try:
                records.append(KnowledgeGovernance.from_dict(json.loads(path.read_text(encoding="utf-8"))))
            except (OSError, TypeError, ValueError, KeyError, json.JSONDecodeError):
                continue
        return records
