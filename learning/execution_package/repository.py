"""Atomic append-only PR189 package and snapshot repository."""

import json
import os
import re
import tempfile
from pathlib import Path
from .exceptions import ExecutionPackageError
from .identity import canonical_bytes, digest
from .models import ExecutionPackage, ExecutionPackageSnapshot

_UUID = re.compile(r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$")


class ExecutionPackageRepository:
    def __init__(self, root="learning_data/execution_package"):
        self.root = Path(root)
        self.snapshot_root = self.root / "snapshots"

    @staticmethod
    def _append(path, value):
        data = canonical_bytes(value.to_dict())
        path.parent.mkdir(parents=True, exist_ok=True)
        descriptor, name = tempfile.mkstemp(prefix=".package-", dir=path.parent)
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
                    raise ExecutionPackageError("REPLAY_COLLISION") from None
        finally:
            temporary.unlink(missing_ok=True)
        return path

    def save(self, value):
        if type(value) is not ExecutionPackage:
            raise ExecutionPackageError("PACKAGE_ASSEMBLY_FAILURE")
        return self._append(self.root / f"{value.execution_package_uuid}.json", value)

    def save_snapshot(self, value):
        if type(value) is not ExecutionPackageSnapshot:
            raise ExecutionPackageError("PACKAGE_ASSEMBLY_FAILURE")
        return self._append(self.snapshot_root / f"{value.snapshot_uuid}.json", value)

    def _load(self, root, model, label, field):
        if not root.exists():
            return ()
        output = []
        for path in sorted(root.glob("*.json")):
            if not _UUID.fullmatch(path.stem):
                raise ExecutionPackageError("REPOSITORY_MISMATCH")
            try:
                item = model(**json.loads(path.read_text()))
            except (OSError, ValueError, TypeError, KeyError, json.JSONDecodeError) as exc:
                raise ExecutionPackageError("REPOSITORY_MISMATCH") from exc
            if getattr(item, field) != path.stem or path.read_bytes() != canonical_bytes(item.to_dict()):
                raise ExecutionPackageError("REPOSITORY_MISMATCH")
            output.append(item)
        return tuple(output)

    def records(self):
        return self._load(self.root, ExecutionPackage, "EXECUTION_PACKAGE", "execution_package_uuid")

    def snapshots(self):
        return self._load(self.snapshot_root, ExecutionPackageSnapshot, "EXECUTION_PACKAGE_SNAPSHOT", "snapshot_uuid")

    def identities(self):
        return tuple((value.execution_package_uuid, value.execution_package_digest) for value in self.records())

    def digest(self):
        return digest([list(value) for value in self.identities()])

    def latest_snapshot(self):
        snapshots = self.snapshots()
        if not snapshots:
            return None
        by_uuid = {value.snapshot_uuid: value for value in snapshots}
        references = {value.previous_snapshot_uuid for value in snapshots if value.previous_snapshot_uuid}
        heads = [value for value in snapshots if value.snapshot_uuid not in references]
        if len(by_uuid) != len(snapshots) or len(heads) != 1:
            raise ExecutionPackageError("SNAPSHOT_MISMATCH")
        head = current = heads[0]
        seen = set()
        partition = (head.package_policy_uuid, head.package_policy_digest,
                     head.package_policy_version, head.package_engine_version)
        while True:
            if current.snapshot_uuid in seen:
                raise ExecutionPackageError("SNAPSHOT_MISMATCH")
            seen.add(current.snapshot_uuid)
            actual = (current.package_policy_uuid, current.package_policy_digest,
                      current.package_policy_version, current.package_engine_version)
            if actual[3] != partition[3]:
                raise ExecutionPackageError("ENGINE_VERSION_MISMATCH")
            if actual != partition:
                raise ExecutionPackageError("POLICY_MISMATCH")
            if current.previous_snapshot_uuid is None:
                break
            previous = by_uuid.get(current.previous_snapshot_uuid)
            if previous is None or previous.snapshot_digest != current.previous_snapshot_digest:
                raise ExecutionPackageError("SNAPSHOT_MISMATCH")
            current = previous
        if len(seen) != len(snapshots) or head.package_identities != self.identities():
            raise ExecutionPackageError("SNAPSHOT_MISMATCH")
        if head.repository_digest != self.digest():
            raise ExecutionPackageError("REPOSITORY_MISMATCH")
        return head
