"""Immutable, append-only and replay-safe promotion registry."""
from dataclasses import dataclass

from .contracts import PromotionReport
from .identity import identity_for


@dataclass(frozen=True)
class PromotionRegistryEntry:
    report: PromotionReport
    sequence: int
    previous_entry_identity: str | None
    entry_identity: str = ""

    def __post_init__(self) -> None:
        PromotionReport(**self.report.__dict__)
        if (type(self.sequence) is not int or self.sequence < 1
                or (self.sequence == 1) != (self.previous_entry_identity is None)):
            raise ValueError("PROMOTION_REGISTRY_ENTRY_INVALID")
        expected = identity_for("PROMOTION_REGISTRY_ENTRY", self.canonical_payload())
        if self.entry_identity and self.entry_identity != expected:
            raise ValueError("PROMOTION_REGISTRY_ENTRY_IDENTITY_INVALID")
        object.__setattr__(self, "entry_identity", expected)

    def canonical_payload(self) -> dict[str, object]:
        return {"report_identity": self.report.report_identity,
                "candidate_identity": self.report.candidate_identity,
                "qualification_report_identity": self.report.qualification_report_identity,
                "qualification_registry_identity": self.report.qualification_registry_identity,
                "policy_identity": self.report.policy.policy_identity, "sequence": self.sequence,
                "previous_entry_identity": self.previous_entry_identity}


@dataclass(frozen=True)
class PromotionRegistry:
    entries: tuple[PromotionRegistryEntry, ...] = ()
    previous_registry_identity: str | None = None
    registry_identity: str = ""

    def __post_init__(self) -> None:
        entries = tuple(self.entries)
        object.__setattr__(self, "entries", entries)
        for index, entry in enumerate(entries):
            PromotionRegistryEntry(**entry.__dict__)
            if (entry.sequence != index + 1 or entry.previous_entry_identity !=
                    (None if index == 0 else entries[index - 1].entry_identity)):
                raise ValueError("PROMOTION_REGISTRY_LINEAGE_INVALID")
        keys = tuple((x.report.candidate_identity, x.report.qualification_report_identity,
                      x.report.policy.policy_identity) for x in entries)
        if len(keys) != len(set(keys)):
            raise ValueError("DUPLICATE_PROMOTION_DECISION")
        predecessor = None if not entries else self._identity(entries[:-1])
        if self.previous_registry_identity != predecessor:
            raise ValueError("PROMOTION_REGISTRY_PREDECESSOR_INVALID")
        expected = self._identity(entries)
        if self.registry_identity and self.registry_identity != expected:
            raise ValueError("PROMOTION_REGISTRY_IDENTITY_INVALID")
        object.__setattr__(self, "registry_identity", expected)

    @staticmethod
    def _identity(entries: tuple[PromotionRegistryEntry, ...]) -> str:
        return identity_for("PROMOTION_REGISTRY", tuple(x.entry_identity for x in entries))

    def append(self, report: PromotionReport) -> "PromotionRegistry":
        PromotionReport(**report.__dict__)
        key = (report.candidate_identity, report.qualification_report_identity,
               report.policy.policy_identity)
        for entry in self.entries:
            current = (entry.report.candidate_identity, entry.report.qualification_report_identity,
                       entry.report.policy.policy_identity)
            if current == key:
                if entry.report == report:
                    return self
                raise ValueError("DUPLICATE_PROMOTION_DECISION")
        entry = PromotionRegistryEntry(report, len(self.entries) + 1,
            None if not self.entries else self.entries[-1].entry_identity)
        return PromotionRegistry(self.entries + (entry,), self.registry_identity)
