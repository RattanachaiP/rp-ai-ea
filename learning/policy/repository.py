"""Read/write repository limited to immutable policy evaluation artifacts."""
from .storage import PolicyEvaluationStorage
class PolicyEvaluationRepository:
    def __init__(self, root="learning_data"): self.storage = PolicyEvaluationStorage(root)
    def save(self, report): return self.storage.write(report)
    def history(self, knowledge_uuid=None):
        reports = self.storage.all()
        return tuple(item for item in reports if knowledge_uuid is None or item.knowledge_uuid == knowledge_uuid)
