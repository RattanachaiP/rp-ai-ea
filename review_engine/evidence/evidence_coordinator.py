from typing import Mapping
from .evidence_builder import EvidenceBuilder
from .evidence_repository import EvidenceRepository, EvidenceWriteResult
class EvidenceCoordinator:
 def __init__(self, builder: EvidenceBuilder, repository: EvidenceRepository): self.builder, self.repository = builder, repository
 def create_for_snapshot(self, snapshot: Mapping[str, object]) -> EvidenceWriteResult: return self.repository.save(self.builder.build(snapshot))
