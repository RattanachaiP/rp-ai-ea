"""Append-only registry owned by Runtime Activation Authority."""
from dataclasses import dataclass

from learning.deployment.contracts import _revalidate, _text, _utc
from learning.promotion.identity import identity_for
from learning.release import ActivationRevocation

from .contracts import ActivationRegistryEntry


@dataclass(frozen=True)
class ActivationRegistry:
    entries: tuple[ActivationRegistryEntry, ...] = ()
    revocations: tuple[ActivationRevocation, ...] = ()
    registry_identity: str = ""

    def __post_init__(self):
        entries, revocations = tuple(self.entries), tuple(self.revocations)
        object.__setattr__(self, "entries", entries)
        object.__setattr__(self, "revocations", revocations)
        for index, entry in enumerate(entries):
            _revalidate(entry)
            if (entry.sequence != index + 1 or entry.previous_entry_identity !=
                    (None if index == 0 else entries[index - 1].entry_identity)):
                raise ValueError("ACTIVATION_REGISTRY_LINEAGE_INVALID")
        identities = [e.consumed_authorization.authorization.authorization_identity
                      for e in entries]
        if len(identities) != len(set(identities)):
            raise ValueError("ACTIVATION_REPLAY")
        for revocation in revocations:
            _revalidate(revocation)
        expected = identity_for("PR277_ACTIVATION_REGISTRY", {
            "entries": tuple(e.entry_identity for e in entries),
            "revocations": tuple(r.revocation_identity for r in revocations)})
        if self.registry_identity and self.registry_identity != expected:
            raise ValueError("ACTIVATION_REGISTRY_IDENTITY_INVALID")
        object.__setattr__(self, "registry_identity", expected)

    def is_consumed(self, authorization_identity):
        return any(e.consumed_authorization.authorization.authorization_identity ==
                   authorization_identity for e in self.entries)

    def is_revoked(self, authorization_identity, at):
        instant = _utc(at)
        return any(r.authorization_identity == authorization_identity and
                   _utc(r.issued_at) <= instant for r in self.revocations)

    def revoke(self, record):
        _revalidate(record)
        if not _text(record.authorization_identity):
            raise ValueError("ACTIVATION_REVOCATION_INVALID")
        if any(r.authorization_identity == record.authorization_identity
               for r in self.revocations):
            raise ValueError("ACTIVATION_REVOCATION_REPLAY")
        return ActivationRegistry(self.entries, self.revocations + (record,))

    def append(self, entry):
        _revalidate(entry)
        expected_previous = None if not self.entries else self.entries[-1].entry_identity
        if entry.sequence != len(self.entries) + 1 or entry.previous_entry_identity != expected_previous:
            raise ValueError("ACTIVATION_REGISTRY_LINEAGE_INVALID")
        if self.is_consumed(entry.consumed_authorization.authorization.authorization_identity):
            raise ValueError("ACTIVATION_REPLAY")
        return ActivationRegistry(self.entries + (entry,), self.revocations)
