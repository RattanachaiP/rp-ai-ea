"""Atomic append-only storage and snapshot-chain validation for PR179."""
import json
import os
from pathlib import Path
import re
import tempfile
from .exceptions import KnowledgeRegistryError
from .identity import digest
from .models import KnowledgeRegistrySnapshot, RegistryRecord

_UUID = re.compile(r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$")


class KnowledgeRegistryRepository:
    def __init__(self, root="learning_data/knowledge_registry"):
        self.root = Path(root); self.snapshot_root = self.root / "snapshots"

    @staticmethod
    def _bytes(value):
        return json.dumps(value.to_dict(), sort_keys=True, separators=(",", ":"), allow_nan=False).encode()

    def _append(self, path, data, collision, prefix):
        path.parent.mkdir(parents=True, exist_ok=True)
        descriptor, name = tempfile.mkstemp(prefix=prefix, dir=path.parent); temporary = Path(name)
        try:
            with os.fdopen(descriptor, "wb") as stream:
                stream.write(data); stream.flush(); os.fsync(stream.fileno())
            try: os.link(temporary, path)
            except FileExistsError:
                if path.read_bytes() != data: raise KnowledgeRegistryError(collision) from None
        finally: temporary.unlink(missing_ok=True)
        return path

    def path_for(self, identifier):
        if not isinstance(identifier, str) or not _UUID.fullmatch(identifier):
            raise KnowledgeRegistryError("INVALID_REGISTRY_FILENAME")
        return self.root / f"{identifier}.json"

    def save(self, record):
        if type(record) is not RegistryRecord: raise KnowledgeRegistryError("INVALID_REGISTRY_RECORD")
        return self._append(self.path_for(record.registry_uuid), self._bytes(record),
                            "REGISTRY_COLLISION", ".knowledge-registry-")

    def save_snapshot(self, snapshot):
        if type(snapshot) is not KnowledgeRegistrySnapshot:
            raise KnowledgeRegistryError("INVALID_REGISTRY_SNAPSHOT")
        path = self.snapshot_root / f"{snapshot.snapshot_uuid}.json"
        return self._append(path, self._bytes(snapshot), "REGISTRY_SNAPSHOT_COLLISION",
                            ".knowledge-registry-snapshot-")

    def _load(self, root, model, label, field):
        if not root.exists(): return ()
        result = []
        for path in sorted(root.glob("*.json")):
            if not _UUID.fullmatch(path.stem): raise KnowledgeRegistryError(f"INVALID_{label}_FILENAME")
            try: item = model(**json.loads(path.read_text(encoding="utf-8")))
            except (OSError, ValueError, TypeError, json.JSONDecodeError) as exc:
                raise KnowledgeRegistryError(f"CORRUPT_{label}_REPOSITORY") from exc
            if getattr(item, field) != path.stem:
                raise KnowledgeRegistryError(f"{label}_FILENAME_IDENTITY_MISMATCH")
            result.append(item)
        return tuple(result)

    def records(self): return self._load(self.root, RegistryRecord, "REGISTRY", "registry_uuid")
    def snapshots(self):
        return self._load(self.snapshot_root, KnowledgeRegistrySnapshot,
                          "REGISTRY_SNAPSHOT", "snapshot_uuid")
    def identities(self): return tuple((x.registry_uuid, x.registry_digest) for x in self.records())
    def digest(self): return digest([list(x) for x in self.identities()])

    def validate_partition(self, registry_version, engine_version, policy_uuid, policy_digest):
        records = self.records(); snapshot = self.latest_snapshot()
        if any(record.registry_version != registry_version for record in records):
            raise KnowledgeRegistryError("REGISTRY_VERSION_MISMATCH")
        if snapshot and snapshot.registry_version != registry_version:
            raise KnowledgeRegistryError("REGISTRY_VERSION_MISMATCH")
        if snapshot and snapshot.promotion_engine_version != engine_version:
            raise KnowledgeRegistryError("PROMOTION_ENGINE_IDENTITY_MISMATCH")
        if snapshot and (snapshot.promotion_policy_uuid != policy_uuid
                         or snapshot.promotion_policy_digest != policy_digest):
            raise KnowledgeRegistryError("MIXED_PROMOTION_POLICY")
        return records, snapshot

    def latest_snapshot(self):
        snapshots = self.snapshots()
        if not snapshots: return None
        by_uuid = {x.snapshot_uuid: x for x in snapshots}
        referenced = {x.previous_snapshot_uuid for x in snapshots if x.previous_snapshot_uuid}
        heads = [x for x in snapshots if x.snapshot_uuid not in referenced]
        if len(by_uuid) != len(snapshots) or len(heads) != 1:
            raise KnowledgeRegistryError("BROKEN_REGISTRY_SNAPSHOT_CHAIN")
        head = current = heads[0]; visited = set()
        partition = (head.registry_version, head.promotion_engine_version,
                     head.promotion_policy_uuid, head.promotion_policy_digest)
        while True:
            if current.snapshot_uuid in visited:
                raise KnowledgeRegistryError("BROKEN_REGISTRY_SNAPSHOT_CHAIN")
            visited.add(current.snapshot_uuid)
            if (current.registry_version, current.promotion_engine_version,
                    current.promotion_policy_uuid, current.promotion_policy_digest) != partition:
                raise KnowledgeRegistryError("MIXED_REGISTRY_PARTITION")
            if not current.previous_snapshot_uuid: break
            previous = by_uuid.get(current.previous_snapshot_uuid)
            if previous is None or previous.snapshot_digest != current.previous_snapshot_digest:
                raise KnowledgeRegistryError("BROKEN_REGISTRY_SNAPSHOT_CHAIN")
            current = previous
        if len(visited) != len(snapshots): raise KnowledgeRegistryError("BROKEN_REGISTRY_SNAPSHOT_CHAIN")
        if head.record_identities != self.identities() or head.repository_digest != self.digest():
            raise KnowledgeRegistryError("REGISTRY_SNAPSHOT_INTEGRITY_FAILURE")
        return head
