import logging
from typing import Mapping
from .evidence_builder import EvidenceBuilder
from .evidence_repository import EvidenceRepository, EvidenceWriteResult
class EvidenceCoordinator:
 def __init__(self, builder: EvidenceBuilder, repository: EvidenceRepository, knowledge_coordinator=None): self.builder, self.repository, self.knowledge_coordinator = builder, repository, knowledge_coordinator
 def create_for_snapshot(self, snapshot: Mapping[str, object]) -> EvidenceWriteResult:
  result = self.repository.save(self.builder.build(snapshot))
  if result.created and self.knowledge_coordinator is not None:
   future = self.knowledge_coordinator.process_async()
   future.add_done_callback(self._log_knowledge_failure)
  return result
 @staticmethod
 def _log_knowledge_failure(future):
  try: future.result()
  except Exception: logging.getLogger(__name__).exception("asynchronous knowledge processing failed", exc_info=True)
