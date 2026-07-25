"""Atomic append-only storage for records and chained repository snapshots."""
from __future__ import annotations
import json
import os
from pathlib import Path
import re
import tempfile
from typing import Any
from .exceptions import PatternMemoryError
from .models import PatternMemoryRecord, PatternMemorySnapshot

_UUID = re.compile(r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$")


class PatternMemoryRepository:
    def __init__(self, root: str | Path = "learning_data/pattern_memory"):
        self.root = Path(root)
        self.snapshot_root = self.root / "snapshots"

    def path_for(self, memory_uuid: str) -> Path:
        if not isinstance(memory_uuid, str) or not _UUID.fullmatch(memory_uuid):
            raise PatternMemoryError("INVALID_MEMORY_FILENAME")
        return self.root / f"{memory_uuid}.json"

    def _atomic_append(self, path: Path, payload: bytes, collision: str, prefix: str) -> Path:
        path.parent.mkdir(parents=True, exist_ok=True)
        descriptor, name = tempfile.mkstemp(prefix=prefix, dir=path.parent)
        temporary = Path(name)
        try:
            with os.fdopen(descriptor, "wb") as stream:
                stream.write(payload)
                stream.flush()
                os.fsync(stream.fileno())
            try:
                os.link(temporary, path)
            except FileExistsError:
                if path.read_bytes() != payload:
                    raise PatternMemoryError(collision) from None
        finally:
            temporary.unlink(missing_ok=True)
        return path

    def save(self, record: PatternMemoryRecord) -> Path:
        if not isinstance(record, PatternMemoryRecord):
            raise PatternMemoryError("INVALID_PATTERN_MEMORY_RECORD")
        payload = json.dumps(record.to_dict(), sort_keys=True, separators=(",", ":"), allow_nan=False).encode()
        return self._atomic_append(self.path_for(record.memory_uuid), payload, "MEMORY_COLLISION", ".pattern-memory-")

    def records(self) -> tuple[PatternMemoryRecord, ...]:
        if not self.root.exists():
            return ()
        records = []
        for path in sorted(self.root.glob("*.json")):
            if not _UUID.fullmatch(path.stem):
                raise PatternMemoryError("INVALID_MEMORY_FILENAME")
            try:
                raw = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError, TypeError, ValueError) as exc:
                raise PatternMemoryError("CORRUPT_PATTERN_MEMORY") from exc
            if not isinstance(raw, dict):
                raise PatternMemoryError("CORRUPT_PATTERN_MEMORY")
            if raw.get("memory_uuid") != path.stem:
                raise PatternMemoryError("MEMORY_FILENAME_IDENTITY_MISMATCH")
            try:
                record = PatternMemoryRecord(**raw)
            except (TypeError, ValueError) as exc:
                raise PatternMemoryError("CORRUPT_PATTERN_MEMORY") from exc
            records.append(record)
        return tuple(records)

    def save_snapshot(self, snapshot: PatternMemorySnapshot) -> Path:
        if not isinstance(snapshot, PatternMemorySnapshot):
            raise PatternMemoryError("INVALID_PATTERN_MEMORY_SNAPSHOT")
        path = self.snapshot_root / f"{snapshot.snapshot_uuid}.json"
        payload = json.dumps(snapshot.to_dict(), sort_keys=True, separators=(",", ":"), allow_nan=False).encode()
        return self._atomic_append(path, payload, "SNAPSHOT_COLLISION", ".pattern-memory-snapshot-")

    def snapshots(self) -> tuple[PatternMemorySnapshot, ...]:
        if not self.snapshot_root.exists():
            return ()
        snapshots = []
        for path in sorted(self.snapshot_root.glob("*.json")):
            if not _UUID.fullmatch(path.stem):
                raise PatternMemoryError("INVALID_SNAPSHOT_FILENAME")
            try:
                snapshot = PatternMemorySnapshot(**json.loads(path.read_text(encoding="utf-8")))
            except (OSError, json.JSONDecodeError, TypeError, ValueError) as exc:
                raise PatternMemoryError("CORRUPT_PATTERN_MEMORY_SNAPSHOT") from exc
            if snapshot.snapshot_uuid != path.stem:
                raise PatternMemoryError("SNAPSHOT_FILENAME_IDENTITY_MISMATCH")
            snapshots.append(snapshot)
        return tuple(snapshots)

    def latest_snapshot(self) -> PatternMemorySnapshot | None:
        snapshots = self.snapshots()
        if not snapshots:
            return None
        previous = {item.previous_snapshot_uuid for item in snapshots if item.previous_snapshot_uuid}
        heads = [item for item in snapshots if item.snapshot_uuid not in previous]
        if len(heads) != 1:
            raise PatternMemoryError("BROKEN_SNAPSHOT_CHAIN")
        by_uuid = {item.snapshot_uuid: item for item in snapshots}
        current = heads[0]
        visited = set()
        while current.previous_snapshot_uuid:
            if current.snapshot_uuid in visited or current.previous_snapshot_uuid not in by_uuid:
                raise PatternMemoryError("BROKEN_SNAPSHOT_CHAIN")
            previous_snapshot = by_uuid[current.previous_snapshot_uuid]
            if previous_snapshot.snapshot_digest != current.previous_snapshot_digest:
                raise PatternMemoryError("BROKEN_SNAPSHOT_CHAIN")
            visited.add(current.snapshot_uuid)
            current = previous_snapshot
        if len(visited) + 1 != len(snapshots):
            raise PatternMemoryError("BROKEN_SNAPSHOT_CHAIN")
        return heads[0]
