"""Atomic, append-only canonical validation-record repository."""
from __future__ import annotations
import json, os, re, tempfile
from pathlib import Path
from learning.pattern_memory.memory_identity import digest
from .exceptions import PatternValidationError
from .models import ValidationRecord

_UUID = re.compile(r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$")


class PatternValidationRepository:
    def __init__(self, root: str | Path = "learning_data/pattern_validation"): self.root = Path(root)
    def path_for(self, value):
        if not isinstance(value, str) or not _UUID.fullmatch(value): raise PatternValidationError("INVALID_VALIDATION_FILENAME")
        return self.root / f"{value}.json"
    def save(self, record):
        if not isinstance(record, ValidationRecord): raise PatternValidationError("INVALID_VALIDATION_RECORD")
        path = self.path_for(record.validation_uuid); path.parent.mkdir(parents=True, exist_ok=True)
        data = json.dumps(record.to_dict(), sort_keys=True, separators=(",", ":"), allow_nan=False).encode()
        fd, name = tempfile.mkstemp(prefix=".pattern-validation-", dir=path.parent)
        try:
            with os.fdopen(fd, "wb") as stream: stream.write(data); stream.flush(); os.fsync(stream.fileno())
            try: os.link(name, path)
            except FileExistsError:
                if path.read_bytes() != data: raise PatternValidationError("VALIDATION_COLLISION") from None
        finally: Path(name).unlink(missing_ok=True)
        return path
    def records(self):
        if not self.root.exists(): return ()
        result = []
        for path in sorted(self.root.glob("*.json")):
            if not _UUID.fullmatch(path.stem): raise PatternValidationError("INVALID_VALIDATION_FILENAME")
            try: record = ValidationRecord(**json.loads(path.read_text()))
            except (OSError, ValueError, TypeError, json.JSONDecodeError) as exc: raise PatternValidationError("CORRUPT_VALIDATION_REPOSITORY") from exc
            if record.validation_uuid != path.stem: raise PatternValidationError("VALIDATION_FILENAME_IDENTITY_MISMATCH")
            result.append(record)
        uuids = [x.validation_uuid for x in result]
        if len(uuids) != len(set(uuids)): raise PatternValidationError("DUPLICATE_VALIDATION_HISTORY")
        return tuple(result)
    def digest(self):
        return digest([[x.validation_uuid, x.validation_digest] for x in self.records()])
