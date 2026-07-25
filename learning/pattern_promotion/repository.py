"""Atomic append-only, single-policy PR178 assessment history."""
import json
import os
from pathlib import Path
import re
import tempfile
from .exceptions import PatternPromotionError
from .identity import digest
from .models import PatternPromotionSnapshot, PromotionRecord

_UUID = re.compile(r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$")


class PatternPromotionRepository:
    def __init__(self, root="learning_data/pattern_promotion"):
        self.root = Path(root); self.snapshot_root = self.root / "snapshots"

    def _append(self, path, data, collision, prefix):
        path.parent.mkdir(parents=True, exist_ok=True)
        descriptor, name = tempfile.mkstemp(prefix=prefix, dir=path.parent); temporary = Path(name)
        try:
            with os.fdopen(descriptor, "wb") as stream:
                stream.write(data); stream.flush(); os.fsync(stream.fileno())
            try: os.link(temporary, path)
            except FileExistsError:
                if path.read_bytes() != data: raise PatternPromotionError(collision) from None
        finally: temporary.unlink(missing_ok=True)
        return path

    @staticmethod
    def _bytes(value):
        return json.dumps(value.to_dict(), sort_keys=True, separators=(",", ":"), allow_nan=False).encode()

    def path_for(self, identifier):
        if not isinstance(identifier, str) or not _UUID.fullmatch(identifier):
            raise PatternPromotionError("INVALID_PROMOTION_FILENAME")
        return self.root / f"{identifier}.json"

    def save(self, record):
        if type(record) is not PromotionRecord: raise PatternPromotionError("INVALID_PROMOTION_RECORD")
        return self._append(self.path_for(record.promotion_uuid), self._bytes(record),
                            "PROMOTION_COLLISION", ".pattern-promotion-")

    def save_snapshot(self, snapshot):
        if type(snapshot) is not PatternPromotionSnapshot:
            raise PatternPromotionError("INVALID_PROMOTION_SNAPSHOT")
        return self._append(self.snapshot_root / f"{snapshot.snapshot_uuid}.json", self._bytes(snapshot),
                            "PROMOTION_SNAPSHOT_COLLISION", ".pattern-promotion-snapshot-")

    def _load(self, root, model, label, field):
        if not root.exists(): return ()
        result = []
        for path in sorted(root.glob("*.json")):
            if not _UUID.fullmatch(path.stem): raise PatternPromotionError(f"INVALID_{label}_FILENAME")
            try: item = model(**json.loads(path.read_text(encoding="utf-8")))
            except (OSError, ValueError, TypeError, json.JSONDecodeError) as exc:
                raise PatternPromotionError(f"CORRUPT_{label}_REPOSITORY") from exc
            if getattr(item, field) != path.stem:
                raise PatternPromotionError(f"{label}_FILENAME_IDENTITY_MISMATCH")
            result.append(item)
        return tuple(result)

    def records(self): return self._load(self.root, PromotionRecord, "PROMOTION", "promotion_uuid")
    def snapshots(self): return self._load(self.snapshot_root, PatternPromotionSnapshot,
                                            "PROMOTION_SNAPSHOT", "snapshot_uuid")
    def identities(self): return tuple((x.promotion_uuid, x.promotion_digest) for x in self.records())
    def digest(self): return digest([list(x) for x in self.identities()])

    def validate_partition(self, engine_version, policy):
        records = self.records(); snapshot = self.latest_snapshot()
        for item in (*records, *((snapshot,) if snapshot else ())):
            if item.promotion_engine_version != engine_version:
                raise PatternPromotionError("PROMOTION_ENGINE_VERSION_MISMATCH")
            if item.promotion_policy_version != policy.promotion_policy_version:
                raise PatternPromotionError("PROMOTION_POLICY_VERSION_MISMATCH")
            if item.promotion_policy_digest != policy.policy_digest:
                raise PatternPromotionError("PROMOTION_POLICY_DIGEST_MISMATCH")
            if item.promotion_policy_uuid != policy.policy_uuid:
                raise PatternPromotionError("MIXED_PROMOTION_POLICY_REPOSITORY")
        if snapshot and snapshot.record_identities != self.identities():
            raise PatternPromotionError("PROMOTION_REPOSITORY_SNAPSHOT_MISMATCH")
        return records, snapshot

    def latest_snapshot(self):
        snapshots = self.snapshots()
        if not snapshots: return None
        by_uuid = {x.snapshot_uuid: x for x in snapshots}
        if len(by_uuid) != len(snapshots): raise PatternPromotionError("BROKEN_PROMOTION_SNAPSHOT_CHAIN")
        referenced = {x.previous_snapshot_uuid for x in snapshots if x.previous_snapshot_uuid}
        heads = [x for x in snapshots if x.snapshot_uuid not in referenced]
        if len(heads) != 1: raise PatternPromotionError("BROKEN_PROMOTION_SNAPSHOT_CHAIN")
        head = current = heads[0]; visited = set()
        identity = (head.promotion_engine_version, head.promotion_policy_uuid,
                    head.promotion_policy_digest, head.promotion_policy_version)
        while True:
            if current.snapshot_uuid in visited:
                raise PatternPromotionError("BROKEN_PROMOTION_SNAPSHOT_CHAIN")
            visited.add(current.snapshot_uuid)
            if (current.promotion_engine_version, current.promotion_policy_uuid,
                    current.promotion_policy_digest, current.promotion_policy_version) != identity:
                raise PatternPromotionError("MIXED_PROMOTION_POLICY_REPOSITORY")
            if not current.previous_snapshot_uuid: break
            previous = by_uuid.get(current.previous_snapshot_uuid)
            if previous is None or previous.snapshot_digest != current.previous_snapshot_digest:
                raise PatternPromotionError("BROKEN_PROMOTION_SNAPSHOT_CHAIN")
            current = previous
        if len(visited) != len(snapshots): raise PatternPromotionError("BROKEN_PROMOTION_SNAPSHOT_CHAIN")
        if head.record_identities != self.identities():
            raise PatternPromotionError("PROMOTION_REPOSITORY_SNAPSHOT_MISMATCH")
        return head
