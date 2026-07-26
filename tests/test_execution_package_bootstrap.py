"""Runtime bootstrap coverage for the PR189 -> PR190 -> PR191 boundary."""

import os
from pathlib import Path
import sys

import pytest

sys.path.insert(0, str(Path(__file__).parents[1]))
sys.path.insert(1, str(Path(__file__).parent / "learning"))

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


def test_bootstrap_assembles_persists_exports_then_starts(tmp_path, monkeypatch):
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


def test_corrupt_or_unloadable_package_fails_before_export(tmp_path, monkeypatch):
    readiness, environment, feasibility, _ = setup_engine(tmp_path)
    config = configuration(tmp_path, readiness, environment, feasibility)
    config.package_root.mkdir(parents=True)
    (config.package_root / "not-a-uuid.json").write_text("{}")
    monkeypatch.delenv("RP_EXECUTION_PACKAGE_UUID", raising=False)

    with pytest.raises(ExecutionPackageBootstrapError, match="PACKAGE_BOOTSTRAP_REJECTED"):
        ExecutionPackageRuntimeBootstrap(config).start(lambda: pytest.fail("started"))

    assert "RP_EXECUTION_PACKAGE_UUID" not in os.environ
