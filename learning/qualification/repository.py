from .storage import QualificationStorage
class QualificationRepository:
    def __init__(self, root="learning_data"): self.storage = QualificationStorage(root)
    def save(self, report): return self.storage.write(report)
