"""Write facade; it accepts only VERIFIED patterns through the builder."""
from __future__ import annotations
from collections.abc import Mapping
from typing import Any
from .knowledge import Knowledge
from .repository import KnowledgeRepository

class KnowledgeWriter:
    def __init__(self, repository: KnowledgeRepository | None = None) -> None:
        self.repository = repository or KnowledgeRepository()
    def build(self, verified_pattern: Mapping[str, Any] | Any, **options: Any) -> Knowledge:
        return self.repository.build(verified_pattern, **options)
