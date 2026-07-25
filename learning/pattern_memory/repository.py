"""Atomic, append-only, replay-safe canonical Pattern Memory storage."""
from __future__ import annotations

import json
import os
from pathlib import Path
import re
import tempfile

from .exceptions import PatternMemoryError
from .models import PatternMemoryRecord

_UUID = re.compile(r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$")


class PatternMemoryRepository:
    def __init__(self, root: str | Path = "learning_data/pattern_memory"):
        self.root = Path(root)

    def path_for(self, memory_uuid: str) -> Path:
        if not isinstance(memory_uuid, str) or not _UUID.fullmatch(memory_uuid):
            raise PatternMemoryError("INVALID_MEMORY_FILENAME")
        return self.root / f"{memory_uuid}.json"

    def save(self, record: PatternMemoryRecord) -> Path:
        if not isinstance(record, PatternMemoryRecord):
            raise PatternMemoryError("INVALID_PATTERN_MEMORY_RECORD")
        path = self.path_for(record.memory_uuid)
        payload = json.dumps(record.to_dict(), sort_keys=True, separators=(",", ":"), allow_nan=False).encode()
        self.root.mkdir(parents=True, exist_ok=True)
        descriptor, name = tempfile.mkstemp(prefix=".pattern-memory-", dir=self.root)
        temporary = Path(name)
        try:
            with os.fdopen(descriptor, "wb") as stream:
                stream.write(payload); stream.flush(); os.fsync(stream.fileno())
            try:
                os.link(temporary, path)
            except FileExistsError:
                if path.read_bytes() != payload:
                    raise PatternMemoryError("MEMORY_COLLISION") from None
        finally:
            temporary.unlink(missing_ok=True)
        return path

    def records(self) -> tuple[PatternMemoryRecord, ...]:
        if not self.root.exists():
            return ()
        records = []
        for path in sorted(self.root.glob("*.json")):
            if not _UUID.fullmatch(path.stem):
                raise PatternMemoryError("INVALID_MEMORY_FILENAME")
            try:
                record = PatternMemoryRecord(**json.loads(path.read_text(encoding="utf-8")))
            except (OSError, json.JSONDecodeError, TypeError, ValueError) as exc:
                raise PatternMemoryError("CORRUPT_PATTERN_MEMORY") from exc
            if record.memory_uuid != path.stem:
                raise PatternMemoryError("MEMORY_FILENAME_IDENTITY_MISMATCH")
            records.append(record)
        return tuple(records)
