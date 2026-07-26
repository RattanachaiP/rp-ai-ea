"""Atomic append-only PR188 record and snapshot repository."""

import json
import os
import re
import tempfile
from pathlib import Path
from .exceptions import ExecutionFeasibilityError
from .identity import canonical_bytes, digest
from .models import ExecutionFeasibilityRecord, ExecutionFeasibilitySnapshot

_UUID = re.compile(r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$")


class ExecutionFeasibilityRepository:
    def __init__(self, root="learning_data/execution_feasibility"):
        self.root = Path(root)
        self.snapshot_root = self.root / "snapshots"

    @staticmethod
    def _append(path, value):
        data = canonical_bytes(value.to_dict())
        path.parent.mkdir(parents=True, exist_ok=True)
        descriptor, name = tempfile.mkstemp(prefix=".feasibility-", dir=path.parent)
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
                    raise ExecutionFeasibilityError("REPLAY_COLLISION") from None
        finally:
            temporary.unlink(missing_ok=True)
        return path

    def save(self, value):
        if type(value) is not ExecutionFeasibilityRecord:
            raise ExecutionFeasibilityError("INVALID_EXECUTION_FEASIBILITY")
        return self._append(self.root / f"{value.execution_feasibility_uuid}.json", value)

    def save_snapshot(self, value):
        if type(value) is not ExecutionFeasibilitySnapshot:
            raise ExecutionFeasibilityError("INVALID_EXECUTION_FEASIBILITY_SNAPSHOT")
        return self._append(self.snapshot_root / f"{value.snapshot_uuid}.json", value)

    def _load(self, root, model, label, field):
        if not root.exists():
            return ()
        output = []
        for path in sorted(root.glob("*.json")):
            if not _UUID.fullmatch(path.stem):
                raise ExecutionFeasibilityError(f"INVALID_{label}_FILENAME")
            try:
                item = model(**json.loads(path.read_text()))
            except (OSError, ValueError, TypeError, KeyError, json.JSONDecodeError) as exc:
                raise ExecutionFeasibilityError(f"CORRUPT_{label}_REPOSITORY") from exc
            if getattr(item, field) != path.stem:
                raise ExecutionFeasibilityError(f"{label}_FILENAME_IDENTITY_MISMATCH")
            if path.read_bytes() != canonical_bytes(item.to_dict()):
                raise ExecutionFeasibilityError(f"NONCANONICAL_{label}_JSON")
            output.append(item)
        return tuple(output)

    def records(self):
        return self._load(self.root, ExecutionFeasibilityRecord, "EXECUTION_FEASIBILITY", "execution_feasibility_uuid")

    def snapshots(self):
        return self._load(self.snapshot_root, ExecutionFeasibilitySnapshot, "EXECUTION_FEASIBILITY_SNAPSHOT", "snapshot_uuid")

    def identities(self):
        return tuple((x.execution_feasibility_uuid, x.execution_feasibility_digest) for x in self.records())

    def digest(self):
        return digest([list(x) for x in self.identities()])

    def latest_snapshot(self):
        snapshots = self.snapshots()
        if not snapshots:
            return None
        by_uuid = {x.snapshot_uuid: x for x in snapshots}
        references = {x.previous_snapshot_uuid for x in snapshots if x.previous_snapshot_uuid}
        heads = [x for x in snapshots if x.snapshot_uuid not in references]
        if len(by_uuid) != len(snapshots) or len(heads) != 1:
            raise ExecutionFeasibilityError("SNAPSHOT_MISMATCH")
        head = current = heads[0]
        seen = set()
        partition = (head.feasibility_policy_uuid, head.feasibility_policy_digest,
                     head.feasibility_policy_version, head.feasibility_engine_version)
        while True:
            if current.snapshot_uuid in seen:
                raise ExecutionFeasibilityError("SNAPSHOT_MISMATCH")
            seen.add(current.snapshot_uuid)
            actual = (current.feasibility_policy_uuid, current.feasibility_policy_digest,
                      current.feasibility_policy_version, current.feasibility_engine_version)
            if actual[3] != partition[3]:
                raise ExecutionFeasibilityError("ENGINE_VERSION_MISMATCH")
            if actual != partition:
                raise ExecutionFeasibilityError("POLICY_MISMATCH")
            if current.previous_snapshot_uuid is None:
                break
            previous = by_uuid.get(current.previous_snapshot_uuid)
            if previous is None or previous.snapshot_digest != current.previous_snapshot_digest:
                raise ExecutionFeasibilityError("SNAPSHOT_MISMATCH")
            current = previous
        if len(seen) != len(snapshots) or head.feasibility_identities != self.identities():
            raise ExecutionFeasibilityError("SNAPSHOT_MISMATCH")
        if head.repository_digest != self.digest():
            raise ExecutionFeasibilityError("REPOSITORY_MISMATCH")
        return head
