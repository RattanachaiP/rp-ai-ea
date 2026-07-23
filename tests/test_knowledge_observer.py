"""PR148 regression tests for isolated, observation-only knowledge reads."""
from __future__ import annotations

from dataclasses import replace
from pathlib import Path
from threading import Event

from bridge.knowledge_observer import KnowledgeObserver
from learning.knowledge import Knowledge


def knowledge(identifier: str = "knowledge-1") -> Knowledge:
    return Knowledge.create(pattern_uuid=f"pattern-{identifier}", validation_uuid="validation-1", knowledge_uuid=identifier,
                            applicable_symbols=("XAUUSD",), applicable_sessions=("LONDON",),
                            applicable_market_states=("TREND",), sample_count=40, verified_win_rate=0.65, average_rr=1.7)


class Reader:
    def __init__(self, result=(), error: Exception | None = None) -> None:
        self.result, self.error, self.calls = result, error, 0

    def query(self, **kwargs):
        self.calls += 1
        if self.error:
            raise self.error
        return self.result


CONTEXT = {"symbol": "xauusd", "session": "london", "market_mode": "trend"}
DECISION = {"direction": "BUY", "bias": "BUY", "execution_state": "EXECUTE", "confidence": 72,
            "risk": {"lot_size": 0.01}, "management_mode": "HOLD_TRAIL"}


def test_disabled_by_default_does_not_query_reader() -> None:
    reader = Reader((knowledge(),))
    result = KnowledgeObserver(reader).observe(CONTEXT, DECISION)
    assert reader.calls == 0 and result["knowledge_observation_status"] == "DISABLED"


def test_enabled_metadata_is_read_only_and_rejects_inactive_or_invalid_results() -> None:
    observer = KnowledgeObserver(Reader((knowledge(),)), enabled=True)
    before = {key: value.copy() if isinstance(value, dict) else value for key, value in DECISION.items()}
    assert observer.observe(CONTEXT, DECISION)["knowledge_observation_status"] == "MATCHED"
    assert DECISION == before
    assert KnowledgeObserver(Reader((replace(knowledge(), knowledge_status="ARCHIVED"),)), enabled=True).observe(CONTEXT, DECISION)["error_code"] == "INVALID_READER_RESULT"
    assert KnowledgeObserver(Reader((object(),)), enabled=True).observe(CONTEXT, DECISION)["error_code"] == "INVALID_READER_RESULT"


def test_timeout_rotates_worker_and_a_later_cycle_recovers() -> None:
    release = Event()

    class SlowThenFast:
        calls = 0
        def query(self, **kwargs):
            self.calls += 1
            if self.calls == 1:
                release.wait()
            return (knowledge(),)

    reader = SlowThenFast()
    observer = KnowledgeObserver(reader, enabled=True)
    assert observer.observe(CONTEXT, DECISION)["error_code"] == "READER_TIMEOUT"
    assert observer.observe(CONTEXT, DECISION)["knowledge_observation_status"] == "MATCHED"
    release.set()
    observer.shutdown()


def test_repeated_timeouts_are_capped_and_shutdown_releases_resources() -> None:
    release = Event()
    class BlockingReader:
        def query(self, **kwargs):
            release.wait()
            return ()

    observer = KnowledgeObserver(BlockingReader(), enabled=True)
    assert observer.observe(CONTEXT, DECISION)["error_code"] == "READER_TIMEOUT"
    assert observer.observe(CONTEXT, DECISION)["error_code"] == "READER_TIMEOUT"
    assert observer.observe(CONTEXT, DECISION)["error_code"] == "ORPHAN_LIMIT_REACHED"
    assert len(observer._orphaned) == observer.MAX_ORPHANED_WORKERS
    observer.shutdown()
    assert observer._orphaned == [] and observer._cache == {}
    release.set()


def test_cache_ttl_lru_and_result_cap() -> None:
    now = [0.0]
    reader = Reader(tuple(knowledge(str(index)) for index in range(21)))
    observer = KnowledgeObserver(reader, enabled=True, clock=lambda: now[0])
    result = observer.observe(CONTEXT, DECISION)
    assert result["knowledge_observation_status"] == "RESULT_LIMITED" and result["knowledge_match_count"] == 20
    assert reader.calls == 1
    observer.observe(CONTEXT, DECISION)
    assert reader.calls == 1
    now[0] += observer.CACHE_TTL_SECONDS + 1
    observer.observe(CONTEXT, DECISION)
    assert reader.calls == 2
    reader.result = ()
    for index in range(257):
        observer.observe({"symbol": f"X{index}", "session": "LONDON", "market_mode": "TREND"}, DECISION)
    assert len(observer._cache) == observer.CACHE_MAX_KEYS


def test_payload_isolation_and_audit_sink_are_outside_decision_publication() -> None:
    from bridge import ai_decision_engine_xauusd_v26_execution_confidence_engine as engine
    events: list[dict] = []
    class Sink:
        def record(self, observation): events.append(observation)

    observer = KnowledgeObserver(Reader((knowledge("secret-id"),)), enabled=True)
    assert engine.observe_knowledge(DECISION, CONTEXT, observer=observer, audit_sink=Sink()) is DECISION
    published = engine.brain_decision_publication(DECISION)
    assert published is DECISION and events[0]["knowledge_ids"] == ["secret-id"]
    assert "knowledge" not in str(published).lower()


def test_architecture_dependencies_keep_repository_storage_writer_and_executor_isolated() -> None:
    root = Path(__file__).parents[1]
    engine_source = (root / "bridge" / "ai_decision_engine_xauusd_v26_execution_confidence_engine.py").read_text()
    observer_source = (root / "bridge" / "knowledge_observer.py").read_text()
    assert "KnowledgeRepository" not in engine_source and "KnowledgeStorage" not in engine_source
    assert "KnowledgeBuilder" not in observer_source
    for path in (root / "bridge" / "decision_writer.py", root / "executor.py"):
        if path.exists():
            assert "learning.knowledge" not in path.read_text()
