"""Atomic append-only repository for PR184 intelligences and snapshot chains."""

import json
import os
import re
import tempfile
from pathlib import Path

from .exceptions import DecisionIntelligenceError
from .identity import canonical_bytes, digest
from .models import DecisionIntelligence, DecisionIntelligenceSnapshot

_UUID = re.compile(r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$")


class DecisionIntelligenceRepository:
    def __init__(self, root="learning_data/decision_intelligence"):
        self.root = Path(root)
        self.snapshot_root = self.root / "snapshots"

    @staticmethod
    def _append(path, value, collision):
        data = canonical_bytes(value.to_dict())
        path.parent.mkdir(parents=True, exist_ok=True)
        descriptor, name = tempfile.mkstemp(prefix=".intelligence-", dir=path.parent)
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
                    raise DecisionIntelligenceError(collision) from None
        finally:
            temporary.unlink(missing_ok=True)
        return path

    def save(self, value):
        if type(value) is not DecisionIntelligence:
            raise DecisionIntelligenceError("INVALID_DECISION_INTELLIGENCE")
        return self._append(
            self.root / f"{value.intelligence_uuid}.json", value, "REPLAY_COLLISION"
        )

    def save_snapshot(self, value):
        if type(value) is not DecisionIntelligenceSnapshot:
            raise DecisionIntelligenceError("INVALID_INTELLIGENCE_SNAPSHOT")
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
                raise DecisionIntelligenceError(f"INVALID_{label}_FILENAME")
            try:
                item = model(**json.loads(path.read_text()))
            except (OSError, ValueError, TypeError, KeyError, json.JSONDecodeError) as exc:
                raise DecisionIntelligenceError(f"CORRUPT_{label}_REPOSITORY") from exc
            if getattr(item, identity_field) != path.stem:
                raise DecisionIntelligenceError(f"{label}_FILENAME_IDENTITY_MISMATCH")
            if path.read_bytes() != canonical_bytes(item.to_dict()):
                raise DecisionIntelligenceError(f"NONCANONICAL_{label}_JSON")
            output.append(item)
        return tuple(output)

    def records(self):
        return self._load(self.root, DecisionIntelligence, "DECISION_INTELLIGENCE", "intelligence_uuid")

    def snapshots(self):
        return self._load(
            self.snapshot_root,
            DecisionIntelligenceSnapshot,
            "INTELLIGENCE_SNAPSHOT",
            "snapshot_uuid",
        )

    def identities(self):
        return tuple(
            (item.intelligence_uuid, item.intelligence_digest) for item in self.records()
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
            raise DecisionIntelligenceError("SNAPSHOT_MISMATCH")
        head = current = heads[0]
        seen = set()
        partition = (
            head.intelligence_policy_uuid,
            head.intelligence_policy_digest,
            head.intelligence_policy_version,
            head.intelligence_engine_version,
            head.context_policy_uuid,
            head.context_policy_digest,
            head.context_policy_version,
            head.context_engine_version,
        )
        while True:
            if current.snapshot_uuid in seen:
                raise DecisionIntelligenceError("SNAPSHOT_MISMATCH")
            seen.add(current.snapshot_uuid)
            if (
                current.intelligence_policy_uuid,
                current.intelligence_policy_digest,
                current.intelligence_policy_version,
                current.intelligence_engine_version,
                current.context_policy_uuid,
                current.context_policy_digest,
                current.context_policy_version,
                current.context_engine_version,
            ) != partition:
                raise DecisionIntelligenceError("POLICY_MISMATCH")
            if current.previous_snapshot_uuid is None:
                break
            previous = by_uuid.get(current.previous_snapshot_uuid)
            if (
                previous is None
                or previous.snapshot_digest != current.previous_snapshot_digest
            ):
                raise DecisionIntelligenceError("SNAPSHOT_MISMATCH")
            current = previous
        if len(seen) != len(snapshots):
            raise DecisionIntelligenceError("SNAPSHOT_MISMATCH")
        if head.intelligence_identities != self.identities():
            raise DecisionIntelligenceError("SNAPSHOT_MISMATCH")
        if head.repository_digest != self.digest():
            raise DecisionIntelligenceError("REPOSITORY_MISMATCH")
        return head
