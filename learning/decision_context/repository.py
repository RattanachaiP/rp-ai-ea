"""Atomic append-only repository for PR183 contexts and snapshot chain."""
import json
import os
import tempfile
from pathlib import Path
from .exceptions import DecisionContextError
from .identity import canonical_bytes, digest
from .models import DecisionContext, DecisionContextSnapshot


class DecisionContextRepository:
    def __init__(self, root="learning_data/decision_context"):
        self.root = Path(root); self.snapshot_root = self.root / "snapshots"

    def _append(self, path, value):
        data = canonical_bytes(value.to_dict()); path.parent.mkdir(parents=True, exist_ok=True)
        descriptor, name = tempfile.mkstemp(prefix=".context-", dir=path.parent)
        try:
            with os.fdopen(descriptor, "wb") as stream:
                stream.write(data); stream.flush(); os.fsync(stream.fileno())
            try: os.link(name, path)
            except FileExistsError:
                if path.read_bytes() != data: raise DecisionContextError("REPLAY_COLLISION") from None
        finally: Path(name).unlink(missing_ok=True)
        return path

    def save(self, value):
        if type(value) is not DecisionContext: raise DecisionContextError("INVALID_CONFIDENCE")
        return self._append(self.root / f"{value.context_uuid}.json", value)

    def save_snapshot(self, value):
        if type(value) is not DecisionContextSnapshot: raise DecisionContextError("SNAPSHOT_MISMATCH")
        return self._append(self.snapshot_root / f"{value.snapshot_uuid}.json", value)

    def _load(self, root, model):
        output = []
        if not root.exists(): return ()
        for path in sorted(root.glob("*.json")):
            try: item = model(**json.loads(path.read_text()))
            except (OSError, ValueError, TypeError, json.JSONDecodeError) as exc: raise DecisionContextError("REPOSITORY_MISMATCH") from exc
            identity = item.context_uuid if model is DecisionContext else item.snapshot_uuid
            if path.stem != identity or path.read_bytes() != canonical_bytes(item.to_dict()): raise DecisionContextError("REPOSITORY_MISMATCH")
            output.append(item)
        return tuple(output)

    def records(self): return self._load(self.root, DecisionContext)
    def snapshots(self): return self._load(self.snapshot_root, DecisionContextSnapshot)
    def identities(self): return tuple((x.context_uuid, x.context_digest) for x in self.records())
    def digest(self): return digest([list(x) for x in self.identities()])

    def latest_snapshot(self):
        snapshots = self.snapshots()
        if not snapshots: return None
        by_id = {x.snapshot_uuid: x for x in snapshots}; referenced = {x.previous_snapshot_uuid for x in snapshots if x.previous_snapshot_uuid}; heads = [x for x in snapshots if x.snapshot_uuid not in referenced]
        if len(by_id) != len(snapshots) or len(heads) != 1: raise DecisionContextError("SNAPSHOT_MISMATCH")
        current = head = heads[0]; seen = set()
        while current:
            if current.snapshot_uuid in seen: raise DecisionContextError("SNAPSHOT_MISMATCH")
            seen.add(current.snapshot_uuid)
            if current.previous_snapshot_uuid is None: break
            previous = by_id.get(current.previous_snapshot_uuid)
            if previous is None or previous.snapshot_digest != current.previous_snapshot_digest: raise DecisionContextError("SNAPSHOT_MISMATCH")
            current = previous
        if len(seen) != len(snapshots) or head.context_identities != self.identities(): raise DecisionContextError("SNAPSHOT_MISMATCH")
        if head.repository_digest != self.digest(): raise DecisionContextError("REPOSITORY_MISMATCH")
        return head
