import pytest

from learning.knowledge import (Knowledge, KnowledgeRepository, KnowledgeValidationError, build, history, latest, load, query)


def verified_pattern(**overrides):
    value = {
        "pattern_uuid": "pattern-1", "validation_uuid": "validation-1", "status": "VERIFIED",
        "conditions": {"symbol": "XAUUSD", "session": "LONDON", "market_state": "TRENDING"},
        "statistics": {"samples": 40, "win_rate": .65, "avg_rr": 1.7},
    }
    value.update(overrides)
    return value


def test_public_api_builds_loads_queries_and_versions_verified_knowledge(tmp_path):
    repository = KnowledgeRepository(tmp_path)
    first = build(verified_pattern(), repository=repository)
    second = build(verified_pattern(validation_uuid="validation-2"), repository=repository)
    assert (first.knowledge_version, second.knowledge_version) == (1, 2)
    assert load(first.knowledge_uuid, repository=repository) == first
    assert query(repository=repository, symbol="XAUUSD") == [first, second]
    assert latest("pattern-1", repository=repository) == second
    assert history("pattern-1", repository=repository) == [first, second]


def test_unverified_patterns_cannot_enter_repository(tmp_path):
    repository = KnowledgeRepository(tmp_path)
    with pytest.raises(ValueError, match="PATTERN_NOT_VERIFIED"):
        repository.build(verified_pattern(status="CANDIDATE"))
    assert repository.query() == []


def test_storage_is_append_only_and_immutable(tmp_path):
    repository = KnowledgeRepository(tmp_path)
    knowledge = repository.build(verified_pattern())
    with pytest.raises(FileExistsError, match="KNOWLEDGE_IMMUTABLE"):
        repository.save(Knowledge.create(
            knowledge_uuid=knowledge.knowledge_uuid, pattern_uuid="pattern-2", validation_uuid="validation-2",
            sample_count=1, verified_win_rate=.5, average_rr=1,
        ))


def test_duplicate_pattern_version_is_rejected(tmp_path):
    repository = KnowledgeRepository(tmp_path)
    repository.build(verified_pattern())

    duplicate = Knowledge.create(
        knowledge_version=1,
        pattern_uuid="pattern-1",
        validation_uuid="validation-duplicate",
        sample_count=40,
        verified_win_rate=.65,
        average_rr=1.7,
    )

    with pytest.raises(KnowledgeValidationError, match="DUPLICATE_KNOWLEDGE_VERSION"):
        repository.save(duplicate)


def test_knowledge_version_must_be_sequential(tmp_path):
    repository = KnowledgeRepository(tmp_path)
    repository.build(verified_pattern())

    skipped_version = Knowledge.create(
        knowledge_version=3,
        pattern_uuid="pattern-1",
        validation_uuid="validation-3",
        sample_count=40,
        verified_win_rate=.65,
        average_rr=1.7,
    )

    with pytest.raises(KnowledgeValidationError, match="INVALID_KNOWLEDGE_VERSION_SEQUENCE"):
        repository.save(skipped_version)

