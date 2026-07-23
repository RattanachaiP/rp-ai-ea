"""Atomic append-only JSON persistence for knowledge records."""
from __future__ import annotations

import json
import os
from time import monotonic
from pathlib import Path

from .knowledge import Knowledge


class KnowledgeStorage:
    def __init__(self, root: str | Path = "learning_data") -> None:
        self.root = Path(root)

    @property
    def directory(self) -> Path:
        return self.root / "knowledge"

    def path_for(self, knowledge_uuid: str) -> Path:
        if not knowledge_uuid or any(part in knowledge_uuid for part in ("/", "\\", "..")):
            raise ValueError("INVALID_KNOWLEDGE_UUID")
        return self.directory / f"knowledge_{knowledge_uuid}.json"

    def write(self, knowledge: Knowledge) -> Path:
        path = self.path_for(knowledge.knowledge_uuid)
        path.parent.mkdir(parents=True, exist_ok=True)
        if path.exists():
            if self.read(knowledge.knowledge_uuid).to_dict() == knowledge.to_dict():
                return path
            raise FileExistsError("KNOWLEDGE_IMMUTABLE")
        payload = (json.dumps(knowledge.to_dict(), sort_keys=True, indent=2, allow_nan=False) + "\n").encode()
        temporary = path.with_suffix(".json.tmp")
        try:
            with temporary.open("xb") as handle:
                handle.write(payload)
                handle.flush()
                os.fsync(handle.fileno())
            os.link(temporary, path)
        except FileExistsError as exc:
            raise FileExistsError("KNOWLEDGE_IMMUTABLE") from exc
        finally:
            if temporary.exists():
                temporary.unlink()
        return path

    def read(self, knowledge_uuid: str) -> Knowledge:
        with self.path_for(knowledge_uuid).open(encoding="utf-8") as handle:
            return Knowledge.from_dict(json.load(handle))

    def all(self, *, deadline_monotonic: float | None = None) -> list[Knowledge]:
        if not self.directory.exists():
            return []
        records: list[Knowledge] = []
        for path in sorted(self.directory.glob("knowledge_*.json")):
            if deadline_monotonic is not None and monotonic() > deadline_monotonic:
                raise TimeoutError("KNOWLEDGE_STORAGE_DEADLINE_EXCEEDED")
            try:
                records.append(Knowledge.from_dict(json.loads(path.read_text(encoding="utf-8"))))
            except (OSError, TypeError, ValueError, KeyError, json.JSONDecodeError):
                # A corrupt append-only record is unavailable to repository readers.
                continue
        return records
