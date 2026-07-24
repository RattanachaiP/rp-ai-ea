"""Narrow persistence facade; evaluation never persists implicitly."""
from .storage import PromotionDecisionStorage

class PromotionDecisionRepository:
    def __init__(self, root="learning_data"): self.storage = PromotionDecisionStorage(root)
    def save(self, report): return self.storage.write(report)
