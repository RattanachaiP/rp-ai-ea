"""Validation boundary for the sole future-learning outcome evidence source."""
from dataclasses import dataclass

from .outcome_registry import OutcomeRegistry
from .pipeline_validator import certification_identity

EVIDENCE_CONTRACT_VERSION = "V28.OUTCOME_EVIDENCE.1.1"


@dataclass(frozen=True)
class OutcomeEvidenceContract:
    registry_identity: str
    outcome_identities: tuple[str, ...]
    record_count: int
    authoritative_source: str
    learning_performed: bool
    replay_identity: str
    schema_version: str = EVIDENCE_CONTRACT_VERSION

    def canonical_payload(self):
        return {key: getattr(self, key) for key in self.__dataclass_fields__ if key != "replay_identity"}

    def __post_init__(self):
        if (self.schema_version != EVIDENCE_CONTRACT_VERSION or
                self.authoritative_source != "OUTCOME_REGISTRY_ONLY" or self.learning_performed is not False or
                self.record_count != len(self.outcome_identities) or len(set(self.outcome_identities)) != self.record_count):
            raise ValueError("OUTCOME_EVIDENCE_CONTRACT_INVALID")
        if self.replay_identity != certification_identity("V28_OUTCOME_EVIDENCE_CONTRACT", self.canonical_payload()):
            raise ValueError("OUTCOME_EVIDENCE_REPLAY_INVALID")


def publish_outcome_evidence(registry: OutcomeRegistry) -> OutcomeEvidenceContract:
    OutcomeRegistry(**registry.__dict__)
    identities = tuple(record.outcome_identity for record in registry.expectancy_dataset)
    values = dict(registry_identity=registry.registry_identity, outcome_identities=identities,
                  record_count=len(identities), authoritative_source="OUTCOME_REGISTRY_ONLY",
                  learning_performed=False, schema_version=EVIDENCE_CONTRACT_VERSION)
    return OutcomeEvidenceContract(**values, replay_identity=certification_identity("V28_OUTCOME_EVIDENCE_CONTRACT", values))


def replay_validate(registry: OutcomeRegistry, evidence: OutcomeEvidenceContract) -> bool:
    """Fail closed without consulting broker history or mutable runtime state."""
    try:
        OutcomeRegistry(**registry.__dict__); OutcomeEvidenceContract(**evidence.__dict__)
        return publish_outcome_evidence(registry) == evidence
    except (TypeError, ValueError, AttributeError):
        return False
