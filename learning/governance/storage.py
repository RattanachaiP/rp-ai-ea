"""Atomic append-only JSON persistence for governance metadata."""
from __future__ import annotations

import json
import os
from pathlib import Path
from uuid import uuid4

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

    @staticmethod
    def _fsync_directory(directory: Path) -> None:
        """Best-effort directory sync after publishing a new immutable entry."""
        flags = os.O_RDONLY | getattr(os, "O_DIRECTORY", 0)
        try:
            descriptor = os.open(directory, flags)
        except OSError:
            return
        try:
            os.fsync(descriptor)
        except OSError:
            # Some platforms/filesystems do not support syncing directories.
            pass
        finally:
            os.close(descriptor)

    def write(self, governance: KnowledgeGovernance) -> Path:
        path = self.path_for(governance.knowledge_uuid, governance.record_version)
        path.parent.mkdir(parents=True, exist_ok=True)
        payload = (
            json.dumps(governance.to_dict(), sort_keys=True, indent=2, allow_nan=False) + "\n"
        ).encode("utf-8")

        if path.exists():
            if path.read_bytes() == payload:
                return path
            raise FileExistsError("GOVERNANCE_IMMUTABLE")

        temporary = path.with_name(f".{path.name}.{uuid4().hex}.tmp")
        try:
            with temporary.open("xb") as handle:
                handle.write(payload)
                handle.flush()
                os.fsync(handle.fileno())
            try:
                os.link(temporary, path)
            except FileExistsError as exc:
                # A concurrent writer may have published the exact same immutable
                # revision. Treat identical publication as idempotent replay.
                if path.exists() and path.read_bytes() == payload:
                    return path
                raise FileExistsError("GOVERNANCE_IMMUTABLE") from exc
            self._fsync_directory(path.parent)
        finally:
            try:
                temporary.unlink()
            except FileNotFoundError:
                pass
        return path

    def all(self) -> list[KnowledgeGovernance]:
        if not self.directory.exists():
            return []
        records: list[KnowledgeGovernance] = []
        for path in sorted(self.directory.glob("governance_*.json")):
            try:
                records.append(
                    KnowledgeGovernance.from_dict(
                        json.loads(path.read_text(encoding="utf-8"))
                    )
                )
            except (OSError, TypeError, ValueError, KeyError, json.JSONDecodeError):
                continue
        return records
