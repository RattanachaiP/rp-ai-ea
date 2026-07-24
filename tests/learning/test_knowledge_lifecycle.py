from concurrent.futures import ThreadPoolExecutor
from dataclasses import FrozenInstanceError

import pytest

from learning.lifecycle import (
    LifecycleRepository,
    LifecycleStorage,
    LifecycleValidationError,
    current_state,
    history,
    timeline,
    transition,
    validate_transition,
)


def event(repo, previous, new, *, timestamp, transition_uuid):
    return transition(
        repository=repo, knowledge_uuid="knowledge-1", previous_state=previous, new_state=new,
        triggering_component="governance", reason="operator-request", governance_version="1.0",
        lifecycle_version="1.0", timestamp=timestamp, transition_uuid=transition_uuid,
    )


def test_legal_transition_persists_complete_immutable_audit_event(tmp_path):
    repo = LifecycleRepository(tmp_path)
    saved = event(repo, "DRAFT", "VERIFIED", timestamp="2026-07-24T00:00:00Z",
                  transition_uuid="00000000-0000-4000-8000-000000000001")
    assert current_state("knowledge-1", repository=repo) == "VERIFIED"
    assert history("knowledge-1", repository=repo) == (saved,)
    assert timeline("knowledge-1", repository=repo) == (saved.to_dict(),)
    assert saved.to_dict()["schema_version"] == "1.0"
    with pytest.raises(FrozenInstanceError):
        saved.reason = "changed"  # type: ignore[misc]


@pytest.mark.parametrize("previous,new", [("DRAFT", "ACTIVE"), ("ACTIVE", "ARCHIVED"), ("ARCHIVED", "ACTIVE")])
def test_illegal_transitions_are_rejected(tmp_path, previous, new):
    with pytest.raises(LifecycleValidationError, match="INVALID_LIFECYCLE_TRANSITION"):
        validate_transition(previous, new)
    repo = LifecycleRepository(tmp_path)
    with pytest.raises(LifecycleValidationError):
        event(repo, previous, new, timestamp="2026-07-24T00:00:00Z",
              transition_uuid="00000000-0000-4000-8000-000000000001")


def test_first_event_must_start_from_draft(tmp_path):
    repo = LifecycleRepository(tmp_path)
    with pytest.raises(LifecycleValidationError, match="INVALID_INITIAL_STATE"):
        event(repo, "VERIFIED", "ACTIVE", timestamp="2026-07-24T00:00:00Z",
              transition_uuid="00000000-0000-4000-8000-000000000001")


def test_append_only_storage_rejects_conflicts_and_replays_identically(tmp_path):
    repo = LifecycleRepository(tmp_path)
    first = event(repo, "DRAFT", "VERIFIED", timestamp="2026-07-24T00:00:00Z",
                  transition_uuid="00000000-0000-4000-8000-000000000001")
    assert repo.append(first) == repo.storage.path_for(first.transition_uuid)
    conflict = first.create(
        knowledge_uuid="knowledge-1", previous_state="DRAFT", new_state="VERIFIED",
        triggering_component="governance", reason="different", governance_version="1.0",
        lifecycle_version="1.0", timestamp="2026-07-24T00:00:00Z", transition_uuid=first.transition_uuid,
    )
    with pytest.raises(FileExistsError, match="LIFECYCLE_IMMUTABLE"):
        repo.append(conflict)
    assert repo.history("knowledge-1") == (first,)


def test_replay_is_deterministic_and_concurrent_competing_transition_is_protected(tmp_path):
    repo = LifecycleRepository(tmp_path)
    event(repo, "DRAFT", "VERIFIED", timestamp="2026-07-24T00:00:00Z",
          transition_uuid="00000000-0000-4000-8000-000000000001")

    def promote(number):
        return event(repo, "VERIFIED", "ACTIVE", timestamp="2026-07-24T00:00:01Z",
                     transition_uuid=f"00000000-0000-4000-8000-{number:012d}")

    with ThreadPoolExecutor(max_workers=2) as executor:
        futures = [executor.submit(promote, number) for number in (2, 3)]
    successes = [future.result() for future in futures if future.exception() is None]
    failures = [future.exception() for future in futures if future.exception() is not None]
    assert len(successes) == 1
    assert len(failures) == 1
    assert isinstance(failures[0], LifecycleValidationError)
    assert [item.new_state for item in repo.history("knowledge-1")] == ["VERIFIED", "ACTIVE"]
    assert LifecycleStorage(tmp_path).all() == list(repo.history("knowledge-1"))
    assert not list((tmp_path / "lifecycle").glob("*.lock"))


def test_equal_timestamp_is_rejected_to_preserve_replay_order(tmp_path):
    repo = LifecycleRepository(tmp_path)
    event(repo, "DRAFT", "VERIFIED", timestamp="2026-07-24T00:00:00Z",
          transition_uuid="00000000-0000-4000-8000-000000000001")
    with pytest.raises(LifecycleValidationError, match="NON_MONOTONIC_TIMESTAMP"):
        event(repo, "VERIFIED", "ACTIVE", timestamp="2026-07-24T00:00:00Z",
              transition_uuid="00000000-0000-4000-8000-000000000002")


def test_storage_rejects_invalid_uuid_at_boundary(tmp_path):
    with pytest.raises(ValueError, match="INVALID_TRANSITION_UUID"):
        LifecycleStorage(tmp_path).path_for("../../escape")


def test_interrupted_temporary_file_is_ignored(tmp_path):
    storage = LifecycleStorage(tmp_path)
    storage.directory.mkdir(parents=True)
    (storage.directory / ".transition_crash.json.partial.tmp").write_text('{"partial":', encoding="utf-8")
    assert storage.all() == []
