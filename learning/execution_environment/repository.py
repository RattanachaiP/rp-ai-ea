"""Atomic append-only repository for PR187 environment and snapshot chains."""

import json
import os
import re
import tempfile
from pathlib import Path

from .exceptions import ExecutionEnvironmentError
from .identity import canonical_bytes, digest
from .models import (
    ExecutionEnvironment,
    ExecutionEnvironmentEvidence,
    ExecutionEnvironmentSnapshot,
)

_UUID = re.compile(r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$")


class ExecutionEnvironmentRepository:
    def __init__(self, root="learning_data/execution_environment"):
        self.root = Path(root)
        self.snapshot_root = self.root / "snapshots"

    @staticmethod
    def _append(path, value, collision):
        data = canonical_bytes(value.to_dict())
        path.parent.mkdir(parents=True, exist_ok=True)
        descriptor, name = tempfile.mkstemp(prefix=".environment-", dir=path.parent)
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
                    raise ExecutionEnvironmentError(collision) from None
        finally:
            temporary.unlink(missing_ok=True)
        return path

    def save(self, value):
        if type(value) is not ExecutionEnvironment:
            raise ExecutionEnvironmentError("INVALID_EXECUTION_ENVIRONMENT")
        return self._append(
            self.root / f"{value.execution_environment_uuid}.json",
            value,
            "REPLAY_COLLISION",
        )

    def save_snapshot(self, value):
        if type(value) is not ExecutionEnvironmentSnapshot:
            raise ExecutionEnvironmentError("INVALID_EXECUTION_ENVIRONMENT_SNAPSHOT")
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
                raise ExecutionEnvironmentError(f"INVALID_{label}_FILENAME")
            try:
                item = model(**json.loads(path.read_text()))
            except (
                OSError,
                ValueError,
                TypeError,
                KeyError,
                json.JSONDecodeError,
            ) as exc:
                raise ExecutionEnvironmentError(f"CORRUPT_{label}_REPOSITORY") from exc
            if getattr(item, identity_field) != path.stem:
                raise ExecutionEnvironmentError(f"{label}_FILENAME_IDENTITY_MISMATCH")
            if path.read_bytes() != canonical_bytes(item.to_dict()):
                raise ExecutionEnvironmentError(f"NONCANONICAL_{label}_JSON")
            output.append(item)
        return tuple(output)

    def records(self):
        return self._load(
            self.root,
            ExecutionEnvironment,
            "EXECUTION_ENVIRONMENT",
            "execution_environment_uuid",
        )

    def snapshots(self):
        return self._load(
            self.snapshot_root,
            ExecutionEnvironmentSnapshot,
            "EXECUTION_ENVIRONMENT_SNAPSHOT",
            "snapshot_uuid",
        )

    def identities(self):
        return tuple(
            (item.execution_environment_uuid, item.execution_environment_digest)
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
            raise ExecutionEnvironmentError("SNAPSHOT_MISMATCH")
        head = current = heads[0]
        seen = set()
        partition = (
            head.environment_policy_uuid,
            head.environment_policy_digest,
            head.environment_policy_version,
            head.environment_engine_version,
            head.readiness_policy_uuid,
            head.readiness_policy_digest,
            head.readiness_policy_version,
            head.readiness_engine_version,
        )
        while True:
            if current.snapshot_uuid in seen:
                raise ExecutionEnvironmentError("SNAPSHOT_MISMATCH")
            seen.add(current.snapshot_uuid)
            if (
                current.environment_engine_version != partition[3]
                or current.readiness_engine_version != partition[7]
            ):
                raise ExecutionEnvironmentError("ENGINE_VERSION_MISMATCH")
            if (
                current.environment_policy_uuid,
                current.environment_policy_digest,
                current.environment_policy_version,
                current.environment_engine_version,
                current.readiness_policy_uuid,
                current.readiness_policy_digest,
                current.readiness_policy_version,
                current.readiness_engine_version,
            ) != partition:
                raise ExecutionEnvironmentError("POLICY_MISMATCH")
            if current.previous_snapshot_uuid is None:
                break
            previous = by_uuid.get(current.previous_snapshot_uuid)
            if (
                previous is None
                or previous.snapshot_digest != current.previous_snapshot_digest
            ):
                raise ExecutionEnvironmentError("SNAPSHOT_MISMATCH")
            current = previous
        if len(seen) != len(snapshots):
            raise ExecutionEnvironmentError("SNAPSHOT_MISMATCH")
        if head.environment_identities != self.identities():
            raise ExecutionEnvironmentError("SNAPSHOT_MISMATCH")
        if head.repository_digest != self.digest():
            raise ExecutionEnvironmentError("REPOSITORY_MISMATCH")
        return head


class ExecutionEnvironmentEvidenceRepository:
    def __init__(self, root="learning_data/execution_environment/evidence"):
        self.root = Path(root)

    def save(self, value):
        if type(value) is not ExecutionEnvironmentEvidence:
            raise ExecutionEnvironmentError("INVALID_EXECUTION_ENVIRONMENT_EVIDENCE")
        return ExecutionEnvironmentRepository._append(
            self.root / f"{value.evidence_uuid}.json", value, "REPLAY_COLLISION"
        )

    def records(self):
        helper = ExecutionEnvironmentRepository(self.root)
        return helper._load(
            self.root,
            ExecutionEnvironmentEvidence,
            "EXECUTION_ENVIRONMENT_EVIDENCE",
            "evidence_uuid",
        )

    def for_readiness(self, readiness):
        matches = tuple(
            x
            for x in self.records()
            if (x.execution_readiness_uuid, x.execution_readiness_digest)
            == (
                readiness.execution_readiness_uuid,
                readiness.execution_readiness_digest,
            )
        )
        if len(matches) > 1:
            raise ExecutionEnvironmentError("REPLAY_COLLISION")
        return matches[0] if matches else None
