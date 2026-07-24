"""Atomic append-only storage for trusted registry events."""
from __future__ import annotations

import json
import os
from pathlib import Path
from uuid import UUID, uuid4

from .models import ActiveKnowledgeEntry


class ActiveRegistryStorage:
    def __init__(self, root: str | Path = "learning_data") -> None:
        self.root = Path(root)

    @property
    def directory(self) -> Path:
        return self.root / "active_registry"

    def path_for(self, activation_uuid: str) -> Path:
        try:
            canonical = str(UUID(activation_uuid))
        except (ValueError, TypeError, AttributeError) as exc:
            raise ValueError("INVALID_ACTIVATION_UUID") from exc
        return self.directory / f"entry_{canonical}.json"

    def write(self, entry: ActiveKnowledgeEntry) -> Path:
        path = self.path_for(entry.activation_uuid)
        data = (
            json.dumps(entry.to_dict(), sort_keys=True, separators=(",", ":"), allow_nan=False) + "\n"
        ).encode("utf-8")
        path.parent.mkdir(parents=True, exist_ok=True)
        if path.exists():
            if path.read_bytes() == data:
                return path
            raise FileExistsError("ACTIVE_REGISTRY_APPEND_ONLY")
        tmp = path.with_name(f".{path.name}.{uuid4().hex}.tmp")
        try:
            with tmp.open("xb") as handle:
                handle.write(data)
                handle.flush()
                os.fsync(handle.fileno())
            try:
                os.link(tmp, path)
            except FileExistsError as exc:
                if path.exists() and path.read_bytes() == data:
                    return path
                raise FileExistsError("ACTIVE_REGISTRY_APPEND_ONLY") from exc
        finally:
            tmp.unlink(missing_ok=True)
        return path

    def all(self) -> tuple[ActiveKnowledgeEntry, ...]:
        if not self.directory.exists():
            return ()
        records: list[ActiveKnowledgeEntry] = []
        for path in sorted(self.directory.glob("entry_*.json")):
            try:
                payload = json.loads(path.read_text(encoding="utf-8"))
                records.append(ActiveKnowledgeEntry(**payload))
            except (OSError, ValueError, TypeError, KeyError, json.JSONDecodeError) as exc:
                raise RuntimeError(f"ACTIVE_REGISTRY_CORRUPTED:{path.name}") from exc
        ordered = tuple(sorted(records, key=lambda item: (item.sequence, item.activation_uuid)))
        sequences = [entry.sequence for entry in ordered]
        if len(sequences) != len(set(sequences)):
            raise RuntimeError("ACTIVE_REGISTRY_DUPLICATE_SEQUENCE")
        return ordered

    def by_receipt(self, receipt_uuid: str) -> ActiveKnowledgeEntry | None:
        return next((entry for entry in self.all() if entry.source_receipt_uuid == receipt_uuid), None)
