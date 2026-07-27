"""Runtime bootstrap coverage for the PR189 -> PR190 -> PR191 boundary."""

import os
from pathlib import Path
import sys

import pytest

sys.path.insert(0, str(Path(__file__).parents[1]))
sys.path.insert(1, str(Path(__file__).parent / "learning"))

import runtime.execution_package_bootstrap as bootstrap_module
from runtime.execution_package_bootstrap import (
    ExecutionPackageBootstrapConfiguration,
    ExecutionPackageBootstrapError,
    ExecutionPackageRuntimeBootstrap,
)
from test_pr189_execution_package import setup_engine


def configuration(root, readiness, environment, feasibility):
    return ExecutionPackageBootstrapConfiguration(
        readiness.execution_readiness_uuid,
        environment.execution_environment_uuid,
        feasibility.execution_feasibility_uuid,
        root / "execution_readiness",
        root / "execution_environment",
        root / "execution_feasibility",
        root / "execution_package",
    )


def test_bootstrap_assembles_persists_exports_then_starts(tmp_path, monkeypatch, capsys):
    readiness, environment, feasibility, _ = setup_engine(tmp_path)
    monkeypatch.delenv("RP_EXECUTION_PACKAGE_UUID", raising=False)
    observed = []

    result = ExecutionPackageRuntimeBootstrap(
        configuration(tmp_path, readiness, environment, feasibility)
    ).start(lambda: observed.append(os.environ["RP_EXECUTION_PACKAGE_UUID"]) or "started")

    assert result == "started"
    assert len(observed) == 1
    package_files = tuple((tmp_path / "execution_package").glob("*.json"))
    assert len(package_files) == 1
    assert observed[0] == package_files[0].stem
    output = capsys.readouterr().out
    assert "EXECUTION PACKAGE CONSUMED" in output
    assert "PACKAGE CREATED" not in output
    assert f"execution_package_uuid={observed[0]}" in output
    assert "execution_package_digest=" in output
    assert f"repository={tmp_path / 'execution_package'}" in output


def test_bootstrap_delegates_to_pr189_and_exports_its_unchanged_uuid(tmp_path, monkeypatch):
    readiness, environment, feasibility, engine = setup_engine(tmp_path)
    canonical, _ = engine.run(readiness, environment, feasibility)
    calls = []
    owner = bootstrap_module.GovernedExecutionPackageAssemblyEngine

    class ObservedCanonicalOwner(owner):
        def assemble(self, *args, **kwargs):
            result = super().assemble(*args, **kwargs)
            calls.append(result[0])
            return result

    monkeypatch.setattr(
        bootstrap_module,
        "GovernedExecutionPackageAssemblyEngine",
        ObservedCanonicalOwner,
    )
    observed = []
    ExecutionPackageRuntimeBootstrap(
        configuration(tmp_path, readiness, environment, feasibility)
    ).start(lambda: observed.append(os.environ["RP_EXECUTION_PACKAGE_UUID"]))

    assert calls == [canonical]
    assert observed == [canonical.execution_package_uuid]
    assert len(tuple((tmp_path / "execution_package").glob("*.json"))) == 1
    assert not (tmp_path / "pr223_execution_package").exists()


def test_bootstrap_restart_with_same_exact_inputs_is_idempotent(tmp_path, monkeypatch):
    readiness, environment, feasibility, _ = setup_engine(tmp_path)
    config = configuration(tmp_path, readiness, environment, feasibility)
    bootstrap = ExecutionPackageRuntimeBootstrap(config)
    monkeypatch.delenv("RP_EXECUTION_PACKAGE_UUID", raising=False)
    exports = []

    assert bootstrap.start(lambda: exports.append(os.environ["RP_EXECUTION_PACKAGE_UUID"])) is None
    package_files = tuple(config.package_root.glob("*.json"))
    snapshot_files = tuple((config.package_root / "snapshots").glob("*.json"))
    assert len(package_files) == len(snapshot_files) == 1
    canonical_bytes = package_files[0].read_bytes()
    package_stat = package_files[0].stat()
    snapshot_bytes = snapshot_files[0].read_bytes()

    assert bootstrap.start(lambda: exports.append(os.environ["RP_EXECUTION_PACKAGE_UUID"])) is None

    assert exports == [package_files[0].stem, package_files[0].stem]
    assert tuple(config.package_root.glob("*.json")) == package_files
    assert tuple((config.package_root / "snapshots").glob("*.json")) == snapshot_files
    assert package_files[0].read_bytes() == canonical_bytes
    assert snapshot_files[0].read_bytes() == snapshot_bytes
    assert package_files[0].stat().st_ino == package_stat.st_ino
    assert package_files[0].stat().st_mtime_ns == package_stat.st_mtime_ns


