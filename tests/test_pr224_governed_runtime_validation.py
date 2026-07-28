"""PR224 end-to-end validation of the existing governed runtime authorities.

This is intentionally a consumer-side test.  It composes public PR183--PR190
interfaces, but does not add another persistence, selection, or execution
authority.
"""

from dataclasses import FrozenInstanceError
import json
from pathlib import Path
import sys

import pytest

sys.path.insert(0, str(Path(__file__).parent / "learning"))
sys.path.insert(0, str(Path(__file__).parents[1]))

from learning.decision_intelligence import (  # noqa: E402
    DecisionIntelligenceRepository,
    GovernedDecisionIntelligenceEngine,
)
from learning.decision_intelligence.operator_activation import commit_activation  # noqa: E402
from learning.decision_recommendation import (  # noqa: E402
    DecisionRecommendationRepository,
    GovernedDecisionRecommendationEngine,
)
from learning.execution_environment import (  # noqa: E402
    ExecutionEnvironmentEvidenceRepository,
    ExecutionEnvironmentRepository,
    GovernedExecutionEnvironmentEngine,
)
from learning.execution_feasibility import (  # noqa: E402
    ExecutionFeasibilityRepository,
    GovernedExecutionFeasibilityEngine,
)
from learning.execution_package import (  # noqa: E402
    ExecutionPackageRepository,
    GovernedExecutionPackageAssemblyEngine,
)
from learning.execution_package_consumer import ExecutionPackageConsumer  # noqa: E402
from learning.execution_readiness import (  # noqa: E402
    ExecutionReadinessRepository,
    GovernedExecutionReadinessEngine,
)
from runtime.market_state_reader import GovernedMarketStateReader  # noqa: E402
from test_pr183_decision_context import setup_engine as context_setup  # noqa: E402
from test_pr187_execution_environment import evidence_for  # noqa: E402
from test_pr223_governed_reader import NOW, publish  # noqa: E402


def test_complete_governed_runtime_reaches_immutable_executor_input_once(tmp_path):
    """Exercise every owner once and prove PR189 survives PR190 byte-for-byte."""
    invocations = {name: 0 for name in (
        "writer", "reader", "context", "intelligence", "activation",
        "recommendation", "readiness", "environment", "feasibility",
        "package", "consumer", "executor_input",
    )}

    publication = tmp_path / "market_state.json"
    publish(publication)
    invocations["writer"] += 1
    market_state = GovernedMarketStateReader(clock=lambda: NOW).read(publication)
    invocations["reader"] += 1

    confidence_report, _, context_engine = context_setup(tmp_path)
    context_report = context_engine.construct_context(confidence_report)
    context = context_report.decision_contexts[0]
    invocations["context"] += 1

    intelligence_engine = GovernedDecisionIntelligenceEngine(
        context_engine.repository,
        DecisionIntelligenceRepository(tmp_path / "decision_intelligence"),
    )
    intelligence_report = intelligence_engine.run(context_report)
    intelligence = intelligence_report.decision_intelligences[0]
    invocations["intelligence"] += 1
    activation = commit_activation(
        repository_root=intelligence_engine.repository.root,
        intelligence_uuid=intelligence.intelligence_uuid,
        snapshot_uuid=intelligence_report.snapshot_uuid,
        authority_owner="PR184_DECISION_INTELLIGENCE_OWNER",
        activated_at=intelligence.created_at,
    )
    invocations["activation"] += 1

    recommendation_engine = GovernedDecisionRecommendationEngine(
        intelligence_engine.repository,
        DecisionRecommendationRepository(tmp_path / "decision_recommendation"),
    )
    recommendation_report = recommendation_engine.run(intelligence_report)
    recommendation = recommendation_report.recommendations[0]
    invocations["recommendation"] += 1

    readiness_engine = GovernedExecutionReadinessEngine(
        recommendation_engine.repository,
        ExecutionReadinessRepository(tmp_path / "execution_readiness"),
    )
    readiness = readiness_engine.run(
        recommendation_report
    ).execution_readiness_records[0]
    invocations["readiness"] += 1

    environment_engine = GovernedExecutionEnvironmentEngine(
        readiness_engine.repository,
        ExecutionEnvironmentRepository(tmp_path / "execution_environment"),
        evidence_repository=ExecutionEnvironmentEvidenceRepository(
            tmp_path / "execution_environment_evidence"
        ),
    )
    evidence_for(
        type("Report", (), {"execution_readiness_records": (readiness,)})(),
        environment_engine,
    )
    environment = environment_engine.run(readiness).execution_environment_records[0]
    invocations["environment"] += 1

    feasibility_engine = GovernedExecutionFeasibilityEngine(
        readiness_engine.repository,
        environment_engine.repository,
        ExecutionFeasibilityRepository(tmp_path / "execution_feasibility"),
    )
    feasibility = feasibility_engine.run(
        readiness, environment
    ).execution_feasibility_records[0]
    invocations["feasibility"] += 1

    package_repository = ExecutionPackageRepository(tmp_path / "execution_package")
    package_engine = GovernedExecutionPackageAssemblyEngine(
        readiness_engine.repository,
        environment_engine.repository,
        feasibility_engine.repository,
        package_repository,
    )
    package, package_report = package_engine.run(readiness, environment, feasibility)
    invocations["package"] += 1
    package_path = package_repository.root / f"{package.execution_package_uuid}.json"
    before = package_path.read_bytes()
    consumed = ExecutionPackageConsumer(package_repository).load(
        package.execution_package_uuid
    )
    invocations["consumer"] += 1
    executor_input = consumed
    invocations["executor_input"] += 1

    # Concrete lineage fields owned by each subsystem are continuous.  The
    # activation is the canonical selection of this exact intelligence record.
    assert context.context_uuid == intelligence.decision_context_uuid
    assert activation.intelligence_uuid == intelligence.intelligence_uuid
    assert recommendation.decision_intelligence_uuid == intelligence.intelligence_uuid
    assert readiness.recommendation_uuid == recommendation.recommendation_uuid
    assert environment.execution_readiness_uuid == readiness.execution_readiness_uuid
    assert feasibility.execution_readiness_uuid == readiness.execution_readiness_uuid
    assert feasibility.execution_environment_uuid == environment.execution_environment_uuid
    assert package.execution_readiness_uuid == readiness.execution_readiness_uuid
    assert package.execution_environment_uuid == environment.execution_environment_uuid
    assert package.execution_feasibility_uuid == feasibility.execution_feasibility_uuid

    # Latest-snapshot, immutable-identity, single-authority, and propagation
    # invariants are checked from the owners' canonical repositories.
    assert market_state.values["source_uuid"] == market_state.source_uuid
    assert len(intelligence_engine.repository.activations()) == 1
    assert len(package_repository.records()) == 1
    snapshot = package_repository.latest_snapshot()
    assert snapshot.snapshot_uuid == package_report.snapshot_uuid
    assert snapshot.repository_digest == package_report.repository_digest
    assert snapshot.package_identities == (
        (package.execution_package_uuid, package.execution_package_digest),
    )
    assert consumed is not package and consumed == package == executor_input
    assert consumed.to_dict() == package.to_dict()
    assert package_path.read_bytes() == before
    assert json.loads(before)["execution_package_uuid"] == package.execution_package_uuid
    with pytest.raises(FrozenInstanceError):
        executor_input.package_state = "MUTATED"

    assert invocations and set(invocations.values()) == {1}
