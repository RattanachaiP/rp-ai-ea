"""PR190 canonical, read-only consumer for immutable PR189 packages."""

import json
from dataclasses import dataclass
from pathlib import Path

from learning.execution_package import ExecutionPackage, ExecutionPackageRepository
from learning.execution_package.identity import canonical_bytes, digest, execution_package_uuid
from learning.execution_package.policy import ENGINE_VERSION, POLICY_VERSION
from learning.pattern_memory.models import valid_digest, valid_uuid

from .exceptions import ExecutionPackageConsumerError


@dataclass(frozen=True)
class ExecutionPackageCompatibility:
    """The explicit package serialization and engine versions PR190 accepts."""

    package_versions: tuple[str, ...] = (POLICY_VERSION,)
    engine_versions: tuple[str, ...] = (ENGINE_VERSION,)

    def __post_init__(self):
        object.__setattr__(self, "package_versions", tuple(self.package_versions))
        object.__setattr__(self, "engine_versions", tuple(self.engine_versions))
        if (not self.package_versions or not self.engine_versions or
                any(not isinstance(value, str) or not value.strip()
                    for value in self.package_versions + self.engine_versions)):
            raise ValueError("INVALID_CONSUMER_COMPATIBILITY")


class ExecutionPackageConsumer:
    """Load one PR189 package without evaluating, changing, or authorizing it."""

    def __init__(self, repository=None, compatibility=None):
        self.repository = repository or ExecutionPackageRepository()
        self.compatibility = compatibility or ExecutionPackageCompatibility()
        if type(self.repository) is not ExecutionPackageRepository:
            raise ExecutionPackageConsumerError("REPOSITORY_MISMATCH")
        if type(self.compatibility) is not ExecutionPackageCompatibility:
            raise ExecutionPackageConsumerError("UNSUPPORTED_PACKAGE_VERSION")

    def load(self, package_uuid):
        if not valid_uuid(package_uuid):
            raise ExecutionPackageConsumerError("INVALID_UUID")
        path = self.repository.root / f"{package_uuid}.json"
        if not path.is_file():
            raise ExecutionPackageConsumerError("PACKAGE_MISSING")

        raw = self._read(path)
        self._verify_uuid_fields(raw, package_uuid)
        self._verify_digest_fields(raw)
        self._verify_versions(raw)
        identity_payload = {key: item for key, item in raw.items()
                            if key not in {"execution_package_uuid", "execution_package_digest"}}
        if execution_package_uuid(identity_payload) != raw["execution_package_uuid"]:
            raise ExecutionPackageConsumerError("REPLAY_IDENTITY_FAILURE")
        package = self._deserialize(raw)

        if path.read_bytes() != canonical_bytes(package.to_dict()):
            raise ExecutionPackageConsumerError("SERIALIZATION_FAILURE")
        self._verify_snapshot(package)
        return package

    load_package = load

    @staticmethod
    def _read(path: Path):
        try:
            value = json.loads(path.read_bytes())
        except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise ExecutionPackageConsumerError("SERIALIZATION_FAILURE") from exc
        if type(value) is not dict:
            raise ExecutionPackageConsumerError("SERIALIZATION_FAILURE")
        return value

    @staticmethod
    def _verify_uuid_fields(value, requested_uuid):
        fields = ("execution_package_uuid", "execution_readiness_uuid",
                  "execution_environment_uuid", "execution_feasibility_uuid",
                  "package_policy_uuid")
        if any(not valid_uuid(value.get(field)) for field in fields):
            raise ExecutionPackageConsumerError("INVALID_UUID")
        if value["execution_package_uuid"] != requested_uuid:
            raise ExecutionPackageConsumerError("REPLAY_IDENTITY_FAILURE")

    @staticmethod
    def _verify_digest_fields(value):
        fields = ("execution_package_digest", "execution_readiness_digest",
                  "execution_environment_digest", "execution_feasibility_digest",
                  "snapshot_chain_digest", "repository_digest", "policy_digest")
        if any(not valid_digest(value.get(field)) for field in fields):
            raise ExecutionPackageConsumerError("SHA256_MISMATCH")
        payload = {key: item for key, item in value.items() if key != "execution_package_digest"}
        if digest(payload) != value["execution_package_digest"]:
            raise ExecutionPackageConsumerError("SHA256_MISMATCH")

    def _verify_versions(self, value):
        if value.get("package_policy_version") not in self.compatibility.package_versions:
            raise ExecutionPackageConsumerError("UNSUPPORTED_PACKAGE_VERSION")
        if value.get("package_engine_version") not in self.compatibility.engine_versions:
            raise ExecutionPackageConsumerError("UNSUPPORTED_ENGINE_VERSION")
        versions = value.get("engine_versions")
        if (not isinstance(versions, list) or len(versions) != 4 or
                versions[-1] != ["package", value["package_engine_version"]]):
            raise ExecutionPackageConsumerError("UNSUPPORTED_ENGINE_VERSION")

    @staticmethod
    def _deserialize(value):
        try:
            return ExecutionPackage(**value)
        except (KeyError, TypeError, ValueError) as exc:
            raise ExecutionPackageConsumerError("SERIALIZATION_FAILURE") from exc

    def _verify_snapshot(self, package):
        try:
            snapshot = self.repository.latest_snapshot()
        except (OSError, ValueError) as exc:
            raise ExecutionPackageConsumerError("SNAPSHOT_MISMATCH") from exc
        identity = (package.execution_package_uuid, package.execution_package_digest)
        if snapshot is None or identity not in snapshot.package_identities:
            raise ExecutionPackageConsumerError("SNAPSHOT_MISMATCH")


GovernedAdvisoryExecutionPackageConsumerInterface = ExecutionPackageConsumer
