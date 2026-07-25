"""Atomic append-only storage for PR180 packages and snapshots."""

import json
import os
import re
import tempfile
from pathlib import Path

from .exceptions import RuntimeKnowledgeError
from .identity import digest
from .models import RuntimeKnowledgePackage, RuntimeKnowledgeSnapshot


_UUID = re.compile(r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$")


class RuntimeKnowledgeRepository:
    def __init__(self, root="learning_data/runtime_knowledge"):
        self.root = Path(root)
        self.snapshot_root = self.root / "snapshots"

    @staticmethod
    def _bytes(value):
        return json.dumps(value.to_dict(), sort_keys=True, separators=(",", ":"),
                          allow_nan=False).encode()

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
                    raise RuntimeKnowledgeError(collision) from None
        finally:
            temporary.unlink(missing_ok=True)
        return path

    def path_for(self, identity):
        if not isinstance(identity, str) or not _UUID.fullmatch(identity):
            raise RuntimeKnowledgeError("INVALID_RUNTIME_PACKAGE_FILENAME")
        return self.root / f"{identity}.json"

    def save(self, package):
        if type(package) is not RuntimeKnowledgePackage:
            raise RuntimeKnowledgeError("INVALID_RUNTIME_KNOWLEDGE_PACKAGE")
        return self._append(self.path_for(package.runtime_package_uuid), self._bytes(package),
                            "RUNTIME_PACKAGE_COLLISION", ".package-")

    def save_snapshot(self, snapshot):
        if type(snapshot) is not RuntimeKnowledgeSnapshot:
            raise RuntimeKnowledgeError("INVALID_RUNTIME_KNOWLEDGE_SNAPSHOT")
        path = self.snapshot_root / f"{snapshot.snapshot_uuid}.json"
        return self._append(path, self._bytes(snapshot), "RUNTIME_SNAPSHOT_COLLISION", ".snapshot-")

    def _load(self, root, model, label, identity_field):
        if not root.exists():
            return ()
        result = []
        for path in sorted(root.glob("*.json")):
            if not _UUID.fullmatch(path.stem):
                raise RuntimeKnowledgeError(f"INVALID_{label}_FILENAME")
            try:
                item = model(**json.loads(path.read_text()))
            except (OSError, ValueError, TypeError, json.JSONDecodeError) as exc:
                raise RuntimeKnowledgeError(f"CORRUPT_{label}_REPOSITORY") from exc
            if getattr(item, identity_field) != path.stem:
                raise RuntimeKnowledgeError(f"{label}_FILENAME_IDENTITY_MISMATCH")
            result.append(item)
        return tuple(result)

    def packages(self):
        return self._load(self.root, RuntimeKnowledgePackage, "RUNTIME_PACKAGE",
                          "runtime_package_uuid")

    def snapshots(self):
        return self._load(self.snapshot_root, RuntimeKnowledgeSnapshot, "RUNTIME_SNAPSHOT",
                          "snapshot_uuid")

    def identities(self):
        return tuple((item.runtime_package_uuid, item.runtime_package_digest)
                     for item in self.packages())

    def digest(self):
        return digest([list(item) for item in self.identities()])

    def latest_snapshot(self):
        snapshots = self.snapshots()
        if not snapshots:
            return None
        by_uuid = {item.snapshot_uuid: item for item in snapshots}
        references = {item.previous_snapshot_uuid for item in snapshots
                      if item.previous_snapshot_uuid is not None}
        heads = [item for item in snapshots if item.snapshot_uuid not in references]
        if len(by_uuid) != len(snapshots) or len(heads) != 1:
            raise RuntimeKnowledgeError("BROKEN_RUNTIME_SNAPSHOT_CHAIN")
        head = current = heads[0]
        seen = set()
        partition = (head.runtime_policy_version, head.runtime_engine_version)
        while True:
            if current.snapshot_uuid in seen:
                raise RuntimeKnowledgeError("BROKEN_RUNTIME_SNAPSHOT_CHAIN")
            seen.add(current.snapshot_uuid)
            if (current.runtime_policy_version, current.runtime_engine_version) != partition:
                raise RuntimeKnowledgeError("MIXED_RUNTIME_PARTITION")
            if current.previous_snapshot_uuid is None:
                break
            previous = by_uuid.get(current.previous_snapshot_uuid)
            if previous is None or previous.snapshot_digest != current.previous_snapshot_digest:
                raise RuntimeKnowledgeError("BROKEN_RUNTIME_SNAPSHOT_CHAIN")
            current = previous
        if len(seen) != len(snapshots):
            raise RuntimeKnowledgeError("BROKEN_RUNTIME_SNAPSHOT_CHAIN")
        if head.package_identities != self.identities() or head.repository_digest != self.digest():
            raise RuntimeKnowledgeError("RUNTIME_SNAPSHOT_INTEGRITY_FAILURE")
        return head
