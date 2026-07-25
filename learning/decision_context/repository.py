"""Atomic append-only repository for PR183 contexts and snapshot chains."""

import json
import os
import re
import tempfile
from pathlib import Path

from .exceptions import DecisionContextError
from .identity import canonical_bytes, digest
from .models import DecisionContext, DecisionContextSnapshot

_UUID = re.compile(r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$")


class DecisionContextRepository:
    def __init__(self, root="learning_data/decision_context"):
        self.root = Path(root)
        self.snapshot_root = self.root / "snapshots"

    @staticmethod
    def _append(path, value, collision):
        data = canonical_bytes(value.to_dict())
        path.parent.mkdir(parents=True, exist_ok=True)
        descriptor, name = tempfile.mkstemp(prefix=".context-", dir=path.parent)
        temporary = Path(name)
        try:
            with os.fdopen(descriptor, "wb") as stream:
                stream.write(data)
                stream.flush()
                os.fsync(stream.fileno())
            try:
                os.link(temporary, path)
            except FileExistsError:
                if path.read_bytes() != data:
                    raise DecisionContextError(collision) from None
        finally:
            temporary.unlink(missing_ok=True)
        return path

    def save(self, value):
        if type(value) is not DecisionContext:
            raise DecisionContextError("INVALID_DECISION_CONTEXT")
        return self._append(
            self.root / f"{value.context_uuid}.json", value, "REPLAY_COLLISION"
        )

    def save_snapshot(self, value):
        if type(value) is not DecisionContextSnapshot:
            raise DecisionContextError("INVALID_CONTEXT_SNAPSHOT")
        return self._append(
            self.snapshot_root / f"{value.snapshot_uuid}.json",
            value,
            "REPLAY_COLLISION",
        )

    def _load(self, root, model, label, identity_field):
        if not root.exists():
            return ()
        output = []
        for path in sorted(root.glob("*.json")):
            if not _UUID.fullmatch(path.stem):
                raise DecisionContextError(f"INVALID_{label}_FILENAME")
            try:
                item = model(**json.loads(path.read_text()))
            except (OSError, ValueError, TypeError, KeyError, json.JSONDecodeError) as exc:
                raise DecisionContextError(f"CORRUPT_{label}_REPOSITORY") from exc
            if getattr(item, identity_field) != path.stem:
                raise DecisionContextError(f"{label}_FILENAME_IDENTITY_MISMATCH")
            if path.read_bytes() != canonical_bytes(item.to_dict()):
                raise DecisionContextError(f"NONCANONICAL_{label}_JSON")
            output.append(item)
        return tuple(output)

    def records(self):
        return self._load(self.root, DecisionContext, "DECISION_CONTEXT", "context_uuid")

    def snapshots(self):
        return self._load(
            self.snapshot_root,
            DecisionContextSnapshot,
            "CONTEXT_SNAPSHOT",
            "snapshot_uuid",
        )

    def identities(self):
        return tuple(
            (item.context_uuid, item.context_digest) for item in self.records()
        )

    def digest(self):
        return digest([list(item) for item in self.identities()])

    def latest_snapshot(self):
        snapshots = self.snapshots()
        if not snapshots:
            return None
        by_uuid = {item.snapshot_uuid: item for item in snapshots}
        references = {
            item.previous_snapshot_uuid
            for item in snapshots
            if item.previous_snapshot_uuid is not None
        }
        heads = [item for item in snapshots if item.snapshot_uuid not in references]
        if len(by_uuid) != len(snapshots) or len(heads) != 1:
            raise DecisionContextError("SNAPSHOT_MISMATCH")
        head = current = heads[0]
        seen = set()
        while True:
            if current.snapshot_uuid in seen:
                raise DecisionContextError("SNAPSHOT_MISMATCH")
            seen.add(current.snapshot_uuid)
            if current.previous_snapshot_uuid is None:
                break
            previous = by_uuid.get(current.previous_snapshot_uuid)
            if (
                previous is None
                or previous.snapshot_digest != current.previous_snapshot_digest
            ):
                raise DecisionContextError("SNAPSHOT_MISMATCH")
            current = previous
        if len(seen) != len(snapshots):
            raise DecisionContextError("SNAPSHOT_MISMATCH")
        if head.context_identities != self.identities():
            raise DecisionContextError("SNAPSHOT_MISMATCH")
        if head.repository_digest != self.digest():
            raise DecisionContextError("REPOSITORY_MISMATCH")
        return head
