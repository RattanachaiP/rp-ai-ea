"""PR190 immutable execution-package consumer tests."""

from dataclasses import FrozenInstanceError
import json
from pathlib import Path
import sys

import pytest

sys.path.insert(0, str(Path(__file__).parents[2]))
sys.path.insert(1, str(Path(__file__).parent))

from learning.execution_package.identity import canonical_bytes, digest
from learning.execution_package_consumer import (
    ExecutionPackageCompatibility, ExecutionPackageConsumer,
    ExecutionPackageConsumerError,
)
from test_pr189_execution_package import setup_engine


def assembled(tmp_path):
    readiness, environment, feasibility, engine = setup_engine(tmp_path)
    package, _ = engine.run(readiness, environment, feasibility)
    return package, engine.repository, ExecutionPackageConsumer(engine.repository)


def rewrite(repository, package_uuid, mutate, canonical=True):
    path = repository.root / f"{package_uuid}.json"
    value = json.loads(path.read_text())
    mutate(value)
    path.write_bytes(canonical_bytes(value) if canonical else json.dumps(value, indent=2).encode())


def test_valid_package_loading_and_immutable_access(tmp_path):
    package, _, consumer = assembled(tmp_path)
    loaded = consumer.load(package.execution_package_uuid)
    assert loaded == package
    assert loaded.advisory_only is True
    with pytest.raises(FrozenInstanceError):
        loaded.package_state = "REJECTED"


def test_missing_package_fails_closed(tmp_path):
    _, repository, consumer = assembled(tmp_path)
    missing = "00000000-0000-5000-8000-000000000000"
    assert not (repository.root / f"{missing}.json").exists()
    with pytest.raises(ExecutionPackageConsumerError, match="PACKAGE_MISSING"):
        consumer.load(missing)


def test_invalid_uuid_fails_closed(tmp_path):
    _, _, consumer = assembled(tmp_path)
    with pytest.raises(ExecutionPackageConsumerError, match="INVALID_UUID"):
        consumer.load("not-a-uuid")


def test_invalid_digest_fails_closed(tmp_path):
    package, repository, consumer = assembled(tmp_path)
    rewrite(repository, package.execution_package_uuid,
            lambda value: value.update(execution_package_digest="0" * 64))
    with pytest.raises(ExecutionPackageConsumerError, match="SHA256_MISMATCH"):
        consumer.load(package.execution_package_uuid)


def test_snapshot_mismatch_fails_closed(tmp_path):
    package, repository, consumer = assembled(tmp_path)
    snapshot = repository.latest_snapshot()
    path = repository.snapshot_root / f"{snapshot.snapshot_uuid}.json"
    value = json.loads(path.read_text())
    value["package_identities"] = []
    path.write_bytes(canonical_bytes(value))
    with pytest.raises(ExecutionPackageConsumerError, match="SNAPSHOT_MISMATCH"):
        consumer.load(package.execution_package_uuid)


def test_engine_version_mismatch_fails_closed(tmp_path):
    package, repository, consumer = assembled(tmp_path)
    def change(value):
        value["package_engine_version"] = "PR189.99.0"
        value["engine_versions"][-1][1] = "PR189.99.0"
        payload = {key: item for key, item in value.items() if key != "execution_package_digest"}
        value["execution_package_digest"] = digest(payload)
    rewrite(repository, package.execution_package_uuid, change)
    with pytest.raises(ExecutionPackageConsumerError, match="UNSUPPORTED_ENGINE_VERSION"):
        consumer.load(package.execution_package_uuid)


def test_replay_identity_mismatch_fails_closed(tmp_path):
    package, repository, consumer = assembled(tmp_path)
    def change(value):
        value["package_reason"] = "IMMUTABLE_ADVISORY_PACKAGE_ASSEMBLED "
        payload = {key: item for key, item in value.items() if key != "execution_package_digest"}
        value["execution_package_digest"] = digest(payload)
    rewrite(repository, package.execution_package_uuid, change)
    with pytest.raises(ExecutionPackageConsumerError, match="REPLAY_IDENTITY_FAILURE"):
        consumer.load(package.execution_package_uuid)


def test_canonical_deserialization_rejects_noncanonical_json(tmp_path):
    package, repository, consumer = assembled(tmp_path)
    rewrite(repository, package.execution_package_uuid, lambda value: None, canonical=False)
    with pytest.raises(ExecutionPackageConsumerError, match="SERIALIZATION_FAILURE"):
        consumer.load(package.execution_package_uuid)


def test_package_version_mismatch_fails_closed(tmp_path):
    _, repository, _consumer = assembled(tmp_path)
    incompatible = ExecutionPackageConsumer(repository,
        ExecutionPackageCompatibility(package_versions=("unsupported",)))
    other_package = repository.records()[0]
    with pytest.raises(ExecutionPackageConsumerError, match="UNSUPPORTED_PACKAGE_VERSION"):
        incompatible.load(other_package.execution_package_uuid)


def test_fail_closed_has_no_recovery_or_repository_modification(tmp_path):
    package, repository, consumer = assembled(tmp_path)
    before = {path: path.read_bytes() for path in repository.root.rglob("*.json")}
    rewrite(repository, package.execution_package_uuid,
            lambda value: value.update(execution_package_digest="f" * 64))
    corrupted = {path: path.read_bytes() for path in repository.root.rglob("*.json")}
    with pytest.raises(ExecutionPackageConsumerError):
        consumer.load(package.execution_package_uuid)
    assert {path: path.read_bytes() for path in repository.root.rglob("*.json")} == corrupted
    assert before != corrupted
    assert not any(hasattr(consumer, name) for name in
                   ("save", "repair", "evaluate", "score", "recommend", "execute"))
