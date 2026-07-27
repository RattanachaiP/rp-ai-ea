"""Atomic append-only repository for PR184 intelligences and snapshot chains."""

import json
import os
import re
import tempfile
from pathlib import Path
from uuid import UUID

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

    def exact(
        self,
        *,
        intelligence_uuid,
        intelligence_digest,
        snapshot_uuid,
        snapshot_digest,
        repository_digest,
        intelligence_policy_uuid,
        intelligence_policy_digest,
        intelligence_policy_version,
        intelligence_engine_version,
    ):
        """Return one caller-bound record and snapshot without head selection."""
        try:
            canonical = (
                str(UUID(intelligence_uuid))
                if type(intelligence_uuid) is str
                else None
            )
        except (ValueError, TypeError, AttributeError):
            canonical = None
        if canonical != intelligence_uuid:
            raise DecisionIntelligenceError("INVALID_DECISION_INTELLIGENCE_UUID")
        record_matches = tuple(
            item
            for item in self.records()
            if item.intelligence_uuid == intelligence_uuid
            and item.intelligence_digest == intelligence_digest
        )
        if len(record_matches) != 1:
            raise DecisionIntelligenceError("DECISION_INTELLIGENCE_MISSING")
        snapshots = self.snapshots()
        snapshot_matches = tuple(
            item
            for item in snapshots
            if item.snapshot_uuid == snapshot_uuid
            and item.snapshot_digest == snapshot_digest
        )
        if len(snapshot_matches) != 1:
            raise DecisionIntelligenceError("SNAPSHOT_MISMATCH")
        snapshot = snapshot_matches[0]
        item = record_matches[0]
        if (
            snapshot.repository_digest != repository_digest
            or snapshot.repository_digest
            != digest([list(identity) for identity in snapshot.intelligence_identities])
            or (
                snapshot.intelligence_policy_uuid,
                snapshot.intelligence_policy_digest,
                snapshot.intelligence_policy_version,
                snapshot.intelligence_engine_version,
            )
            != (
                intelligence_policy_uuid,
                intelligence_policy_digest,
                intelligence_policy_version,
                intelligence_engine_version,
            )
            or (item.intelligence_uuid, item.intelligence_digest)
            not in snapshot.intelligence_identities
        ):
            raise DecisionIntelligenceError("SNAPSHOT_MISMATCH")
        by_uuid = {value.snapshot_uuid: value for value in snapshots}
        if len(by_uuid) != len(snapshots):
            raise DecisionIntelligenceError("SNAPSHOT_MISMATCH")
        children = {}
        for value in snapshots:
            if value.previous_snapshot_uuid is not None:
                children.setdefault(value.previous_snapshot_uuid, []).append(value)
        seen = set()
        current = snapshot
        while True:
            if current.snapshot_uuid in seen:
                raise DecisionIntelligenceError("SNAPSHOT_MISMATCH")
            seen.add(current.snapshot_uuid)
            if current.previous_snapshot_uuid is None:
                break
            previous = by_uuid.get(current.previous_snapshot_uuid)
            if previous is None or previous.snapshot_digest != current.previous_snapshot_digest:
                raise DecisionIntelligenceError("SNAPSHOT_MISMATCH")
            current = previous
        current = snapshot
        while children.get(current.snapshot_uuid):
            descendants = children[current.snapshot_uuid]
            if len(descendants) != 1:
                raise DecisionIntelligenceError("SNAPSHOT_MISMATCH")
            descendant = descendants[0]
            if descendant.previous_snapshot_digest != current.snapshot_digest:
                raise DecisionIntelligenceError("SNAPSHOT_MISMATCH")
            current = descendant
            if current.snapshot_uuid in seen:
                raise DecisionIntelligenceError("SNAPSHOT_MISMATCH")
            seen.add(current.snapshot_uuid)
        if len(seen) != len(snapshots):
            raise DecisionIntelligenceError("SNAPSHOT_MISMATCH")
        expected_partition = (
            intelligence_policy_uuid,
            intelligence_policy_digest,
            intelligence_policy_version,
            intelligence_engine_version,
        )
        records = {(value.intelligence_uuid, value.intelligence_digest) for value in self.records()}
        for value in snapshots:
            if (
                value.intelligence_policy_uuid,
                value.intelligence_policy_digest,
                value.intelligence_policy_version,
                value.intelligence_engine_version,
            ) != expected_partition or value.repository_digest != digest(
                [list(identity) for identity in value.intelligence_identities]
            ) or not set(value.intelligence_identities).issubset(records):
                raise DecisionIntelligenceError("POLICY_MISMATCH")
        return item, snapshot

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
