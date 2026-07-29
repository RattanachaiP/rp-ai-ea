"""Append-only registry and the authoritative expectancy evidence dataset."""
from dataclasses import dataclass

from .outcome_contract import OutcomeRecord
from .pipeline_validator import certification_identity

REGISTRY_SCHEMA_VERSION = "V28.OUTCOME_REGISTRY.1.0"


@dataclass(frozen=True)
class OutcomeRegistryEntry:
    sequence: int
    previous_entry_identity: str | None
    outcome: OutcomeRecord
    entry_identity: str

    def canonical_payload(self):
        return {key: getattr(self, key) for key in self.__dataclass_fields__ if key != "entry_identity"}

    def __post_init__(self):
        OutcomeRecord(**self.outcome.__dict__)
        if self.sequence < 1 or (self.sequence == 1) != (self.previous_entry_identity is None):
            raise ValueError("OUTCOME_REGISTRY_ENTRY_SEQUENCE_INVALID")
        if self.entry_identity != certification_identity("V28_OUTCOME_REGISTRY_ENTRY", self.canonical_payload()):
            raise ValueError("OUTCOME_REGISTRY_ENTRY_IDENTITY_INVALID")


@dataclass(frozen=True)
class OutcomeRegistry:
    entries: tuple[OutcomeRegistryEntry, ...]
    previous_registry_identity: str | None
    registry_identity: str
    schema_version: str = REGISTRY_SCHEMA_VERSION

    def canonical_payload(self):
        return {key: getattr(self, key) for key in self.__dataclass_fields__ if key != "registry_identity"}

    def __post_init__(self):
        if self.schema_version != REGISTRY_SCHEMA_VERSION or (not self.entries) != (self.previous_registry_identity is None):
            raise ValueError("OUTCOME_REGISTRY_VERSION_OR_LINEAGE_INVALID")
        seen = set()
        for index, entry in enumerate(self.entries, 1):
            OutcomeRegistryEntry(**entry.__dict__)
            previous = None if index == 1 else self.entries[index - 2].entry_identity
            if entry.sequence != index or entry.previous_entry_identity != previous or entry.outcome.outcome_identity in seen:
                raise ValueError("OUTCOME_REGISTRY_LINEAGE_INVALID")
            seen.add(entry.outcome.outcome_identity)
        if self.registry_identity != certification_identity("V28_OUTCOME_REGISTRY", self.canonical_payload()):
            raise ValueError("OUTCOME_REGISTRY_IDENTITY_INVALID")

    def append(self, outcome: OutcomeRecord) -> "OutcomeRegistry":
        OutcomeRecord(**outcome.__dict__)
        if outcome.outcome_identity in {entry.outcome.outcome_identity for entry in self.entries}:
            raise ValueError("OUTCOME_REPLAY_DUPLICATE")
        if outcome.trade_identity in {entry.outcome.trade_identity for entry in self.entries}:
            raise ValueError("OUTCOME_TRADE_DUPLICATE")
        previous = self.entries[-1].entry_identity if self.entries else None
        values = {"sequence": len(self.entries) + 1, "previous_entry_identity": previous, "outcome": outcome}
        entry = OutcomeRegistryEntry(**values, entry_identity=certification_identity("V28_OUTCOME_REGISTRY_ENTRY", values))
        registry_values = {"entries": self.entries + (entry,), "previous_registry_identity": self.registry_identity,
                           "schema_version": self.schema_version}
        return OutcomeRegistry(**registry_values, registry_identity=certification_identity("V28_OUTCOME_REGISTRY", registry_values))

    @property
    def expectancy_dataset(self) -> tuple[OutcomeRecord, ...]:
        """Evidence-only dataset; no aggregation, learning, or threshold tuning."""
        return tuple(entry.outcome for entry in self.entries)


def create_outcome_registry() -> OutcomeRegistry:
    values = {"entries": (), "previous_registry_identity": None, "schema_version": REGISTRY_SCHEMA_VERSION}
    return OutcomeRegistry(**values, registry_identity=certification_identity("V28_OUTCOME_REGISTRY", values))
