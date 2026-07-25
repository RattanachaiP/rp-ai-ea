"""Atomic append-only records and chained PR177 repository snapshots."""
from __future__ import annotations
import json
import os
from pathlib import Path
import re
import tempfile
from .exceptions import PatternValidationError
from .identity import digest
from .models import PatternValidationSnapshot, ValidationRecord

_UUID = re.compile(r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$")


class PatternValidationRepository:
    def __init__(self, root: str | Path = "learning_data/pattern_validation"):
        self.root = Path(root)
        self.snapshot_root = self.root / "snapshots"

    def path_for(self, value):
        if not isinstance(value, str) or not _UUID.fullmatch(value):
            raise PatternValidationError("INVALID_VALIDATION_FILENAME")
        return self.root / f"{value}.json"

    def _append(self, path, data, collision, prefix):
        path.parent.mkdir(parents=True, exist_ok=True)
        descriptor, name = tempfile.mkstemp(prefix=prefix, dir=path.parent)
        temporary = Path(name)
        try:
            with os.fdopen(descriptor, "wb") as stream:
                stream.write(data); stream.flush(); os.fsync(stream.fileno())
            try:
                os.link(temporary, path)
            except FileExistsError:
                if path.read_bytes() != data:
                    raise PatternValidationError(collision) from None
        finally:
            temporary.unlink(missing_ok=True)
        return path

    def save(self, record):
        if not isinstance(record, ValidationRecord):
            raise PatternValidationError("INVALID_VALIDATION_RECORD")
        data = json.dumps(record.to_dict(), sort_keys=True, separators=(",", ":"), allow_nan=False).encode()
        return self._append(self.path_for(record.validation_uuid), data, "VALIDATION_COLLISION",
                            ".pattern-validation-")

    def records(self):
        return self._load(self.root, ValidationRecord, "VALIDATION", "validation_uuid")

    def save_snapshot(self, snapshot):
        if not isinstance(snapshot, PatternValidationSnapshot):
            raise PatternValidationError("INVALID_VALIDATION_SNAPSHOT")
        data = json.dumps(snapshot.to_dict(), sort_keys=True, separators=(",", ":"), allow_nan=False).encode()
        return self._append(self.snapshot_root / f"{snapshot.snapshot_uuid}.json", data,
                            "VALIDATION_SNAPSHOT_COLLISION", ".pattern-validation-snapshot-")

    def snapshots(self):
        return self._load(self.snapshot_root, PatternValidationSnapshot, "VALIDATION_SNAPSHOT", "snapshot_uuid")

    def _load(self, root, model, label, identity_field):
        if not root.exists():
            return ()
        result = []
        for path in sorted(root.glob("*.json")):
            if not _UUID.fullmatch(path.stem):
                raise PatternValidationError(f"INVALID_{label}_FILENAME")
            try:
                raw = json.loads(path.read_text(encoding="utf-8"))
                item = model(**raw)
            except (OSError, ValueError, TypeError, json.JSONDecodeError) as exc:
                raise PatternValidationError(f"CORRUPT_{label}_REPOSITORY") from exc
            if getattr(item, identity_field) != path.stem:
                raise PatternValidationError(f"{label}_FILENAME_IDENTITY_MISMATCH")
            result.append(item)
        return tuple(result)

    def latest_snapshot(self):
        snapshots = self.snapshots()
        if not snapshots:
            return None
        by_uuid = {x.snapshot_uuid: x for x in snapshots}
        referenced = {x.previous_snapshot_uuid for x in snapshots if x.previous_snapshot_uuid}
        heads = [x for x in snapshots if x.snapshot_uuid not in referenced]
        if len(heads) != 1:
            raise PatternValidationError("BROKEN_VALIDATION_SNAPSHOT_CHAIN")
        current, visited = heads[0], set()
        while current.previous_snapshot_uuid:
            if current.snapshot_uuid in visited or current.previous_snapshot_uuid not in by_uuid:
                raise PatternValidationError("BROKEN_VALIDATION_SNAPSHOT_CHAIN")
            previous = by_uuid[current.previous_snapshot_uuid]
            if previous.snapshot_digest != current.previous_snapshot_digest:
                raise PatternValidationError("BROKEN_VALIDATION_SNAPSHOT_CHAIN")
            visited.add(current.snapshot_uuid); current = previous
        if len(visited) + 1 != len(snapshots):
            raise PatternValidationError("BROKEN_VALIDATION_SNAPSHOT_CHAIN")
        return heads[0]

    def identities(self):
        return tuple((x.validation_uuid, x.validation_digest) for x in self.records())

    def digest(self):
        return digest([list(x) for x in self.identities()])
