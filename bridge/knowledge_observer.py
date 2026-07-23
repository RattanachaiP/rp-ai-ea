"""Bounded, read-only Decision Engine observation of verified knowledge.

This module is deliberately a bridge: it owns no repository, storage, writer,
or decision authority.  Its only dependency is the injected reader protocol.

The reader deadline is cooperative: it is checked between local file reads and
cannot interrupt one OS-level read already in progress.  Production knowledge
storage must therefore be local disk only, with bounded file size/count, no
network mount, and no recursive scan.
"""
from __future__ import annotations

from collections import OrderedDict
from time import monotonic
from typing import Any, Protocol, Sequence

from learning.knowledge.knowledge import Knowledge


class VerifiedKnowledgeReader(Protocol):
    """The narrow, read-only reader surface permitted to this adapter."""

    def query(self, *, symbol: str, session: str, market_state: str,
              status: str = "ACTIVE", timeout_seconds: float | None = None) -> Sequence[Knowledge]: ...


class KnowledgeObserver:
    """Return bounded provenance metadata without changing a decision input."""

    READER_DEADLINE_SECONDS = 0.035
    TOTAL_BUDGET_SECONDS = 0.050
    CACHE_TTL_SECONDS = 30.0
    CACHE_MAX_KEYS = 256
    RESULT_LIMIT = 20

    def __init__(self, reader: VerifiedKnowledgeReader | None = None, *, enabled: bool = False,
                 clock=monotonic) -> None:
        self._reader = reader
        self._enabled = bool(enabled)
        self._clock = clock
        self._cache: OrderedDict[tuple[str, str, str, str], tuple[float, tuple[Knowledge, ...], bool]] = OrderedDict()
        self._closed = False

    def observe(self, market_context: Any, decision_context: Any) -> dict[str, Any]:
        """Observe ACTIVE verified knowledge; never raise into the decision loop."""
        started = self._clock()
        if self._closed:
            return self._result("READER_UNAVAILABLE", self._enabled, {}, "CLOSED", "OBSERVER_CLOSED", 0, (), (), started)
        if not self._enabled:
            return self._result("DISABLED", False, {}, "NOT_QUERIED", None, 0, (), (), started)
        query_context = self._query_context(market_context, decision_context)
        if query_context is None:
            return self._result("INVALID_CONTEXT", True, {}, "NOT_QUERIED", "INVALID_CONTEXT", 0, (), (), started)
        if self._reader is None:
            return self._result("READER_UNAVAILABLE", True, query_context, "UNAVAILABLE", "READER_UNAVAILABLE", 0, (), (), started)

        key = (query_context["symbol"], query_context["session"], query_context["market_state"], "ACTIVE")
        cached = self._cache.get(key)
        if cached is not None and self._clock() - cached[0] <= self.CACHE_TTL_SECONDS:
            self._cache.move_to_end(key)
            records, limited = cached[1], cached[2]
            return self._metadata(query_context, records, limited, "CACHE_HIT", started)
        if cached is not None:
            del self._cache[key]

        try:
            records = tuple(self._reader.query(**query_context, status="ACTIVE", timeout_seconds=self.READER_DEADLINE_SECONDS))
        except TimeoutError:
            return self._result("READ_ERROR", True, query_context, "TIMEOUT", "READER_TIMEOUT", 0, (), (), started)
        except Exception:
            return self._result("READ_ERROR", True, query_context, "ERROR", "READER_ERROR", 0, (), (), started)

        if self._clock() - started > self.TOTAL_BUDGET_SECONDS:
            return self._result("READ_ERROR", True, query_context, "TIMEOUT", "OBSERVATION_BUDGET_EXCEEDED", 0, (), (), started)
        # The reader contract already filters these, but reject fake/untrusted results safely.
        if any(not isinstance(record, Knowledge) or record.knowledge_status != "ACTIVE" for record in records):
            return self._result("READ_ERROR", True, query_context, "INVALID", "INVALID_READER_RESULT", 0, (), (), started)
        limited = len(records) > self.RESULT_LIMIT
        records = records[:self.RESULT_LIMIT]
        self._cache[key] = (self._clock(), records, limited)
        self._cache.move_to_end(key)
        while len(self._cache) > self.CACHE_MAX_KEYS:
            self._cache.popitem(last=False)
        return self._metadata(query_context, records, limited, "OK", started)

    def shutdown(self) -> None:
        """Stop accepting observations and clear process-local cache state."""
        self._closed = True
        self._cache.clear()

    @staticmethod
    def _query_context(market_context: Any, decision_context: Any) -> dict[str, str] | None:
        if not isinstance(market_context, dict) or not isinstance(decision_context, dict):
            return None
        values = {
            "symbol": market_context.get("symbol", decision_context.get("symbol")),
            "session": market_context.get("session", decision_context.get("session")),
            "market_state": market_context.get("market_state", market_context.get("market_mode", decision_context.get("market_mode"))),
        }
        if any(not isinstance(value, str) or not value.strip() for value in values.values()):
            return None
        return {key: value.strip().upper() for key, value in values.items()}

    def _metadata(self, query_context: dict[str, str], records: tuple[Knowledge, ...], limited: bool,
                  reader_status: str, started: float) -> dict[str, Any]:
        status = "RESULT_LIMITED" if limited else ("MATCHED" if records else "NO_MATCH")
        return self._result(status, True, query_context, reader_status, None, len(records),
                            tuple(record.knowledge_uuid for record in records),
                            tuple(record.knowledge_version for record in records), started)

    def _result(self, status: str, enabled: bool, query_context: dict[str, str], reader_status: str,
                error_code: str | None, count: int, ids: tuple[str, ...], versions: tuple[int, ...],
                started: float) -> dict[str, Any]:
        return {
            "knowledge_observation_enabled": enabled,
            "knowledge_observation_status": status,
            "knowledge_match_count": count,
            "knowledge_ids": list(ids),
            "knowledge_versions": list(versions),
            "query_context": dict(query_context),
            "reader_status": reader_status,
            "error_code": error_code,
            "elapsed_ms": round((self._clock() - started) * 1000, 3),
        }
