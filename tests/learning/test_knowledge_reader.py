"""Regression coverage for the verified-knowledge read boundary."""
from __future__ import annotations

import ast
import inspect
from pathlib import Path

from learning.knowledge import KnowledgeReader, KnowledgeRepository


def verified_pattern(**overrides: object) -> dict[str, object]:
    value: dict[str, object] = {
        "pattern_uuid": "pattern-1",
        "validation_uuid": "validation-1",
        "status": "VERIFIED",
        "conditions": {"symbol": "XAUUSD", "session": "LONDON", "market_state": "TRENDING"},
        "statistics": {"samples": 40, "win_rate": 0.65, "avg_rr": 1.7},
    }
    value.update(overrides)
    return value


def test_reader_reads_through_repository_and_returns_verified_knowledge(tmp_path: Path) -> None:
    repository = KnowledgeRepository(tmp_path)
    knowledge = repository.build(verified_pattern())

    reader = KnowledgeReader(repository)

    assert reader.get(knowledge.knowledge_uuid) == knowledge
    assert reader.exists(knowledge.knowledge_uuid) is True
    assert reader.exists("missing") is False


def test_reader_has_no_storage_dependency_or_write_operations() -> None:
    source = inspect.getsource(__import__("learning.knowledge.reader", fromlist=["KnowledgeReader"]))
    tree = ast.parse(source)
    imported = {
        alias.name
        for node in ast.walk(tree) if isinstance(node, ast.ImportFrom)
        for alias in node.names
    }

    assert "KnowledgeStorage" not in imported
    assert not {"build", "save", "promote", "write", "archive", "delete"} & set(dir(KnowledgeReader))


def test_reader_excludes_invalid_or_non_active_records_and_handles_empty_repository(tmp_path: Path) -> None:
    repository = KnowledgeRepository(tmp_path)
    active = repository.build(verified_pattern())
    repository.build(verified_pattern(validation_uuid="validation-2"), knowledge_status="ARCHIVED")
    (tmp_path / "knowledge" / "knowledge_candidate.json").write_text(
        '{"knowledge_uuid":"candidate","knowledge_version":3,"pattern_uuid":"pattern-1",'
        '"validation_uuid":"candidate","created_timestamp":"2026-01-01T00:00:00Z",'
        '"applicable_symbols":[],"applicable_sessions":[],"applicable_market_states":[],'
        'sample_count":0,"verified_win_rate":0.0,"average_rr":0.0,"confidence_placeholder":null,'
        '"knowledge_status":"CANDIDATE","schema_version":"1.0"}',
        encoding="utf-8",
    )
    malformed = tmp_path / "knowledge" / "knowledge_malformed.json"
    malformed.write_text("{not-json", encoding="utf-8")
    reader = KnowledgeReader(repository)

    assert reader.query() == (active,)
    assert reader.query(status=None) == (active, reader.latest("pattern-1"))
    assert KnowledgeReader(KnowledgeRepository(tmp_path / "empty")).query() == ()
    assert KnowledgeReader(KnowledgeRepository(tmp_path / "empty")).history("missing") == ()
    assert KnowledgeReader(KnowledgeRepository(tmp_path / "empty")).latest("missing") is None


def test_reader_history_latest_query_and_defensive_copy_are_deterministic(tmp_path: Path) -> None:
    repository = KnowledgeRepository(tmp_path)
    first = repository.build(verified_pattern(confidence_placeholder={"nested": ["original"]}))
    second = repository.build(verified_pattern(validation_uuid="validation-2"))
    other = repository.build(verified_pattern(pattern_uuid="pattern-2", validation_uuid="validation-3"))
    reader = KnowledgeReader(repository)

    assert reader.history("pattern-1") == (first, second)
    assert reader.latest("pattern-1") == second
    assert reader.query(symbol="XAUUSD", session="LONDON", market_state="TRENDING") == (first, second, other)

    returned = reader.get(first.knowledge_uuid)
    assert returned is not None
    returned.confidence_placeholder["nested"].append("consumer-change")
    assert reader.get(first.knowledge_uuid).confidence_placeholder == {"nested": ["original"]}
