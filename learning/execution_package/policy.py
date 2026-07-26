"""Immutable PR189 package-assembly compatibility policy."""

from dataclasses import dataclass
from .identity import digest, policy_uuid

POLICY_VERSION = "PR189-EXECUTION-PACKAGE-ASSEMBLY-POLICY.1.0"
ENGINE_VERSION = "PR189.1.0"


@dataclass(frozen=True)
class ExecutionPackagePolicy:
    package_policy_version: str = POLICY_VERSION
    package_engine_version: str = ENGINE_VERSION

    def __post_init__(self):
        if not all(isinstance(value, str) and value.strip() for value in (
            self.package_policy_version, self.package_engine_version
        )):
            raise ValueError("INVALID_EXECUTION_PACKAGE_POLICY")

    def to_dict(self):
        return {name: getattr(self, name) for name in self.__dataclass_fields__}

    @property
    def package_policy_digest(self):
        return digest(self.to_dict())

    @property
    def package_policy_uuid(self):
        return policy_uuid(self.to_dict())
