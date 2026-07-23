"""Read-only boundary for consumers of verified knowledge.

``KnowledgeReader`` is the sole public read interface intended for consumers
outside :mod:`learning.knowledge`.  It delegates all persistence access to an
injected :class:`KnowledgeRepository`; it neither knows nor accesses storage.

Absent, malformed, unsupported, and invalid records are treated as unavailable:
``get`` and ``latest`` return ``None`` while collection methods return tuples.
Returned records are deeply immutable and expose no mutable repository-owned
state.
"""
from __future__ import annotations

from time import monotonic
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
        if not isinstance(record, Knowledge):
            return None
        return next(
            (
                self._detached(candidate)
                for candidate in self.history(record.pattern_uuid)
                if candidate.knowledge_uuid == knowledge_uuid
            ),
            None,
        )

    def exists(self, knowledge_uuid: str) -> bool:
        """Return whether ``knowledge_uuid`` resolves to readable knowledge."""
        return self.get(knowledge_uuid) is not None

    def latest(self, pattern_uuid: str) -> Knowledge | None:
        """Return the highest valid sequential version for ``pattern_uuid``."""
        records = self.history(pattern_uuid)
        return records[-1] if records else None

    def history(self, pattern_uuid: str) -> tuple[Knowledge, ...]:
        """Return the contiguous valid version lineage in deterministic order.

        Reading stops before the first missing, invalid, or duplicate version.
        A later individually valid record can therefore never bridge a broken
        append-only lineage.
        """
        return tuple(
            self._detached(record)
            for record in self._lineages(lambda: self._repository.history(pattern_uuid))
        )

    def query(
        self,
        *,
        symbol: str | None = None,
        session: str | None = None,
        market_state: str | None = None,
        status: str | None = "ACTIVE",
        timeout_seconds: float | None = None,
    ) -> tuple[Knowledge, ...]:
        """Return valid records matching filters in repository-defined stable order.

        ``status=None`` intentionally requests every valid lifecycle status;
        the default limits consumer reads to active knowledge.
        """
        deadline = monotonic() + timeout_seconds if timeout_seconds is not None else None
        records = self._lineages(self._repository.query, deadline=deadline)
        return tuple(
            self._detached(record)
            for record in records
            if self._matches(
                record,
                symbol=symbol,
                session=session,
                market_state=market_state,
                status=status,
            )
        )

    def load(self, knowledge_uuid: str) -> Knowledge | None:
        """Compatibility alias for :meth:`get`; new consumers should use ``get``."""
        return self.get(knowledge_uuid)

    def _lineages(self, read: Callable[[], list[Knowledge]], *, deadline: float | None = None) -> tuple[Knowledge, ...]:
        """Return only contiguous, individually valid per-pattern lineages.

        The repository may omit unreadable JSON files.  Validating a complete
        unfiltered collection here keeps that omission visible as a version
        gap, while allowing ``query`` to filter the resulting safe lineages.
        """
        try:
            records = read()
        except (OSError, ValueError, TypeError, KeyError):
            return ()

        by_pattern: dict[str, list[Knowledge]] = {}
        for record in records:
            self._check_deadline(deadline)
            if isinstance(record, Knowledge):
                by_pattern.setdefault(record.pattern_uuid, []).append(record)

        lineages: list[Knowledge] = []
        for pattern_uuid in sorted(by_pattern):
            self._check_deadline(deadline)
            versions = sorted(
                by_pattern[pattern_uuid],
                key=lambda item: (item.knowledge_version, item.created_timestamp, item.knowledge_uuid),
            )
            expected_version = 1
            position = 0
            lineage: list[Knowledge] = []
            while position < len(versions):
                self._check_deadline(deadline)
                matching = []
                while position < len(versions) and versions[position].knowledge_version == expected_version:
                    matching.append(versions[position])
                    position += 1
                if len(matching) != 1:
                    break
                try:
                    # Validate every record against the accepted prefix.  This
                    # preserves the repository's sequence invariant while
                    # retaining a complete collection for filtered reads.
                    self._validator.validate(matching[0], lineage)
                except (KnowledgeValidationError, TypeError, ValueError):
                    break
                lineage.append(matching[0])
                expected_version += 1
            lineages.extend(lineage)
        return tuple(sorted(
            lineages,
            key=lambda item: (item.pattern_uuid, item.knowledge_version, item.created_timestamp),
        ))

    @staticmethod
    def _check_deadline(deadline: float | None) -> None:
        if deadline is not None and monotonic() > deadline:
            raise TimeoutError("KNOWLEDGE_READER_DEADLINE_EXCEEDED")

    @staticmethod
    def _matches(
        record: Knowledge,
        *,
        symbol: str | None,
        session: str | None,
        market_state: str | None,
        status: str | None,
    ) -> bool:
        return (
            (status is None or record.knowledge_status == status)
            and (symbol is None or symbol in record.applicable_symbols)
            and (session is None or session in record.applicable_sessions)
            and (market_state is None or market_state in record.applicable_market_states)
        )

    @staticmethod
    def _detached(record: Knowledge) -> Knowledge:
        """Return the immutable record without exposing mutable state."""
        return record
