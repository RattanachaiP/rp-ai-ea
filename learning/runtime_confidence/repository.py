"""Atomic append-only PR182 repository with governed partition integrity."""

import json
import os
import re
import tempfile
from pathlib import Path

from .exceptions import RuntimeConfidenceError
from .identity import digest
from .models import (
    PARTITION_FIELDS,
    ConfidenceDimensionResult,
    ConfidenceRecord,
    ConfidenceSnapshot,
)

_UUID = re.compile(r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$")


class RuntimeConfidenceRepository:
    def __init__(self, root="learning_data/runtime_confidence"):
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
                    raise RuntimeConfidenceError(collision) from None
        finally:
            temporary.unlink(missing_ok=True)
        return path

    def path_for(self, identity):
        if not isinstance(identity, str) or not _UUID.fullmatch(identity):
            raise RuntimeConfidenceError("INVALID_CONFIDENCE_FILENAME")
        return self.root / f"{identity}.json"

    def save(self, value):
        if type(value) is not ConfidenceRecord:
            raise RuntimeConfidenceError("INVALID_CONFIDENCE_EVIDENCE")
        return self._append(
            self.path_for(value.confidence_uuid),
            self._bytes(value),
            "REPLAY_COLLISION",
            ".confidence-",
        )

    def save_snapshot(self, value):
        if type(value) is not ConfidenceSnapshot:
            raise RuntimeConfidenceError("INVALID_CONFIDENCE_EVIDENCE")
        return self._append(
            self.snapshot_root / f"{value.snapshot_uuid}.json",
            self._bytes(value),
            "REPLAY_COLLISION",
            ".snapshot-",
        )

    def _load(self, root, model, label, identity_field):
        if not root.exists():
            return ()
        output = []
        for path in sorted(root.glob("*.json")):
            if not _UUID.fullmatch(path.stem):
                raise RuntimeConfidenceError(f"INVALID_{label}_FILENAME")
            try:
                values = json.loads(path.read_text())
                if model is ConfidenceRecord:
                    values["confidence_dimension_results"] = tuple(
                        ConfidenceDimensionResult(**item)
                        for item in values["confidence_dimension_results"]
                    )
                item = model(**values)
            except (
                OSError,
                ValueError,
                TypeError,
                KeyError,
                json.JSONDecodeError,
            ) as exc:
                raise RuntimeConfidenceError(f"CORRUPT_{label}_REPOSITORY") from exc
            if getattr(item, identity_field) != path.stem:
                raise RuntimeConfidenceError(f"{label}_FILENAME_IDENTITY_MISMATCH")
            if path.read_bytes() != self._bytes(item):
                raise RuntimeConfidenceError(f"CORRUPT_{label}_REPOSITORY")
            output.append(item)
        return tuple(output)

    def records(self):
        return self._load(self.root, ConfidenceRecord, "CONFIDENCE", "confidence_uuid")

    def snapshots(self):
        return self._load(
            self.snapshot_root,
            ConfidenceSnapshot,
            "CONFIDENCE_SNAPSHOT",
            "snapshot_uuid",
        )

    def identities(self):
        return tuple(
            (item.confidence_uuid, item.confidence_digest) for item in self.records()
        )

    def digest(self):
        return digest([list(item) for item in self.identities()])

    def validate_partition(self, expected):
        records = self.records()
        snapshots = self.snapshots()
        expected_partition = tuple(expected[name] for name in PARTITION_FIELDS)
        for item in (*records, *snapshots):
            actual = tuple(getattr(item, name) for name in PARTITION_FIELDS)
            if actual != expected_partition:
                if actual[:4] != expected_partition[:4]:
                    raise RuntimeConfidenceError("POLICY_MISMATCH")
                if actual[4:8] != expected_partition[4:8]:
                    raise RuntimeConfidenceError("UPSTREAM_PARTITION_MISMATCH")
                raise RuntimeConfidenceError("UPSTREAM_PARTITION_MISMATCH")
        return records, self.latest_snapshot() if snapshots else None

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
            raise RuntimeConfidenceError("CORRUPT_CONFIDENCE_SNAPSHOT_REPOSITORY")
        head = current = heads[0]
        seen = set()
        partition = tuple(getattr(head, name) for name in PARTITION_FIELDS)
        while True:
            if current.snapshot_uuid in seen:
                raise RuntimeConfidenceError("CORRUPT_CONFIDENCE_SNAPSHOT_REPOSITORY")
            if tuple(getattr(current, name) for name in PARTITION_FIELDS) != partition:
                raise RuntimeConfidenceError("UPSTREAM_PARTITION_MISMATCH")
            seen.add(current.snapshot_uuid)
            if current.previous_snapshot_uuid is None:
                break
            previous = by_uuid.get(current.previous_snapshot_uuid)
            if (
                previous is None
                or previous.snapshot_digest != current.previous_snapshot_digest
            ):
                raise RuntimeConfidenceError("CORRUPT_CONFIDENCE_SNAPSHOT_REPOSITORY")
            current = previous
        if len(seen) != len(snapshots):
            raise RuntimeConfidenceError("CORRUPT_CONFIDENCE_SNAPSHOT_REPOSITORY")
        if head.confidence_identities != self.identities():
            raise RuntimeConfidenceError("SNAPSHOT_MISMATCH")
        if head.repository_digest != self.digest():
            raise RuntimeConfidenceError("REPOSITORY_MISMATCH")
        return head
