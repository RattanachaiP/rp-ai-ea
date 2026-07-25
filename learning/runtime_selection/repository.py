"""Atomic append-only PR181 eligibility repository with complete partitions."""

import json
import os
import re
import tempfile
from pathlib import Path

from .exceptions import RuntimeKnowledgeSelectionError
from .identity import digest
from .models import (
    PARTITION_FIELDS,
    RuntimeKnowledgeSelection,
    RuntimeKnowledgeSelectionSnapshot,
)

_UUID = re.compile(r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$")


class RuntimeKnowledgeSelectionRepository:
    def __init__(self, root="learning_data/runtime_selection"):
        self.root = Path(root)
        self.snapshot_root = self.root / "snapshots"

    @staticmethod
    def _bytes(value):
        return json.dumps(
            value.to_dict(), sort_keys=True, separators=(",", ":"), allow_nan=False
        ).encode()

    def _append(self, path, data, collision, prefix):
        path.parent.mkdir(parents=True, exist_ok=True)
        descriptor, name = tempfile.mkstemp(prefix=prefix, dir=path.parent)
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
                    raise RuntimeKnowledgeSelectionError(collision) from None
        finally:
            temporary.unlink(missing_ok=True)
        return path

    def path_for(self, identity):
        if not isinstance(identity, str) or not _UUID.fullmatch(identity):
            raise RuntimeKnowledgeSelectionError("INVALID_SELECTION_FILENAME")
        return self.root / f"{identity}.json"

    def save(self, value):
        if type(value) is not RuntimeKnowledgeSelection:
            raise RuntimeKnowledgeSelectionError("INVALID_RUNTIME_KNOWLEDGE_SELECTION")
        return self._append(
            self.path_for(value.selection_uuid),
            self._bytes(value),
            "SELECTION_COLLISION",
            ".selection-",
        )

    def save_snapshot(self, value):
        if type(value) is not RuntimeKnowledgeSelectionSnapshot:
            raise RuntimeKnowledgeSelectionError("INVALID_SELECTION_SNAPSHOT")
        return self._append(
            self.snapshot_root / f"{value.snapshot_uuid}.json",
            self._bytes(value),
            "SELECTION_SNAPSHOT_COLLISION",
            ".snapshot-",
        )

    def _load(self, root, model, label, field):
        if not root.exists():
            return ()
        output = []
        for path in sorted(root.glob("*.json")):
            if not _UUID.fullmatch(path.stem):
                raise RuntimeKnowledgeSelectionError(f"INVALID_{label}_FILENAME")
            try:
                item = model(**json.loads(path.read_text()))
            except (OSError, ValueError, TypeError, json.JSONDecodeError) as exc:
                raise RuntimeKnowledgeSelectionError(
                    f"CORRUPT_{label}_REPOSITORY"
                ) from exc
            if getattr(item, field) != path.stem:
                raise RuntimeKnowledgeSelectionError(
                    f"{label}_FILENAME_IDENTITY_MISMATCH"
                )
            output.append(item)
        return tuple(output)

    def selections(self):
        return self._load(
            self.root, RuntimeKnowledgeSelection, "SELECTION", "selection_uuid"
        )

    def snapshots(self):
        return self._load(
            self.snapshot_root,
            RuntimeKnowledgeSelectionSnapshot,
            "SELECTION_SNAPSHOT",
            "snapshot_uuid",
        )

    def identities(self):
        return tuple(
            (item.selection_uuid, item.selection_digest) for item in self.selections()
        )

    def digest(self):
        return digest([list(item) for item in self.identities()])

    def validate_partition(self, expected):
        selections = self.selections()
        snapshots = self.snapshots()
        expected_partition = tuple(expected[name] for name in PARTITION_FIELDS)
        for item in (*selections, *snapshots):
            if (
                tuple(getattr(item, name) for name in PARTITION_FIELDS)
                != expected_partition
            ):
                raise RuntimeKnowledgeSelectionError(
                    "MIXED_SELECTION_REPOSITORY_PARTITION"
                )
        return selections, self.latest_snapshot() if snapshots else None

    def latest_snapshot(self):
        snapshots = self.snapshots()
        if not snapshots:
            return None
        by_uuid = {item.snapshot_uuid: item for item in snapshots}
        references = {
            item.previous_snapshot_uuid
            for item in snapshots
            if item.previous_snapshot_uuid
        }
        heads = [item for item in snapshots if item.snapshot_uuid not in references]
        if len(by_uuid) != len(snapshots) or len(heads) != 1:
            raise RuntimeKnowledgeSelectionError("BROKEN_SELECTION_SNAPSHOT_CHAIN")
        head = current = heads[0]
        partition = tuple(getattr(head, name) for name in PARTITION_FIELDS)
        seen = set()
        while True:
            if (
                current.snapshot_uuid in seen
                or tuple(getattr(current, name) for name in PARTITION_FIELDS)
                != partition
            ):
                raise RuntimeKnowledgeSelectionError("BROKEN_SELECTION_SNAPSHOT_CHAIN")
            seen.add(current.snapshot_uuid)
            if not current.previous_snapshot_uuid:
                break
            previous = by_uuid.get(current.previous_snapshot_uuid)
            if (
                previous is None
                or previous.snapshot_digest != current.previous_snapshot_digest
            ):
                raise RuntimeKnowledgeSelectionError("BROKEN_SELECTION_SNAPSHOT_CHAIN")
            current = previous
        if len(seen) != len(snapshots):
            raise RuntimeKnowledgeSelectionError("BROKEN_SELECTION_SNAPSHOT_CHAIN")
        if head.selection_identities != self.identities():
            raise RuntimeKnowledgeSelectionError("SELECTION_SNAPSHOT_MISMATCH")
        if head.repository_digest != self.digest():
            raise RuntimeKnowledgeSelectionError("SELECTION_REPOSITORY_MISMATCH")
        return head
