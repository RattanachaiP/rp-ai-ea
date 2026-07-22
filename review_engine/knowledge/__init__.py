"""Passive, deterministic Knowledge Layer built solely from immutable evidence."""

from .pattern_discovery import KnowledgeCoordinator, PatternDiscoveryEngine
from .pattern_repository import PatternRepository

__all__ = ["KnowledgeCoordinator", "PatternDiscoveryEngine", "PatternRepository"]
