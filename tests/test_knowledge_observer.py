"""PR148 regression tests for observation-only knowledge integration."""
from __future__ import annotations

from pathlib import Path

from bridge.knowledge_observer import KnowledgeObserver
from learning.knowledge import Knowledge


def knowledge() -> Knowledge:
    return Knowledge.create(
        pattern_uuid="pattern-1", validation_uuid="validation-1", knowledge_uuid="knowledge-1",
        applicable_symbols=("XAUUSD",), applicable_sessions=("LONDON",),
        applicable_market_states=("TREND",), sample_count=40, verified_win_rate=0.65, average_rr=1.7,
    )


class Reader:
    def __init__(self, result=(), error: Exception | None = None) -> None:
        self.result, self.error, self.calls = result, error, 0

    def query(self, **kwargs):
        self.calls += 1
        if self.error:
            raise self.error
        assert kwargs == {"symbol": "XAUUSD", "session": "LONDON", "market_state": "TREND", "status": "ACTIVE"}
        return self.result


CONTEXT = {"symbol": "xauusd", "session": "london", "market_mode": "trend"}
DECISION = {"direction": "BUY", "bias": "BUY", "execution_state": "EXECUTE", "confidence": 72,
            "risk": {"lot_size": 0.01}, "management_mode": "HOLD_TRAIL"}


def test_disabled_by_default_does_not_query_reader() -> None:
    reader = Reader((knowledge(),))
    result = KnowledgeObserver(reader).observe(CONTEXT, DECISION)
    assert reader.calls == 0
    assert result["knowledge_observation_status"] == "DISABLED"
    assert result["knowledge_observation_enabled"] is False


def test_enabled_observation_returns_metadata_only_and_preserves_inputs() -> None:
    record, reader = knowledge(), Reader((knowledge(),))
    before = {key: value.copy() if isinstance(value, dict) else value for key, value in DECISION.items()}
    result = KnowledgeObserver(reader, enabled=True).observe(CONTEXT, DECISION)
    assert reader.calls == 1
    assert result["knowledge_observation_status"] == "MATCHED"
    assert result["knowledge_ids"] == [record.knowledge_uuid]
    assert result["knowledge_versions"] == [record.knowledge_version]
    assert DECISION == before
    assert "confidence" not in result and "risk" not in result
    # The returned metadata has no handle to immutable Knowledge content.
    assert record.confidence_placeholder is None


def test_enabled_no_match_unavailable_and_exception_fail_open() -> None:
    assert KnowledgeObserver(Reader(), enabled=True).observe(CONTEXT, DECISION)["knowledge_observation_status"] == "NO_MATCH"
    assert KnowledgeObserver(None, enabled=True).observe(CONTEXT, DECISION)["knowledge_observation_status"] == "READER_UNAVAILABLE"
    result = KnowledgeObserver(Reader(error=OSError("down")), enabled=True).observe(CONTEXT, DECISION)
    assert result["knowledge_observation_status"] == "READ_ERROR"
    assert result["error_code"] == "READER_ERROR"


def test_behavioral_equivalence_disabled_no_match_and_match() -> None:
    from bridge import ai_decision_engine_xauusd_v26_execution_confidence_engine as engine

    original = {key: value.copy() if isinstance(value, dict) else value for key, value in DECISION.items()}
    disabled = engine.attach_knowledge_observation(DECISION, CONTEXT)
    no_match = engine.attach_knowledge_observation(DECISION, CONTEXT, observer=KnowledgeObserver(Reader(), enabled=True))
    observed = engine.attach_knowledge_observation(
        DECISION, CONTEXT, observer=KnowledgeObserver(Reader((knowledge(),)), enabled=True),
    )
    assert disabled is DECISION
    assert DECISION == original
    authoritative_fields = ("direction", "bias", "execution_state", "confidence", "risk", "management_mode")
    assert all(disabled[field] == no_match[field] == observed[field] for field in authoritative_fields)
    assert observed["diagnostics"]["knowledge_observation"]["knowledge_observation_status"] == "MATCHED"
    assert no_match["diagnostics"]["knowledge_observation"]["knowledge_observation_status"] == "NO_MATCH"


def test_architecture_dependencies_keep_repository_storage_writer_and_executor_isolated() -> None:
    root = Path(__file__).parents[1]
    engine_source = (root / "bridge" / "ai_decision_engine_xauusd_v26_execution_confidence_engine.py").read_text()
    observer_source = (root / "bridge" / "knowledge_observer.py").read_text()
    for source in (engine_source,):
        assert "KnowledgeRepository" not in source
        assert "KnowledgeStorage" not in source
    assert "KnowledgeBuilder" not in observer_source
    for path in (root / "bridge" / "decision_writer.py", root / "executor.py"):
        if path.exists():
            assert "learning.knowledge" not in path.read_text()