def test_bootstrap_requires_exact_upstream_identity_and_never_starts(tmp_path, monkeypatch):
    readiness, environment, feasibility, _ = setup_engine(tmp_path)
    monkeypatch.delenv("RP_EXECUTION_PACKAGE_UUID", raising=False)
    config = configuration(tmp_path, readiness, environment, feasibility)
    config = ExecutionPackageBootstrapConfiguration(
        "00000000-0000-5000-8000-000000000000", config.environment_uuid,
        config.feasibility_uuid, config.readiness_root, config.environment_root,
        config.feasibility_root, config.package_root,
    )
    started = []

    with pytest.raises(ExecutionPackageBootstrapError, match="READINESS_MISSING"):
        ExecutionPackageRuntimeBootstrap(config).start(lambda: started.append(True))

    assert started == []
    assert "RP_EXECUTION_PACKAGE_UUID" not in os.environ
    assert not config.package_root.exists()


def test_corrupt_exact_target_package_fails_without_repair_or_export(tmp_path, monkeypatch):
    readiness, environment, feasibility, _ = setup_engine(tmp_path)
    config = configuration(tmp_path, readiness, environment, feasibility)
    bootstrap = ExecutionPackageRuntimeBootstrap(config)
    monkeypatch.delenv("RP_EXECUTION_PACKAGE_UUID", raising=False)
    bootstrap.start(lambda: None)
    target = next(config.package_root.glob("*.json"))
    corrupt_bytes = b"{}"
    target.write_bytes(corrupt_bytes)
    monkeypatch.delenv("RP_EXECUTION_PACKAGE_UUID")
    invoked = []

    with pytest.raises(ExecutionPackageBootstrapError, match="PACKAGE_BOOTSTRAP_REJECTED"):
        bootstrap.start(lambda: invoked.append(True))

    assert invoked == []
    assert "RP_EXECUTION_PACKAGE_UUID" not in os.environ
    assert target.read_bytes() == corrupt_bytes


@pytest.mark.parametrize(
    ("field", "value", "reason"),
    (
        ("readiness_uuid", "not-a-uuid", "INVALID_READINESS_UUID"),
        ("environment_uuid", "AAAAAAAA-AAAA-4AAA-8AAA-AAAAAAAAAAAA", "INVALID_ENVIRONMENT_UUID"),
        ("feasibility_uuid", "", "INVALID_FEASIBILITY_UUID"),
    ),
)
def test_configuration_rejects_noncanonical_uuids(field, value, reason):
    values = {
        "readiness_uuid": "00000000-0000-4000-8000-000000000001",
        "environment_uuid": "00000000-0000-4000-8000-000000000002",
        "feasibility_uuid": "00000000-0000-4000-8000-000000000003",
    }
    values[field] = value
    with pytest.raises(ExecutionPackageBootstrapError, match=reason):
        ExecutionPackageBootstrapConfiguration(**values)


@pytest.mark.parametrize(
    "field",
    ("readiness_root", "environment_root", "feasibility_root", "package_root"),
)
def test_configuration_rejects_invalid_root_types(field):
    values = {
        "readiness_uuid": "00000000-0000-4000-8000-000000000001",
        "environment_uuid": "00000000-0000-4000-8000-000000000002",
        "feasibility_uuid": "00000000-0000-4000-8000-000000000003",
        field: "not-a-path",
    }
    with pytest.raises(ExecutionPackageBootstrapError, match="INVALID_REPOSITORY_ROOT"):
        ExecutionPackageBootstrapConfiguration(**values)


def test_runtime_failure_without_previous_export_restores_absence(tmp_path, monkeypatch):
    readiness, environment, feasibility, _ = setup_engine(tmp_path)
    monkeypatch.delenv("RP_EXECUTION_PACKAGE_UUID", raising=False)
    invocations = []

    def fail():
        invocations.append(os.environ["RP_EXECUTION_PACKAGE_UUID"])
        raise RuntimeError("runtime startup failed")

    with pytest.raises(RuntimeError, match="runtime startup failed"):
        ExecutionPackageRuntimeBootstrap(
            configuration(tmp_path, readiness, environment, feasibility)
        ).start(fail)

    assert len(invocations) == 1
    assert "RP_EXECUTION_PACKAGE_UUID" not in os.environ


def test_runtime_failure_restores_previous_export(tmp_path, monkeypatch):
    readiness, environment, feasibility, _ = setup_engine(tmp_path)
    previous = "00000000-0000-4000-8000-000000000099"
    monkeypatch.setenv("RP_EXECUTION_PACKAGE_UUID", previous)
    invocations = []

    def fail():
        invocations.append(os.environ["RP_EXECUTION_PACKAGE_UUID"])
        raise RuntimeError("runtime startup failed")

    with pytest.raises(RuntimeError, match="runtime startup failed"):
        ExecutionPackageRuntimeBootstrap(
            configuration(tmp_path, readiness, environment, feasibility)
        ).start(fail)

    assert len(invocations) == 1
    assert invocations[0] != previous
    assert os.environ["RP_EXECUTION_PACKAGE_UUID"] == previous
