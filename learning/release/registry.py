"""Append-only, single-certificate production release registry."""
from dataclasses import dataclass

from learning.deployment.contracts import _revalidate
from learning.promotion.identity import identity_for
from .contracts import ReleaseDecision


@dataclass(frozen=True)
class ReleaseRegistryEntry:
    decision: ReleaseDecision
    sequence: int
    previous_entry_identity: str | None
    entry_identity: str = ""

    def __post_init__(self):
        _revalidate(self.decision)
        if (self.decision.certificate is None or type(self.sequence) is not int or self.sequence < 1
                or (self.sequence == 1) != (self.previous_entry_identity is None)):
            raise ValueError("RELEASE_REGISTRY_ENTRY_INVALID")
        expected = identity_for("RELEASE_REGISTRY_ENTRY", self.canonical_payload())
        if self.entry_identity and self.entry_identity != expected:
            raise ValueError("RELEASE_REGISTRY_ENTRY_IDENTITY_INVALID")
        object.__setattr__(self, "entry_identity", expected)

    def canonical_payload(self):
        return {"decision_identity": self.decision.decision_identity, "sequence": self.sequence,
                "previous_entry_identity": self.previous_entry_identity}


@dataclass(frozen=True)
class ReleaseRegistry:
    entries: tuple[ReleaseRegistryEntry, ...] = ()
    previous_registry_identity: str | None = None
    registry_identity: str = ""

    def __post_init__(self):
        entries = tuple(self.entries)
        object.__setattr__(self, "entries", entries)
        scopes = set()
        for index, entry in enumerate(entries):
            ReleaseRegistryEntry(**entry.__dict__)
            if entry.sequence != index + 1 or entry.previous_entry_identity != (
                    None if index == 0 else entries[index - 1].entry_identity):
                raise ValueError("RELEASE_REGISTRY_LINEAGE_INVALID")
            certificate = entry.decision.certificate
            scope = (certificate.release_request_identity, certificate.deployment_manifest_identity,
                     certificate.target_environment_identity, certificate.runtime_contract_identity)
            if scope in scopes:
                raise ValueError("MULTIPLE_RELEASE_CERTIFICATES_FOR_ACTIVATION")
            scopes.add(scope)
        predecessor = None if not entries else self._identity(entries[:-1])
        if self.previous_registry_identity != predecessor:
            raise ValueError("RELEASE_REGISTRY_PREDECESSOR_INVALID")
        expected = self._identity(entries)
        if self.registry_identity and self.registry_identity != expected:
            raise ValueError("RELEASE_REGISTRY_IDENTITY_INVALID")
        object.__setattr__(self, "registry_identity", expected)

    @staticmethod
    def _identity(entries):
        return identity_for("RELEASE_REGISTRY", tuple(entry.entry_identity for entry in entries))

    def append(self, decision):
        _revalidate(decision)
        if decision.certificate is None:
            raise ValueError("REJECTED_RELEASE_NOT_REGISTRABLE")
        if any(entry.decision.decision_identity == decision.decision_identity for entry in self.entries):
            return self
        certificate = decision.certificate
        scope = (certificate.release_request_identity, certificate.deployment_manifest_identity,
                 certificate.target_environment_identity, certificate.runtime_contract_identity)
        for entry in self.entries:
            current = entry.decision.certificate
            if scope == (current.release_request_identity, current.deployment_manifest_identity,
                         current.target_environment_identity, current.runtime_contract_identity):
                raise ValueError("MULTIPLE_RELEASE_CERTIFICATES_FOR_ACTIVATION")
        entry = ReleaseRegistryEntry(decision, len(self.entries) + 1,
                                     None if not self.entries else self.entries[-1].entry_identity)
        return ReleaseRegistry(self.entries + (entry,), self.registry_identity)
