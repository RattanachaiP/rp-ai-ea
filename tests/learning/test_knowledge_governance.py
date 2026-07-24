from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace

import pytest

from learning.governance import (
    GovernanceRepository,
    GovernanceStorage,
    GovernanceValidationError,
    KnowledgeGovernance,
)


def governance(**changes):
    value = KnowledgeGovernance(
        knowledge_uuid="knowledge-1",
        pattern_uuid="pattern-1",
        validation_uuid="validation-1",
        analytics_uuid="analytics-1",
        source_baseline_commit="6e4258261adf30f42c59c5a91511f2e0ab895049",
        rule_version="1.0",
        analytics_version="1.0",
        current_lifecycle_state="DRAFT",
        lineage_reference="pattern-1/1",
        production_eligible=False,
    )
    return replace(value, **changes)


def test_governance_persists_every_required_metadata_field(tmp_path):
    repo = GovernanceRepository(tmp_path)
    saved = governance()
    assert repo.save(saved) == repo.storage.path_for("knowledge-1", 1)
    assert repo.load("knowledge-1").to_dict() == saved.to_dict()
    assert set(saved.to_dict()) >= {
        "knowledge_uuid",
        "pattern_uuid",
        "validation_uuid",
        "analytics_uuid",
        "source_baseline_commit",
        "schema_version",
        "rule_version",
        "analytics_version",
        "promotion_timestamp",
        "retirement_timestamp",
        "current_lifecycle_state",
        "lineage_reference",
        "production_eligible",
    }


def test_lifecycle_transitions_are_explicit_and_append_only(tmp_path):
    repo = GovernanceRepository(tmp_path)
    draft = governance()
    repo.save(draft)
    verified = replace(draft, current_lifecycle_state="VERIFIED", record_version=2)
    repo.save(verified)
    active = replace(
        verified,
        current_lifecycle_state="ACTIVE",
        promotion_timestamp="2026-07-24T00:00:00Z",
        production_eligible=True,
        record_version=3,
    )
    repo.save(active)
    retired = replace(
        active,
        current_lifecycle_state="RETIRED",
        production_eligible=False,
        retirement_timestamp="2026-07-25T00:00:00Z",
        record_version=4,
    )
    repo.save(retired)
    assert [item.current_lifecycle_state for item in repo.history("knowledge-1")] == [
        "DRAFT",
        "VERIFIED",
        "ACTIVE",
        "RETIRED",
    ]
    assert repo.query(lifecycle_state="RETIRED") == [retired]


@pytest.mark.parametrize("starting_state", ["DRAFT", "VERIFIED"])
def test_unpromoted_records_can_be_archived_without_promotion_timestamp(tmp_path, starting_state):
    repo = GovernanceRepository(tmp_path)
    initial = governance(current_lifecycle_state=starting_state)
    repo.save(initial)
    archived = replace(initial, current_lifecycle_state="ARCHIVED", record_version=2)
    repo.save(archived)
    assert repo.load("knowledge-1") == archived
    assert archived.promotion_timestamp is None


def test_validator_rejects_automatic_or_invalid_lifecycle_metadata(tmp_path):
    repo = GovernanceRepository(tmp_path)
    repo.save(governance())
    with pytest.raises(GovernanceValidationError, match="INVALID_LIFECYCLE_TRANSITION"):
        repo.save(
            replace(
                governance(),
                current_lifecycle_state="RETIRED",
                promotion_timestamp="2026-07-24T00:00:00Z",
                retirement_timestamp="2026-07-25T00:00:00Z",
                record_version=2,
            )
        )
    with pytest.raises(GovernanceValidationError, match="INELIGIBLE_LIFECYCLE_STATE"):
        repo.save(replace(governance(), production_eligible=True, record_version=2))


def test_storage_idempotent_replay_returns_same_path(tmp_path):
    storage = GovernanceStorage(tmp_path)
    record = governance()
    first = storage.write(record)
    second = storage.write(record)
    assert first == second
    assert len(storage.all()) == 1


def test_concurrent_identical_writers_publish_one_immutable_record(tmp_path):
    record = governance()

    def publish(_):
        return GovernanceStorage(tmp_path).write(record)

    with ThreadPoolExecutor(max_workers=8) as executor:
        paths = list(executor.map(publish, range(16)))

    assert len(set(paths)) == 1
    assert GovernanceStorage(tmp_path).all() == [record]
    assert not list((tmp_path / "governance").glob("*.tmp"))


def test_conflicting_replay_cannot_replace_published_record(tmp_path):
    storage = GovernanceStorage(tmp_path)
    storage.write(governance())
    conflicting = replace(governance(), pattern_uuid="pattern-conflict")
    with pytest.raises(FileExistsError, match="GOVERNANCE_IMMUTABLE"):
        storage.write(conflicting)
    assert storage.all() == [governance()]


def test_interrupted_temporary_file_is_ignored_and_clean_publication_succeeds(tmp_path):
    storage = GovernanceStorage(tmp_path)
    storage.directory.mkdir(parents=True)
    interrupted = storage.directory / ".governance_knowledge-1_1.json.crash.tmp"
    interrupted.write_text('{"partial":', encoding="utf-8")

    assert storage.all() == []
    path = storage.write(governance())
    assert path.exists()
    assert storage.all() == [governance()]


def test_governance_never_changes_knowledge_runtime_records(tmp_path):
    from learning.knowledge import Knowledge, KnowledgeRepository

    knowledge_repo = KnowledgeRepository(tmp_path)
    knowledge = Knowledge.create(
        pattern_uuid="pattern-1",
        validation_uuid="validation-1",
        sample_count=1,
        verified_win_rate=.5,
        average_rr=1,
    )
    knowledge_repo.save(knowledge)
    before = knowledge_repo.load(knowledge.knowledge_uuid).to_dict()
    GovernanceRepository(tmp_path).save(
        replace(
            governance(),
            knowledge_uuid=knowledge.knowledge_uuid,
            pattern_uuid=knowledge.pattern_uuid,
            validation_uuid=knowledge.validation_uuid,
        )
    )
    assert knowledge_repo.load(knowledge.knowledge_uuid).to_dict() == before
