"""Read-only boundary for consumers of verified knowledge.

``KnowledgeReader`` is the sole public read interface intended for consumers
outside :mod:`learning.knowledge`.  It delegates all persistence access to an
injected :class:`KnowledgeRepository`; it neither knows nor accesses storage.

Absent, malformed, unsupported, and invalid records are treated as unavailable:
``get`` and ``latest`` return ``None`` while collection methods return tuples.
Returned records are defensive copies, so a consumer cannot mutate the
repository-owned instance through nested mutable values.
"""
from __future__ import annotations

from copy import deepcopy
from typing import Callable

from .knowledge import Knowledge
from .repository import KnowledgeRepository
from .validator import KnowledgeValidationError, KnowledgeValidator


class KnowledgeReader:
    """Read verified, schema-valid knowledge through ``KnowledgeRepository`` only."""

    def __init__(self, repository: KnowledgeRepository | None = None) -> None:
        self._repository = repository or KnowledgeRepository()
        self._validator = KnowledgeValidator()

    def get(self, knowledge_uuid: str) -> Knowledge | None:
        """Return a detached valid record, or ``None`` when it is unavailable."""
        try:
            record = self._repository.load(knowledge_uuid)
        except (OSError, ValueError, TypeError, KeyError):
            return None
        return self._readable(record)

    def exists(self, knowledge_uuid: str) -> bool:
        """Return whether ``knowledge_uuid`` resolves to readable knowledge."""
        return self.get(knowledge_uuid) is not None

    def latest(self, pattern_uuid: str) -> Knowledge | None:
        """Return the highest valid sequential version for ``pattern_uuid``."""
        records = self.history(pattern_uuid)
        return records[-1] if records else None

    def history(self, pattern_uuid: str) -> tuple[Knowledge, ...]:
        """Return all valid versions for a pattern in deterministic version order."""
        return self._records(lambda: self._repository.history(pattern_uuid))

    def query(
        self,
        *,
        symbol: str | None = None,
        session: str | None = None,
        market_state: str | None = None,
        status: str | None = "ACTIVE",
    ) -> tuple[Knowledge, ...]:
        """Return valid records matching filters in repository-defined stable order.

        ``status=None`` intentionally requests every valid lifecycle status;
        the default limits consumer reads to active knowledge.
        """
        return self._records(lambda: self._repository.query(
            symbol=symbol,
            session=session,
            market_state=market_state,
            status=status,
        ))

    def load(self, knowledge_uuid: str) -> Knowledge | None:
        """Compatibility alias for :meth:`get`; new consumers should use ``get``."""
        return self.get(knowledge_uuid)

    def _records(self, read: Callable[[], list[Knowledge]]) -> tuple[Knowledge, ...]:
        try:
            records = read()
        except (OSError, ValueError, TypeError, KeyError):
            return ()
        readable = (self._readable(record) for record in records)
        return tuple(record for record in readable if record is not None)

    def _readable(self, record: Knowledge) -> Knowledge | None:
        """Validate repository output and return a detached copy when it is safe."""
        try:
            # Sequence validation is an append-time repository invariant.  A
            # filtered read can legitimately contain only version two or later.
            self._validator.validate(record, validate_sequence=False)
            return deepcopy(record)
        except (KnowledgeValidationError, TypeError, ValueError):
            return None
