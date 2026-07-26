"""PR191 immutable V26 execution-confidence integration tests."""
from dataclasses import FrozenInstanceError
import json
from pathlib import Path
import sys
import pytest
sys.path.insert(0, str(Path(__file__).parents[2]))
sys.path.insert(1, str(Path(__file__).parent))
from bridge.execution_confidence_integration import (ExecutionConfidenceContext,
    ExecutionConfidenceIntegration, ExecutionConfidenceIntegrationError)
from learning.execution_package.identity import canonical_bytes, digest
from learning.execution_package_consumer import ExecutionPackageConsumer
from test_pr189_execution_package import setup_engine

def assembled(tmp_path):
    readiness, environment, feasibility, engine = setup_engine(tmp_path)
    package, _ = engine.run(readiness, environment, feasibility)
    return package, engine.repository, ExecutionConfidenceIntegration(ExecutionPackageConsumer(engine.repository))

def rewrite(repository, package_uuid, mutate):
    path = repository.root / f"{package_uuid}.json"
    value = json.loads(path.read_text()); mutate(value)
    path.write_bytes(canonical_bytes(value))

def test_successful_integration_and_immutable_consumption(tmp_path):
    package, _, integration = assembled(tmp_path)
    context = integration.consume(package.execution_package_uuid)
    assert (context.execution_readiness, context.environment_assessment, context.feasibility_assessment) == (
        "EXECUTION_READY_FOR_ENVIRONMENT_CHECK", "ENVIRONMENT_READY_FOR_FEASIBILITY", "EXECUTION_FEASIBLE")
    assert context.advisory_only is True
    with pytest.raises(FrozenInstanceError):
        context.package_state = "REJECTED"
    assert integration.consume(package.execution_package_uuid) == context

def test_missing_package_and_consumer_failure_fail_closed(tmp_path):
    _, _, integration = assembled(tmp_path)
    with pytest.raises(ExecutionConfidenceIntegrationError, match="PACKAGE_REJECTED"):
        integration.consume("00000000-0000-5000-8000-000000000000")
    with pytest.raises(ExecutionConfidenceIntegrationError, match="CONSUMER_FAILURE"):
        ExecutionConfidenceIntegration(object())

def test_invalid_package_fails_closed_without_mutation(tmp_path):
    package, repository, integration = assembled(tmp_path)
    rewrite(repository, package.execution_package_uuid, lambda value: value.update(execution_package_digest="0" * 64))
    before = {path: path.read_bytes() for path in repository.root.rglob("*.json")}
    with pytest.raises(ExecutionConfidenceIntegrationError, match="PACKAGE_REJECTED"):
        integration.consume(package.execution_package_uuid)
    assert {path: path.read_bytes() for path in repository.root.rglob("*.json")} == before

@pytest.mark.parametrize("field,value", [
    ("package_policy_version", "PR189-PACKAGE-POLICY.99"),
    ("package_reason", "IMMUTABLE_ADVISORY_PACKAGE_ASSEMBLED "),
])
def test_version_and_replay_mismatch_fail_closed(tmp_path, field, value):
    package, repository, integration = assembled(tmp_path)
    def corrupt(raw):
        raw[field] = value
        payload = {key: item for key, item in raw.items() if key != "execution_package_digest"}
        raw["execution_package_digest"] = digest(payload)
    rewrite(repository, package.execution_package_uuid, corrupt)
    with pytest.raises(ExecutionConfidenceIntegrationError, match="PACKAGE_REJECTED"):
        integration.consume(package.execution_package_uuid)

def test_context_rejects_inconsistent_assessments():
    with pytest.raises(ExecutionConfidenceIntegrationError, match="INVALID_CONFIDENCE_CONTEXT"):
        ExecutionConfidenceContext("id", "digest", "PACKAGE_READY", "reason",
            "NOT_CONFIRMED_BY_PACKAGE", "ENVIRONMENT_READY_FOR_FEASIBILITY",
            "EXECUTION_FEASIBLE", "policy", "engine", "timestamp", "id")
