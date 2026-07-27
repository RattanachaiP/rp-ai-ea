"""Atomic append-only repository for PR186 readiness and snapshot chains."""

import json
import os
import re
import tempfile
from pathlib import Path

from .exceptions import ExecutionReadinessError
from .identity import canonical_bytes, digest
from .models import ExecutionReadiness, ExecutionReadinessSnapshot

_UUID = re.compile(r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$")


class ExecutionReadinessRepository:
    def __init__(self, root="learning_data/execution_readiness"):
        self.root = Path(root)
        self.snapshot_root = self.root / "snapshots"

    @staticmethod
    def _append(path, value, collision):
        data = canonical_bytes(value.to_dict())
        path.parent.mkdir(parents=True, exist_ok=True)
        descriptor, name = tempfile.mkstemp(prefix=".readiness-", dir=path.parent)
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
                    raise ExecutionReadinessError(collision) from None
        finally:
            temporary.unlink(missing_ok=True)
        return path

    def save(self, value):
        if type(value) is not ExecutionReadiness:
            raise ExecutionReadinessError("INVALID_EXECUTION_READINESS")
        return self._append(
            self.root / f"{value.execution_readiness_uuid}.json", value, "REPLAY_COLLISION"
        )

    def save_snapshot(self, value):
        if type(value) is not ExecutionReadinessSnapshot:
            raise ExecutionReadinessError("INVALID_EXECUTION_READINESS_SNAPSHOT")
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
                raise ExecutionReadinessError(f"INVALID_{label}_FILENAME")
            try:
                item = model(**json.loads(path.read_text()))
            except (
                OSError,
                ValueError,
                TypeError,
                KeyError,
                json.JSONDecodeError,
            ) as exc:
                raise ExecutionReadinessError(
                    f"CORRUPT_{label}_REPOSITORY"
                ) from exc
            if getattr(item, identity_field) != path.stem:
                raise ExecutionReadinessError(f"{label}_FILENAME_IDENTITY_MISMATCH")
            if path.read_bytes() != canonical_bytes(item.to_dict()):
                raise ExecutionReadinessError(f"NONCANONICAL_{label}_JSON")
            output.append(item)
        return tuple(output)

    def records(self):
        return self._load(
            self.root,
            ExecutionReadiness,
            "EXECUTION_READINESS",
            "execution_readiness_uuid",
        )

    def snapshots(self):
        return self._load(
            self.snapshot_root,
            ExecutionReadinessSnapshot,
            "EXECUTION_READINESS_SNAPSHOT",
            "snapshot_uuid",
        )

    def identities(self):
        return tuple(
            (item.execution_readiness_uuid, item.execution_readiness_digest)
            for item in self.records()
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
            raise ExecutionReadinessError("SNAPSHOT_MISMATCH")
        head = current = heads[0]
        seen = set()
        partition = (
            head.readiness_policy_uuid,
            head.readiness_policy_digest,
            head.readiness_policy_version,
            head.readiness_engine_version,
            head.recommendation_policy_uuid,
            head.recommendation_policy_digest,
            head.recommendation_policy_version,
            head.recommendation_engine_version,
        )
        while True:
            if current.snapshot_uuid in seen:
                raise ExecutionReadinessError("SNAPSHOT_MISMATCH")
            seen.add(current.snapshot_uuid)
            if (
                current.readiness_engine_version != partition[3]
                or current.recommendation_engine_version != partition[7]
            ):
                raise ExecutionReadinessError("ENGINE_VERSION_MISMATCH")
            if (
                current.readiness_policy_uuid,
                current.readiness_policy_digest,
                current.readiness_policy_version,
                current.readiness_engine_version,
                current.recommendation_policy_uuid,
                current.recommendation_policy_digest,
                current.recommendation_policy_version,
                current.recommendation_engine_version,
            ) != partition:
                raise ExecutionReadinessError("POLICY_MISMATCH")
            if current.previous_snapshot_uuid is None:
                break
            previous = by_uuid.get(current.previous_snapshot_uuid)
            if (
                previous is None
                or previous.snapshot_digest != current.previous_snapshot_digest
            ):
                raise ExecutionReadinessError("SNAPSHOT_MISMATCH")
            current = previous
        if len(seen) != len(snapshots):
            raise ExecutionReadinessError("SNAPSHOT_MISMATCH")
        if head.readiness_identities != self.identities():
            raise ExecutionReadinessError("SNAPSHOT_MISMATCH")
        if head.repository_digest != self.digest():
            raise ExecutionReadinessError("REPOSITORY_MISMATCH")
        return head

    def exact_snapshot_for(
        self,
        readiness,
        snapshot_uuid,
        snapshot_digest,
    ):
        """Resolve one caller-specified snapshot and verify its complete lineage.

        This API deliberately does not infer a head or use filesystem ordering. The
        caller must provide the snapshot identity emitted by the PR186 engine.
        """
        if type(readiness) is not ExecutionReadiness:
            raise ExecutionReadinessError("INVALID_EXECUTION_READINESS")
        records = self.records()
        record_matches = tuple(
            item
            for item in records
            if (
                item.execution_readiness_uuid,
                item.execution_readiness_digest,
            )
            == (
                readiness.execution_readiness_uuid,
                readiness.execution_readiness_digest,
            )
        )
        if len(record_matches) != 1 or record_matches[0] != readiness:
            raise ExecutionReadinessError("BROKEN_PROVENANCE")

        snapshots = self.snapshots()
        matches = tuple(
            item
            for item in snapshots
            if (item.snapshot_uuid, item.snapshot_digest)
            == (snapshot_uuid, snapshot_digest)
        )
        if len(matches) != 1:
            raise ExecutionReadinessError("SNAPSHOT_MISMATCH")
        target = matches[0]
        expected_partition = (
            readiness.readiness_policy_uuid,
            readiness.readiness_policy_digest,
            readiness.readiness_policy_version,
            readiness.readiness_engine_version,
        )
        actual_partition = (
            target.readiness_policy_uuid,
            target.readiness_policy_digest,
            target.readiness_policy_version,
            target.readiness_engine_version,
        )
        if actual_partition[3] != expected_partition[3]:
            raise ExecutionReadinessError("ENGINE_VERSION_MISMATCH")
        if actual_partition != expected_partition:
            raise ExecutionReadinessError("POLICY_MISMATCH")
        identity = (
            readiness.execution_readiness_uuid,
            readiness.execution_readiness_digest,
        )
        if target.readiness_identities.count(identity) != 1:
            raise ExecutionReadinessError("SNAPSHOT_MISMATCH")
        if target.readiness_identities != self.identities():
            raise ExecutionReadinessError("SNAPSHOT_MISMATCH")
        if target.repository_digest != self.digest():
            raise ExecutionReadinessError("REPOSITORY_MISMATCH")

        by_uuid = {item.snapshot_uuid: item for item in snapshots}
        if len(by_uuid) != len(snapshots):
            raise ExecutionReadinessError("SNAPSHOT_MISMATCH")
        current = target
        seen = set()
        while True:
            if current.snapshot_uuid in seen:
                raise ExecutionReadinessError("SNAPSHOT_MISMATCH")
            seen.add(current.snapshot_uuid)
            current_partition = (
                current.readiness_policy_uuid,
                current.readiness_policy_digest,
                current.readiness_policy_version,
                current.readiness_engine_version,
            )
            if current_partition[3] != expected_partition[3]:
                raise ExecutionReadinessError("ENGINE_VERSION_MISMATCH")
            if current_partition != expected_partition:
                raise ExecutionReadinessError("POLICY_MISMATCH")
            if current.previous_snapshot_uuid is None:
                break
            previous = by_uuid.get(current.previous_snapshot_uuid)
            if (
                previous is None
                or previous.snapshot_digest != current.previous_snapshot_digest
            ):
                raise ExecutionReadinessError("SNAPSHOT_MISMATCH")
            current = previous
        if len(seen) != len(snapshots):
            raise ExecutionReadinessError("SNAPSHOT_MISMATCH")
        return target
